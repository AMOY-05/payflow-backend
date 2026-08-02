"""
Admin API routes.
Protected by admin secret key — never expose these to regular users.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.config import settings
from app.core.mongodb import get_mongo_db
from app.services.admin_service import (
    get_platform_stats,
    get_all_users,
    get_all_withdrawals,
    suspend_user,
    reactivate_user,
    verify_user_kyc,
    log_admin_action
)
from app.models.kyc import KYCVerification
from app.models.user import User

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


def verify_admin_key(x_admin_key: Optional[str] = None):
    """Verify admin secret key from request header."""
    from fastapi import Header
    if not x_admin_key or x_admin_key != settings.ADMIN_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin key"
        )
    return x_admin_key


from fastapi import Header

def get_admin_key(x_admin_key: Optional[str] = Header(None)):
    if not x_admin_key or x_admin_key != settings.ADMIN_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin key"
        )
    return x_admin_key


@router.get("/stats")
def platform_stats(
    db: Session = Depends(get_db),
    admin_key: str = Depends(get_admin_key)
):
    """Get full platform statistics."""
    return get_platform_stats(db)


@router.get("/users")
def list_users(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin_key: str = Depends(get_admin_key)
):
    """Get all users with pagination."""
    return get_all_users(db, limit, offset)


@router.get("/withdrawals")
def list_withdrawals(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin_key: str = Depends(get_admin_key)
):
    """Get all withdrawals with pagination."""
    return get_all_withdrawals(db, limit, offset)


@router.post("/users/{user_id}/suspend")
def suspend(
    user_id: str,
    db: Session = Depends(get_db),
    mongo_db=Depends(get_mongo_db),
    admin_key: str = Depends(get_admin_key)
):
    result = suspend_user(db, user_id)
    log_admin_action(mongo_db, "admin", "suspend_user", {"user_id": user_id})
    return result


@router.post("/users/{user_id}/reactivate")
def reactivate(
    user_id: str,
    db: Session = Depends(get_db),
    mongo_db=Depends(get_mongo_db),
    admin_key: str = Depends(get_admin_key)
):
    result = reactivate_user(db, user_id)
    log_admin_action(
        mongo_db, "admin", "reactivate_user", {"user_id": user_id}
    )
    return result


@router.post("/users/{user_id}/verify-kyc")
def approve_kyc_admin(
    user_id: str,
    db: Session = Depends(get_db),
    mongo_db=Depends(get_mongo_db),
    admin_key: str = Depends(get_admin_key)
):
    result = verify_user_kyc(db, user_id)
    log_admin_action(mongo_db, "admin", "verify_kyc", {"user_id": user_id})
    return result


@router.post("/users/{user_id}/verify-email")
def admin_verify_email(
    user_id: str,
    db: Session = Depends(get_db),
    mongo_db=Depends(get_mongo_db),
    admin_key: str = Depends(get_admin_key)
):
    """Manually verify a user's email address."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    user.is_email_verified = True
    db.add(user)
    db.commit()
    log_admin_action(
        mongo_db, "admin", "verify_email", {"user_id": user_id}
    )
    return {"success": True, "message": f"Email verified for {user.email}"}


@router.get("/kyc/pending")
def list_pending_kyc(
    db: Session = Depends(get_db),
    admin_key: str = Depends(get_admin_key)
):
    """Get all pending KYC submissions with user details."""
    pending = db.query(KYCVerification).filter(
        KYCVerification.status == "pending"
    ).all()

    result = []
    for k in pending:
        user = db.query(User).filter(User.id == k.user_id).first()
        result.append({
            "kyc_id": str(k.id),
            "user_id": str(k.user_id),
            "user_name": user.full_name if user else "Unknown",
            "user_email": user.email if user else "Unknown",
            "user_country": user.country if user else "Unknown",
            "document_type": k.document_type,
            "document_number": k.document_number,
            "document_country": k.document_country,
            "front_image_path": k.front_image_path,
            "status": k.status,
            "submitted_at": (
                k.submitted_at.isoformat() if k.submitted_at else None
            ),
        })

    return {"total": len(result), "submissions": result}


@router.get("/kyc/all")
def list_all_kyc(
    db: Session = Depends(get_db),
    admin_key: str = Depends(get_admin_key)
):
    """Get all KYC submissions regardless of status."""
    all_kyc = db.query(KYCVerification).order_by(
        KYCVerification.submitted_at.desc()
    ).all()

    result = []
    for k in all_kyc:
        user = db.query(User).filter(User.id == k.user_id).first()
        result.append({
            "kyc_id": str(k.id),
            "user_id": str(k.user_id),
            "user_name": user.full_name if user else "Unknown",
            "user_email": user.email if user else "Unknown",
            "document_type": k.document_type,
            "document_number": k.document_number,
            "document_country": k.document_country,
            "front_image_path": k.front_image_path,
            "status": k.status,
            "rejection_reason": k.rejection_reason,
            "submitted_at": (
                k.submitted_at.isoformat() if k.submitted_at else None
            ),
            "reviewed_at": (
                k.reviewed_at.isoformat() if k.reviewed_at else None
            ),
        })

    return {"total": len(result), "submissions": result}


@router.post("/kyc/{user_id}/review")
def review_kyc(
    user_id: str,
    action: str,
    reason: str = None,
    db: Session = Depends(get_db),
    mongo_db=Depends(get_mongo_db),
    admin_key: str = Depends(get_admin_key)
):
    """Approve or reject a user KYC. action = approve or reject"""
    from app.services.kyc_service import admin_review_kyc
    result = admin_review_kyc(db, user_id, action, reason)
    log_admin_action(
        mongo_db,
        "admin",
        f"kyc_{action}",
        {"user_id": user_id, "reason": reason}
    )
    return result


@router.get("/audit-logs")
def get_audit_logs(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin_key: str = Depends(get_admin_key)
):
    """Get platform audit logs."""
    from app.models.security import AuditLog
    total = db.query(AuditLog).count()
    logs = db.query(AuditLog).order_by(
        AuditLog.created_at.desc()
    ).limit(limit).offset(offset).all()

    return {
        "total": total,
        "logs": [
            {
                "id": str(log.id),
                "user_id": log.user_id,
                "ip_address": log.ip_address,
                "action": log.action,
                "resource": log.resource,
                "details": log.details,
                "risk_level": log.risk_level,
                "created_at": (
                    log.created_at.isoformat() if log.created_at else None
                ),
            }
            for log in logs
        ]
    }


@router.get("/health")
def admin_health(admin_key: str = Depends(get_admin_key)):
    return {"status": "admin panel operational"}


@router.post("/refresh-bank-cache")
def refresh_bank_cache(
    country: str = "NG",
    admin_key: str = Depends(get_admin_key)
):
    """Force refresh the bank list cache."""
    from app.services.account_verification_service import (
        clear_bank_cache,
        get_all_banks
    )
    clear_bank_cache()
    banks = get_all_banks(country)
    return {
        "message": f"Bank cache refreshed for {country}",
        "total_banks": len(banks),
        "sample": [b["name"] for b in banks[:5]]
    }