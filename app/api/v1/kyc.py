"""
KYC and email verification routes.
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.services.kyc_service import get_kyc_status, submit_kyc
from app.services.email_service import (
    send_verification_email,
    verify_email_token
)

router = APIRouter(prefix="/api/v1/kyc", tags=["KYC"])


@router.get("/status")
def kyc_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current KYC status."""
    return get_kyc_status(db, current_user)


@router.post("/submit")
async def submit_kyc_docs(
    document_type: str = Form(...),
    document_number: str = Form(...),
    document_country: str = Form(...),
    front_image: UploadFile = File(...),
    back_image: Optional[UploadFile] = File(None),
    selfie: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit KYC documents for review."""
    return submit_kyc(
        db=db,
        user=current_user,
        document_type=document_type,
        document_number=document_number,
        document_country=document_country,
        front_image=front_image,
        back_image=back_image,
        selfie=selfie
    )


@router.post("/send-verification-email")
def send_verification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resend email verification link."""
    if current_user.is_email_verified:
        return {"message": "Your email is already verified."}

    sent = send_verification_email(db, current_user)
    if sent:
        return {
            "message": (
                "Verification email sent. "
                "Please check your inbox and spam folder."
            )
        }
    return {
        "message": (
            "Email service not configured. "
            "Please contact support to verify your email."
        )
    }


@router.get("/verify-email")
def verify_email(
    token: str,
    db: Session = Depends(get_db)
):
    """Verify email address using token from email link."""
    user = verify_email_token(db, token)
    return {
        "message": "Email verified successfully! You can now log in.",
        "email": user.email
    }