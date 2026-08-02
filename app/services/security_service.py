"""
Security service — handles account lockout, audit logging,
suspicious activity detection, and token blacklisting.
"""

import json
import secrets
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, Request, status

from app.models.security import LoginAttempt, TokenBlacklist, AuditLog
from app.models.user import User
from app.core.config import settings

logger = logging.getLogger("fintech.security")

# Security configuration
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
SUSPICIOUS_COUNTRIES = []  # Add country codes to flag if needed


def record_login_attempt(
    db: Session,
    email: str,
    ip_address: str,
    success: bool,
    user_agent: str = None
):
    """Record every login attempt for security monitoring."""
    attempt = LoginAttempt(
        email=email,
        ip_address=ip_address,
        success=success,
        user_agent=user_agent
    )
    db.add(attempt)
    db.commit()

    if not success:
        logger.warning(
            f"Failed login attempt for {email} from {ip_address}"
        )


def check_account_lockout(db: Session, email: str, ip_address: str):
    """
    Check if account or IP is locked out due to too many failed attempts.
    Raises HTTPException if locked out.
    """
    lockout_window = datetime.now(timezone.utc) - timedelta(
        minutes=LOCKOUT_DURATION_MINUTES
    )

    # Count failed attempts in lockout window for this email
    failed_attempts = db.query(LoginAttempt).filter(
        LoginAttempt.email == email,
        LoginAttempt.success == False,
        LoginAttempt.created_at >= lockout_window
    ).count()

    if failed_attempts >= MAX_LOGIN_ATTEMPTS:
        logger.warning(
            f"Account locked: {email} from {ip_address} "
            f"({failed_attempts} failed attempts)"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Account temporarily locked due to {failed_attempts} "
                f"failed login attempts. "
                f"Please try again in {LOCKOUT_DURATION_MINUTES} minutes "
                f"or reset your password."
            )
        )

    # Also check for brute force from same IP
    ip_attempts = db.query(LoginAttempt).filter(
        LoginAttempt.ip_address == ip_address,
        LoginAttempt.success == False,
        LoginAttempt.created_at >= lockout_window
    ).count()

    if ip_attempts >= MAX_LOGIN_ATTEMPTS * 2:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many failed attempts from your network. "
                f"Please try again in {LOCKOUT_DURATION_MINUTES} minutes."
            )
        )


def blacklist_token(
    db: Session,
    token_jti: str,
    user_id: str,
    expires_at: datetime,
    reason: str = "logout"
):
    """Add a JWT token to the blacklist so it cannot be reused."""
    blacklisted = TokenBlacklist(
        token_jti=token_jti,
        user_id=user_id,
        expires_at=expires_at,
        reason=reason
    )
    db.add(blacklisted)
    db.commit()
    logger.info(f"Token blacklisted for user {user_id}: {reason}")


def is_token_blacklisted(db: Session, token_jti: str) -> bool:
    """Check if a token has been blacklisted."""
    return db.query(TokenBlacklist).filter(
        TokenBlacklist.token_jti == token_jti
    ).first() is not None


def log_audit_event(
    db: Session,
    action: str,
    user_id: str = None,
    ip_address: str = None,
    resource: str = None,
    details: dict = None,
    risk_level: str = "low"
):
    """
    Log security-relevant events for compliance and audit trail.

    Risk levels: low, medium, high, critical
    """
    log = AuditLog(
        user_id=user_id,
        ip_address=ip_address,
        action=action,
        resource=resource,
        details=json.dumps(details) if details else None,
        risk_level=risk_level
    )
    db.add(log)
    db.commit()

    if risk_level in ["high", "critical"]:
        logger.warning(
            f"HIGH RISK EVENT: {action} | "
            f"User: {user_id} | "
            f"IP: {ip_address} | "
            f"Details: {details}"
        )


def detect_suspicious_activity(
    db: Session,
    user: User,
    action: str,
    ip_address: str,
    amount: float = None
) -> dict:
    """
    Detect potentially suspicious activity and flag it.
    Returns a dict with is_suspicious flag and reason.
    """
    flags = []

    # Large withdrawal detection
    if action == "withdrawal" and amount:
        if amount > 5000:
            flags.append(f"Large withdrawal: ${amount}")
        if amount > 10000:
            log_audit_event(
                db,
                action="large_withdrawal_attempt",
                user_id=str(user.id),
                ip_address=ip_address,
                details={"amount": amount},
                risk_level="high"
            )

    # Multiple rapid withdrawals
    if action == "withdrawal":
        from app.models.withdrawal import Withdrawal
        recent_withdrawals = db.query(Withdrawal).filter(
            Withdrawal.user_id == user.id,
            Withdrawal.created_at >= datetime.now(timezone.utc) - timedelta(hours=1)
        ).count()

        if recent_withdrawals >= 3:
            flags.append(
                f"Multiple withdrawals in 1 hour: {recent_withdrawals}"
            )
            log_audit_event(
                db,
                action="rapid_withdrawals",
                user_id=str(user.id),
                ip_address=ip_address,
                details={"count": recent_withdrawals, "hours": 1},
                risk_level="medium"
            )

    # Withdrawal without KYC exceeding limit
    if action == "withdrawal" and amount and not user.is_kyc_verified:
        if amount > 500:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Withdrawals above $500 require KYC verification. "
                    "Please complete your identity verification in the "
                    "KYC section before proceeding."
                )
            )

    return {
        "is_suspicious": len(flags) > 0,
        "flags": flags
    }


def cleanup_expired_blacklist(db: Session):
    """Remove expired tokens from blacklist to keep the table small."""
    db.query(TokenBlacklist).filter(
        TokenBlacklist.expires_at < datetime.now(timezone.utc)
    ).delete()
    db.commit()


def get_security_summary(db: Session, user_id: str) -> dict:
    """Get security summary for a user."""
    recent_logins = db.query(LoginAttempt).filter(
        LoginAttempt.email.in_(
            db.query(User.email).filter(User.id == user_id)
        )
    ).order_by(
        LoginAttempt.created_at.desc()
    ).limit(5).all()

    failed_last_24h = db.query(LoginAttempt).filter(
        LoginAttempt.email.in_(
            db.query(User.email).filter(User.id == user_id)
        ),
        LoginAttempt.success == False,
        LoginAttempt.created_at >= datetime.now(timezone.utc) - timedelta(hours=24)
    ).count()

    return {
        "failed_logins_24h": failed_last_24h,
        "recent_login_ips": list(set(
            a.ip_address for a in recent_logins
        )),
        "account_locked": failed_last_24h >= MAX_LOGIN_ATTEMPTS,
    }