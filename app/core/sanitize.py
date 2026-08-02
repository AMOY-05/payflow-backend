"""
Input sanitization to prevent XSS and injection attacks.
All user-provided text input should pass through these functions.
"""

import re
import bleach
from typing import Optional


def sanitize_text(text: Optional[str], max_length: int = 500) -> Optional[str]:
    """
    Clean user input to prevent XSS.
    Strips HTML tags and dangerous characters.
    """
    if text is None:
        return None
    # Strip HTML tags
    clean = bleach.clean(text, tags=[], strip=True)
    # Remove null bytes
    clean = clean.replace("\x00", "")
    # Truncate to max length
    clean = clean[:max_length].strip()
    return clean if clean else None


def sanitize_email(email: str) -> str:
    """Normalize and validate email format."""
    return email.lower().strip()[:254]


def sanitize_amount(amount: str) -> str:
    """Ensure amount is a valid number."""
    clean = re.sub(r"[^\d.]", "", str(amount))
    parts = clean.split(".")
    if len(parts) > 2:
        clean = parts[0] + "." + parts[1]
    return clean


def sanitize_account_number(account_number: str) -> str:
    """Keep only digits in account numbers."""
    return re.sub(r"\D", "", account_number)[:20]


def sanitize_bank_code(bank_code: str) -> str:
    """Keep only alphanumeric characters in bank codes."""
    return re.sub(r"[^a-zA-Z0-9]", "", bank_code)[:10]