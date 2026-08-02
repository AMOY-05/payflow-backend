import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, func, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class KYCVerification(Base):
    __tablename__ = "kyc_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        unique=True,
        nullable=False
    )

    # Document details
    document_type = Column(String, nullable=False)
    # international_passport, drivers_license, national_id,
    # voters_card, residence_permit

    document_number = Column(String, nullable=True)
    document_country = Column(String, nullable=True)

    # File paths (stored on server)
    front_image_path = Column(String, nullable=True)
    back_image_path = Column(String, nullable=True)
    selfie_path = Column(String, nullable=True)

    # Status flow:
    # not_submitted → pending → approved
    # not_submitted → pending → rejected
    status = Column(String, default="not_submitted", nullable=False)
    rejection_reason = Column(Text, nullable=True)
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    submitted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    user = relationship("User", back_populates="kyc")