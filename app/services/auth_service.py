"""
Authentication service — user creation and credential verification.
"""

import logging
import secrets
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.user import User
from app.models.wallet import Wallet
from app.models.virtual_account import VirtualAccount
from app.schemas.user import UserCreate
from app.core.security import hash_password, verify_password

logger = logging.getLogger("fintech.auth")

# Bounded, so a database fault can never spin this forever.
_ACCOUNT_NUMBER_ATTEMPTS = 10

# Built once on first miss. See _equalise_timing below.
_dummy_hash: str | None = None


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def generate_account_number(db: Session) -> str:
    """
    Generate a unique 10-digit account number.

    Uses `secrets` rather than `random`. Mersenne Twister output is
    reconstructible from enough observed values, and account numbers on a
    financial product must not be predictable from previously issued ones.
    """
    for _ in range(_ACCOUNT_NUMBER_ATTEMPTS):
        number = "".join(str(secrets.randbelow(10)) for _ in range(10))
        exists = db.query(VirtualAccount).filter(
            VirtualAccount.account_number == number
        ).first()
        if not exists:
            return number

    logger.error(
        "Could not generate a unique account number in %d attempts",
        _ACCOUNT_NUMBER_ATTEMPTS,
    )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Could not allocate an account number. Please try again.",
    )


def create_user(db: Session, user_in: UserCreate) -> User:
    existing = get_user_by_email(db, user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
        country=user_in.country,
        phone_number=user_in.phone_number,
    )
    db.add(user)

    try:
        db.flush()  # get user.id without committing

        # Auto-create USD wallet
        wallet = Wallet(
            user_id=user.id,
            balance=Decimal("0.00"),
            currency="USD"
        )
        db.add(wallet)

        # Auto-create virtual USD account
        virtual_account = VirtualAccount(
            user_id=user.id,
            account_number=generate_account_number(db),
            routing_number="101019644",
            account_name=user_in.full_name.upper(),
            bank_name="Lead Bank",
            account_type="checking",
            currency="USD",
            provider="mock",
        )
        db.add(virtual_account)

        db.commit()

    except IntegrityError:
        # The duplicate check above is a read. Two concurrent registrations
        # can both pass it and only collide here, on the unique constraint.
        db.rollback()
        logger.info("Registration collided on a unique constraint")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    except Exception:
        # Without this the session stays poisoned for the rest of the
        # request and every later query in it fails too.
        db.rollback()
        raise

    db.refresh(user)

    # Send email verification.
    # Deliberately non-fatal: a mail outage should not fail a registration
    # that has already been committed.
    try:
        from app.services.email_service import send_verification_email
        send_verification_email(db, user)
    except Exception as e:
        logger.error(f"Failed to send verification email: {e}")

    return user


def _equalise_timing(password: str) -> None:
    """
    Run one hash comparison against a throwaway hash.

    Without this an unknown email returns before bcrypt is ever called, and
    the gap between that and a real password check is wide enough to
    enumerate which addresses are registered.
    """
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("timing-equalisation-placeholder")
    verify_password(password, _dummy_hash)


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)

    if not user:
        _equalise_timing(password)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    # Soft-deleted accounts get the same answer as a wrong password, so
    # deletion is not observable from the outside.
    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been disabled. Contact support.",
        )

    return user