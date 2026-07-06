import uuid
from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class FXConversion(Base):
    __tablename__ = "fx_conversions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False)

    # What the user sent
    from_currency = Column(String, nullable=False)   # e.g. "USD"
    from_amount = Column(Numeric(precision=18, scale=2), nullable=False)

    # What the user received
    to_currency = Column(String, nullable=False)     # e.g. "NGN"
    to_amount = Column(Numeric(precision=18, scale=2), nullable=False)

    # Rate details — store everything for audit trail
    interbank_rate = Column(Numeric(precision=18, scale=6), nullable=False)
    platform_rate = Column(Numeric(precision=18, scale=6), nullable=False)
    spread_percent = Column(Numeric(precision=5, scale=2), nullable=False)
    fee_usd = Column(Numeric(precision=18, scale=2), nullable=False)

    # Reference links to the wallet transaction
    transaction_reference = Column(String, nullable=False)

    status = Column(String, default="completed", nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())