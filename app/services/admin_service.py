"""
Admin analytics service.
Reads from PostgreSQL for real financial data.
Writes aggregated stats to MongoDB for fast dashboard queries.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.models.user import User
from app.models.wallet import Wallet, Transaction
from app.models.withdrawal import Withdrawal
from app.models.fx import FXConversion
from app.core.mongodb import get_admin_db
import logging

logger = logging.getLogger("fintech.admin")


def get_platform_stats(db: Session) -> dict:
    """
    Pull real-time platform statistics from PostgreSQL.
    This is the main admin dashboard data.
    """
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # User stats
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(
        User.is_active == True
    ).scalar() or 0
    kyc_verified = db.query(func.count(User.id)).filter(
        User.is_kyc_verified == True
    ).scalar() or 0
    new_users_today = db.query(func.count(User.id)).filter(
        User.created_at >= today_start
    ).scalar() or 0
    new_users_7d = db.query(func.count(User.id)).filter(
        User.created_at >= seven_days_ago
    ).scalar() or 0
    new_users_30d = db.query(func.count(User.id)).filter(
        User.created_at >= thirty_days_ago
    ).scalar() or 0

    # Transaction stats
    total_transactions = db.query(func.count(Transaction.id)).scalar() or 0
    total_volume = db.query(
        func.sum(Transaction.amount)
    ).filter(
        Transaction.transaction_type == "credit"
    ).scalar() or Decimal("0")

    volume_30d = db.query(
        func.sum(Transaction.amount)
    ).filter(
        Transaction.transaction_type == "credit",
        Transaction.created_at >= thirty_days_ago
    ).scalar() or Decimal("0")

    # Withdrawal stats
    total_withdrawals = db.query(func.count(Withdrawal.id)).scalar() or 0
    total_withdrawal_volume = db.query(
        func.sum(Withdrawal.amount)
    ).scalar() or Decimal("0")

    completed_withdrawals = db.query(func.count(Withdrawal.id)).filter(
        Withdrawal.status == "completed"
    ).scalar() or 0

    failed_withdrawals = db.query(func.count(Withdrawal.id)).filter(
        Withdrawal.status == "failed"
    ).scalar() or 0

    processing_withdrawals = db.query(func.count(Withdrawal.id)).filter(
        Withdrawal.status == "processing"
    ).scalar() or 0

    # Revenue from fees
    total_fees_collected = db.query(
        func.sum(Withdrawal.fee)
    ).filter(
        Withdrawal.status == "completed"
    ).scalar() or Decimal("0")

    # FX stats
    total_fx_conversions = db.query(func.count(FXConversion.id)).scalar() or 0
    total_fx_volume = db.query(
        func.sum(FXConversion.from_amount)
    ).scalar() or Decimal("0")
    total_fx_revenue = db.query(
        func.sum(FXConversion.fee_usd)
    ).scalar() or Decimal("0")

    # Provider breakdown
    provider_stats = db.query(
        Withdrawal.provider,
        func.count(Withdrawal.id).label("count"),
        func.sum(Withdrawal.amount).label("volume")
    ).group_by(Withdrawal.provider).all()

    # Recent users (last 10)
    recent_users = db.query(User).order_by(
        User.created_at.desc()
    ).limit(10).all()

    # Recent withdrawals (last 10)
    recent_withdrawals = db.query(Withdrawal).order_by(
        Withdrawal.created_at.desc()
    ).limit(10).all()

    # Business type breakdown
    business_breakdown = db.query(
        User.business_type,
        func.count(User.id).label("count")
    ).group_by(User.business_type).all()

    # Country breakdown
    country_breakdown = db.query(
        User.country,
        func.count(User.id).label("count")
    ).group_by(User.country).order_by(
        func.count(User.id).desc()
    ).limit(10).all()

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "kyc_verified": kyc_verified,
            "new_today": new_users_today,
            "new_7d": new_users_7d,
            "new_30d": new_users_30d,
            "kyc_rate": round((kyc_verified / total_users * 100), 1) if total_users > 0 else 0,
        },
        "transactions": {
            "total": total_transactions,
            "total_volume": float(total_volume),
            "volume_30d": float(volume_30d),
        },
        "withdrawals": {
            "total": total_withdrawals,
            "total_volume": float(total_withdrawal_volume),
            "completed": completed_withdrawals,
            "failed": failed_withdrawals,
            "processing": processing_withdrawals,
            "success_rate": round(
                (completed_withdrawals / total_withdrawals * 100), 1
            ) if total_withdrawals > 0 else 0,
        },
        "revenue": {
            "total_fees": float(total_fees_collected),
            "fx_revenue": float(total_fx_revenue),
            "total_revenue": float(total_fees_collected + total_fx_revenue),
        },
        "fx": {
            "total_conversions": total_fx_conversions,
            "total_volume": float(total_fx_volume),
        },
        "providers": [
            {
                "provider": p.provider,
                "count": p.count,
                "volume": float(p.volume or 0)
            }
            for p in provider_stats
        ],
        "business_breakdown": [
            {
                "type": b.business_type or "not_set",
                "count": b.count
            }
            for b in business_breakdown
        ],
        "country_breakdown": [
            {
                "country": c.country or "unknown",
                "count": c.count
            }
            for c in country_breakdown
        ],
        "recent_users": [
            {
                "id": str(u.id),
                "full_name": u.full_name,
                "email": u.email,
                "country": u.country,
                "business_type": u.business_type,
                "is_kyc_verified": u.is_kyc_verified,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in recent_users
        ],
        "recent_withdrawals": [
            {
                "id": str(w.id),
                "amount": float(w.amount),
                "fee": float(w.fee),
                "provider": w.provider,
                "status": w.status,
                "destination_country": w.destination_country,
                "created_at": w.created_at.isoformat() if w.created_at else None,
            }
            for w in recent_withdrawals
        ],
        "generated_at": now.isoformat(),
    }


def log_admin_action(
    mongo_db,
    admin_email: str,
    action: str,
    details: dict = None
):
    """
    Log every admin action to MongoDB for audit trail.
    """
    if mongo_db is None:
        return
    try:
        mongo_db.admin_audit_log.insert_one({
            "admin_email": admin_email,
            "action": action,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.error(f"Failed to log admin action: {e}")


def get_all_users(db: Session, limit: int = 50, offset: int = 0) -> dict:
    """Get paginated list of all users for admin."""
    total = db.query(func.count(User.id)).scalar() or 0
    users = db.query(User).order_by(
        User.created_at.desc()
    ).limit(limit).offset(offset).all()

    return {
        "total": total,
        "users": [
            {
                "id": str(u.id),
                "full_name": u.full_name,
                "email": u.email,
                "country": u.country,
                "phone_number": u.phone_number,
                "business_type": u.business_type,
                "is_active": u.is_active,
                "is_kyc_verified": u.is_kyc_verified,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ]
    }


def get_all_withdrawals(db: Session, limit: int = 50, offset: int = 0) -> dict:
    """Get paginated list of all withdrawals for admin."""
    total = db.query(func.count(Withdrawal.id)).scalar() or 0
    withdrawals = db.query(Withdrawal).order_by(
        Withdrawal.created_at.desc()
    ).limit(limit).offset(offset).all()

    return {
        "total": total,
        "withdrawals": [
            {
                "id": str(w.id),
                "user_id": str(w.user_id),
                "amount": float(w.amount),
                "fee": float(w.fee),
                "amount_after_fee": float(w.amount_after_fee),
                "provider": w.provider,
                "status": w.status,
                "bank_name": w.bank_name,
                "account_number": w.account_number,
                "account_name": w.account_name,
                "destination_country": w.destination_country,
                "reference": w.reference,
                "created_at": w.created_at.isoformat() if w.created_at else None,
            }
            for w in withdrawals
        ]
    }


def suspend_user(db: Session, user_id: str, reason: str = None) -> dict:
    """Suspend a user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "message": "User not found"}
    user.is_active = False
    db.commit()
    return {"success": True, "message": f"User {user.email} suspended"}


def reactivate_user(db: Session, user_id: str) -> dict:
    """Reactivate a suspended user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "message": "User not found"}
    user.is_active = True
    db.commit()
    return {"success": True, "message": f"User {user.email} reactivated"}


def verify_user_kyc(db: Session, user_id: str) -> dict:
    """Manually approve a user's KYC."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "message": "User not found"}
    user.is_kyc_verified = True
    db.commit()
    return {"success": True, "message": f"KYC approved for {user.email}"}