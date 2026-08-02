import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Date, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    full_name = Column(String, nullable=False)
    country = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)

    date_of_birth = Column(Date, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    business_type = Column(String, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    is_kyc_verified = Column(Boolean, default=False, nullable=False)
    is_email_verified = Column(Boolean, default=False, nullable=False)

    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    wallet = relationship("Wallet", back_populates="user", uselist=False)
    virtual_account = relationship(
        "VirtualAccount", back_populates="user", uselist=False
    )
    kyc = relationship("KYCVerification", back_populates="user", uselist=False)