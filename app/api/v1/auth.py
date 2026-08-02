from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.config import settings
from app.core.security import (
    create_access_token, create_refresh_token,
    decode_token, hash_password
)
from app.schemas.user import (
    UserCreate, UserOut, UserLogin,
    Token, TokenRefreshRequest
)
from app.services.auth_service import create_user, authenticate_user
from app.services.security_service import (
    record_login_attempt,
    check_account_lockout,
    blacklist_token,
    log_audit_event
)
from app.api.v1.deps import get_current_user
from app.models.user import User
import logging

logger = logging.getLogger("fintech.auth")
router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


def get_client_ip(request: Request) -> str:
    """Get real client IP accounting for proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED
)
@limiter.limit(f"{settings.AUTH_RATE_LIMIT_PER_MINUTE}/minute")
def register(
    request: Request,
    user_in: UserCreate,
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    user = create_user(db, user_in)

    log_audit_event(
        db,
        action="user_registered",
        user_id=str(user.id),
        ip_address=ip,
        details={"email": user.email, "country": user.country},
        risk_level="low"
    )
    return user


@router.post("/login", response_model=Token)
@limiter.limit(f"{settings.AUTH_RATE_LIMIT_PER_MINUTE}/minute")
def login(
    request: Request,
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")

    # Check lockout before attempting auth
    check_account_lockout(db, credentials.email, ip)

    try:
        user = authenticate_user(db, credentials.email, credentials.password)
    except HTTPException as e:
        # Record failed attempt
        record_login_attempt(db, credentials.email, ip, False, user_agent)
        raise e

    # Record successful login
    record_login_attempt(db, credentials.email, ip, True, user_agent)

    log_audit_event(
        db,
        action="user_login",
        user_id=str(user.id),
        ip_address=ip,
        details={"email": user.email},
        risk_level="low"
    )

    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout")
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout and blacklist the current access token.
    After this the token cannot be used even if it has not expired.
    """
    from datetime import timezone
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    payload = decode_token(token)

    if payload:
        jti = payload.get("jti") or token[-16:]
        exp = payload.get("exp")
        expires_at = None
        if exp:
            from datetime import datetime
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)

        if expires_at:
            blacklist_token(
                db,
                token_jti=jti,
                user_id=str(current_user.id),
                expires_at=expires_at,
                reason="user_logout"
            )

    ip = get_client_ip(request)
    log_audit_event(
        db,
        action="user_logout",
        user_id=str(current_user.id),
        ip_address=ip,
        risk_level="low"
    )

    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=Token)
@limiter.limit("10/minute")
def refresh_token(
    request: Request,
    payload: TokenRefreshRequest,
    db: Session = Depends(get_db)
):
    data = decode_token(payload.refresh_token)
    if data is None or data.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )
    user_id = data.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        )
    new_access_token = create_access_token(subject=str(user.id))
    new_refresh_token = create_refresh_token(subject=str(user.id))
    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token
    )


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/security-summary")
def security_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get security overview for the current user."""
    from app.services.security_service import get_security_summary
    return get_security_summary(db, str(current_user.id))


from pydantic import BaseModel as PydanticBaseModel

class ForgotPasswordRequest(PydanticBaseModel):
    email: str

class ResetPasswordRequest(PydanticBaseModel):
    token: str
    new_password: str


@router.post("/forgot-password")
@limiter.limit("3/minute")
def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Send password reset email.
    Always returns success even if email not found
    (prevents email enumeration attacks).
    """
    from app.services.email_service import send_password_reset_email
    from app.core.sanitize import sanitize_email

    email = sanitize_email(data.email)
    user = db.query(User).filter(User.email == email).first()

    if user and user.is_active and not user.is_deleted:
        try:
            send_password_reset_email(db, user)
            log_audit_event(
                db,
                action="password_reset_requested",
                user_id=str(user.id),
                ip_address=get_client_ip(request),
                risk_level="medium"
            )
        except Exception as e:
            logger.error(f"Password reset email failed: {e}")

    # Always return same message to prevent email enumeration
    return {
        "message": (
            "If an account exists with that email, "
            "you will receive a reset link within 2 minutes. "
            "Please also check your spam folder."
        )
    }


@router.post("/reset-password")
def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Reset password using token from email."""
    from app.services.email_service import complete_password_reset

    result = complete_password_reset(db, data.token, data.new_password)

    log_audit_event(
        db,
        action="password_reset_completed",
        ip_address=get_client_ip(request),
        risk_level="medium"
    )

    return result


@router.get("/verify-reset-token")
def verify_reset_token(
    token: str,
    db: Session = Depends(get_db)
):
    """Check if a reset token is valid before showing the form."""
    from app.services.email_service import verify_password_reset_token
    try:
        user, _ = verify_password_reset_token(db, token)
        return {
            "valid": True,
            "email": user.email[:3] + "***" + user.email[user.email.index("@"):]
        }
    except HTTPException:
        return {"valid": False}