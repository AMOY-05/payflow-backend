import uuid
from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # One wallet per user
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)

    # NEVER use float for money — Numeric(precision, scale) maps to
    # PostgreSQL DECIMAL which is exact. Float loses precision and can
    # cause $0.001 errors that compound over thousands of transactions.
    balance = Column(Numeric(precision=18, scale=2), default=0.00, nullable=False)

    currency = Column(String, default="USD", nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", back_populates="wallet")
    transactions = relationship("Transaction", back_populates="wallet", order_by="Transaction.created_at.desc()")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False)

    # credit = money coming in, debit = money going out
    transaction_type = Column(String, nullable=False)  # "credit" or "debit"

    amount = Column(Numeric(precision=18, scale=2), nullable=False)
    balance_before = Column(Numeric(precision=18, scale=2), nullable=False)
    balance_after = Column(Numeric(precision=18, scale=2), nullable=False)

    # What caused this transaction
    # e.g. "deposit", "withdrawal", "fx_conversion", "transfer"
    category = Column(String, nullable=False)

    description = Column(String, nullable=True)
    reference = Column(String, unique=True, nullable=False)  # unique transaction ID
    status = Column(String, default="success", nullable=False)  # success, pending, failed

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    wallet = relationship("Wallet", back_populates="transactions")