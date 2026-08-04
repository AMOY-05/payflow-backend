"""
Security primitives: password hashing + JWT issuance/verification.

Fintech-specific notes:
- We use bcrypt (via passlib) — industry standard, slow-by-design to resist
  brute force, unlike fast hashes like SHA-256.
- We issue short-lived ACCESS tokens (30 min) + longer-lived REFRESH tokens
  (7 days), a standard pattern that limits the damage window if an access
  token is leaked (e.g. via XSS), without forcing re-login every 30 minutes.
- Tokens carry a "type" claim (access/refresh) so a refresh token can never
  be used directly to access protected endpoints — a common vulnerability
  if this distinction is skipped.
"""

from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets
import string

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash password using bcrypt.
    Truncates to 72 bytes to avoid bcrypt limitation on production.
    """
    # bcrypt has a 72-byte limit — truncate safely
    password_bytes = password.encode("utf-8")[:72]
    password_truncated = password_bytes.decode("utf-8", errors="ignore")
    return pwd_context.hash(password_truncated)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash.
    Must truncate the same way as hash_password.
    """
    password_bytes = plain_password.encode("utf-8")[:72]
    password_truncated = password_bytes.decode("utf-8", errors="ignore")
    return pwd_context.verify(password_truncated, hashed_password)


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    from jose import jwt
    from app.core.config import settings

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    jti = secrets.token_hex(8)
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
        "jti": jti
    }
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )


def create_refresh_token(subject: str) -> str:
    from jose import jwt
    from app.core.config import settings

    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    jti = secrets.token_hex(8)
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "jti": jti
    }
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )


def decode_token(token: str) -> Optional[dict]:
    from jose import jwt, JWTError
    from app.core.config import settings

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def generate_random_password(length: int = 16) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))