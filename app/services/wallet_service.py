import uuid
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.wallet import Wallet, Transaction
from app.models.user import User


def get_or_create_wallet(db: Session, user: User) -> Wallet:
    """
    Get the user's wallet. If it doesn't exist yet, create it.
    This is a safety net — wallets are normally created at registration.
    """
    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
    if not wallet:
        wallet = Wallet(user_id=user.id, balance=Decimal("0.00"), currency="USD")
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
    return wallet


def get_wallet_balance(db: Session, user: User) -> Wallet:
    return get_or_create_wallet(db, user)


def deposit_funds(db: Session, user: User, amount: Decimal, description: str = None) -> Transaction:
    """
    Simulate a deposit into the user's USD wallet.

    In Phase 9 this will be replaced by a real webhook from
    a payment provider (e.g. Grey, Stripe Treasury) that calls
    this same function after confirming funds have arrived.
    """
    if amount <= Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deposit amount must be greater than zero"
        )

    # Cap simulated deposits at $50,000 per transaction for compliance reasons
    if amount > Decimal("50000.00"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum deposit amount is $50,000 per transaction"
        )

    wallet = get_or_create_wallet(db, user)
    balance_before = wallet.balance
    balance_after = balance_before + amount

    # Update wallet balance
    wallet.balance = balance_after
    db.add(wallet)

    # Record the transaction — every money movement must be logged
    transaction = Transaction(
        wallet_id=wallet.id,
        transaction_type="credit",
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
        category="deposit",
        description=description or "Simulated deposit",
        reference=f"DEP-{uuid.uuid4().hex.upper()[:16]}",
        status="success"
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def get_transaction_history(
    db: Session,
    user: User,
    limit: int = 20,
    offset: int = 0
) -> dict:
    wallet = get_or_create_wallet(db, user)

    total = db.query(Transaction).filter(
        Transaction.wallet_id == wallet.id
    ).count()

    transactions = db.query(Transaction).filter(
        Transaction.wallet_id == wallet.id
    ).order_by(
        Transaction.created_at.desc()
    ).limit(limit).offset(offset).all()

    return {"total": total, "transactions": transactions}