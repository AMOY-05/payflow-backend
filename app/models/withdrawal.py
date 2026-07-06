import uuid
from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False)

    # Amount details
    amount = Column(Numeric(precision=18, scale=2), nullable=False)
    fee = Column(Numeric(precision=18, scale=2), nullable=False)
    amount_after_fee = Column(Numeric(precision=18, scale=2), nullable=False)
    currency = Column(String, default="USD", nullable=False)

    # Routing details
    provider = Column(String, nullable=False)       # flutterwave, grey, wire, ach etc
    method = Column(String, nullable=False)         # bank_transfer, wire_transfer, ach
    estimated_delivery = Column(String, nullable=False)

    # Recipient bank details
    bank_name = Column(String, nullable=False)
    account_number = Column(String, nullable=False)
    account_name = Column(String, nullable=False)
    bank_code = Column(String, nullable=True)       # required by Flutterwave
    destination_country = Column(String, nullable=False)
    destination_currency = Column(String, nullable=False)

    # Tracking
    reference = Column(String, unique=True, nullable=False)
    provider_reference = Column(String, nullable=True)  # provider's own ID

    # Status flow:
    # pending → processing → completed
    # pending → cancelled
    # pending → failed
    status = Column(String, default="pending", nullable=False)
    status_message = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)