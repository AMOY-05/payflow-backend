from asyncio.log import logger
import random
from venv import logger
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.models.wallet import Wallet
from app.models.virtual_account import VirtualAccount
from app.schemas.user import UserCreate
from app.core.security import hash_password, verify_password

import logging
logger = logging.getLogger("fintech.auth")

def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def generate_account_number(db: Session) -> str:
    while True:
        number = "".join([str(random.randint(0, 9)) for _ in range(10)])
        exists = db.query(VirtualAccount).filter(
            VirtualAccount.account_number == number
        ).first()
        if not exists:
            return number


def create_user(db: Session, user_in: UserCreate) -> User:
    existing = get_user_by_email(db, user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Create user
    user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
        country=user_in.country,
        phone_number=user_in.phone_number,
    )
    db.add(user)
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
    db.refresh(user)

    # Send email verification
    try:
        from app.services.email_service import send_verification_email
        send_verification_email(db, user)
    except Exception as e:
        logger.warning(f"Failed to send verification email: {e}")

    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
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