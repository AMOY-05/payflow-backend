"""
Rate limiting to prevent abuse.

Why rate limiting matters in fintech:
- Prevents brute force attacks on login
- Prevents someone from hammering the withdrawal endpoint
- Protects your provider API quotas (Flutterwave charges per call)
- Required by most payment compliance frameworks
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"]
)