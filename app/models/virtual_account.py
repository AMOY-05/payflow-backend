import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class VirtualAccount(Base):
    __tablename__ = "virtual_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # One virtual account per user for now
    # In later phases a user can have multiple accounts in different currencies
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)

    # US bank account details
    account_number = Column(String, unique=True, nullable=False)
    routing_number = Column(String, nullable=False)
    account_name = Column(String, nullable=False)
    bank_name = Column(String, nullable=False, default="Lead Bank")

    # Type of account — most freelancers need checking
    account_type = Column(String, nullable=False, default="checking")

    # Currency this account receives
    currency = Column(String, nullable=False, default="USD")

    # Which provider issued this account
    # "mock" for now, "grey" / "stripe_treasury" / "lead_bank" in Phase 9
    provider = Column(String, nullable=False, default="mock")

    # Provider's own reference ID for this account
    provider_account_id = Column(String, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", back_populates="virtual_account")