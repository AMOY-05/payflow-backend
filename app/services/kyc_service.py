"""
KYC verification service.
Handles document upload, status tracking, and admin review.
"""

import os
import uuid
import shutil
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.models.kyc import KYCVerification
from app.models.user import User

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
ALLOWED_DOCUMENT_TYPES = {
    "international_passport",
    "drivers_license",
    "national_id",
    "voters_card",
    "residence_permit",
}


def validate_file(file: UploadFile) -> None:
    """Validate file type and size."""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Use: {', '.join(ALLOWED_EXTENSIONS)}"
        )


def save_upload(file: UploadFile, user_id: str, doc_type: str) -> str:
    """Save uploaded file and return file path."""
    upload_dir = os.path.join(settings.KYC_UPLOAD_DIR, str(user_id))
    os.makedirs(upload_dir, exist_ok=True)

    ext = os.path.splitext(file.filename)[1].lower()
    filename = f"{doc_type}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return file_path


def get_or_create_kyc(db: Session, user: User) -> KYCVerification:
    """Get existing KYC record or create new one."""
    kyc = db.query(KYCVerification).filter(
        KYCVerification.user_id == user.id
    ).first()

    if not kyc:
        kyc = KYCVerification(
            user_id=user.id,
            status="not_submitted"
        )
        db.add(kyc)
        db.commit()
        db.refresh(kyc)

    return kyc


def get_kyc_status(db: Session, user: User) -> dict:
    """Get user's current KYC status."""
    kyc = get_or_create_kyc(db, user)

    return {
        "status": kyc.status,
        "document_type": kyc.document_type,
        "submitted_at": kyc.submitted_at.isoformat() if kyc.submitted_at else None,
        "reviewed_at": kyc.reviewed_at.isoformat() if kyc.reviewed_at else None,
        "rejection_reason": kyc.rejection_reason,
        "is_kyc_verified": user.is_kyc_verified,
        "allowed_document_types": list(ALLOWED_DOCUMENT_TYPES),
    }


def submit_kyc(
    db: Session,
    user: User,
    document_type: str,
    document_number: str,
    document_country: str,
    front_image: UploadFile,
    back_image: UploadFile = None,
    selfie: UploadFile = None,
) -> dict:
    """Submit KYC documents for review."""
    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document type. Allowed: {', '.join(ALLOWED_DOCUMENT_TYPES)}"
        )

    kyc = get_or_create_kyc(db, user)

    if kyc.status == "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your KYC is already approved."
        )

    # Validate and save front image (required)
    validate_file(front_image)
    front_path = save_upload(front_image, str(user.id), "front")

    # Save back image if provided
    back_path = None
    if back_image and back_image.filename:
        validate_file(back_image)
        back_path = save_upload(back_image, str(user.id), "back")

    # Save selfie if provided
    selfie_path = None
    if selfie and selfie.filename:
        validate_file(selfie)
        selfie_path = save_upload(selfie, str(user.id), "selfie")

    # Update KYC record
    kyc.document_type = document_type
    kyc.document_number = document_number
    kyc.document_country = document_country
    kyc.front_image_path = front_path
    kyc.back_image_path = back_path
    kyc.selfie_path = selfie_path
    kyc.status = "pending"
    kyc.submitted_at = datetime.now(timezone.utc)
    kyc.rejection_reason = None

    db.add(kyc)
    db.commit()

    return {
        "message": (
            "KYC documents submitted successfully. "
            "Our team will review your documents within 24-48 hours. "
            "You will receive an email notification when your KYC is processed."
        ),
        "status": "pending",
        "submitted_at": kyc.submitted_at.isoformat()
    }


def admin_review_kyc(
    db: Session,
    user_id: str,
    action: str,
    reason: str = None
) -> dict:
    """Admin approves or rejects KYC."""
    kyc = db.query(KYCVerification).filter(
        KYCVerification.user_id == user_id
    ).first()

    if not kyc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC record not found"
        )

    user = db.query(User).filter(User.id == user_id).first()

    if action == "approve":
        kyc.status = "approved"
        kyc.rejection_reason = None
        user.is_kyc_verified = True
    elif action == "reject":
        kyc.status = "rejected"
        kyc.rejection_reason = reason or "Document could not be verified"
        user.is_kyc_verified = False
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be 'approve' or 'reject'"
        )

    kyc.reviewed_at = datetime.now(timezone.utc)
    db.add(kyc)
    db.add(user)
    db.commit()

    # Send email notification
    from app.services.email_service import send_kyc_status_email
    send_kyc_status_email(user, action, reason)

    return {
        "message": f"KYC {action}d for user {user.email}",
        "status": kyc.status
    }