"""
Pydantic schemas — define the exact shape of API input/output.

Why separate from the SQLAlchemy model:
- Never return the ORM model directly. `UserOut` deliberately excludes
  `hashed_password` so it can never leak through an endpoint, even if a
  developer later does something careless like `return user`.
"""

import uuid
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


def _normalize_email(v):
    """
    Lowercase and trim before anything else looks at the value.

    EmailStr does not do this. Without it, Alice@example.com and
    alice@example.com are two different rows, and the duplicate check in
    create_user() misses the collision entirely.
    """
    return v.strip().lower() if isinstance(v, str) else v


def _normalize_country(v):
    """
    Accept a 2-letter ISO 3166-1 alpha-2 code in any case.

    Runs in "before" mode so it fires ahead of the max_length constraint,
    which lets a caller sending a full country name get a message that
    explains the format instead of "String should have at most 2 characters".
    """
    if v is None or v == "":
        return None
    v = str(v).strip().upper()
    if len(v) != 2 or not v.isalpha():
        raise ValueError(
            "country must be a 2-letter ISO 3166-1 alpha-2 code, "
            "e.g. NG for Nigeria"
        )
    return v


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=100)
    country: Optional[str] = Field(None, max_length=2)
    phone_number: Optional[str] = None

    _norm_email = field_validator("email", mode="before")(_normalize_email)
    _norm_country = field_validator("country", mode="before")(_normalize_country)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    # Must match UserCreate exactly, or an account registered as
    # Alice@example.com can never be logged into.
    _norm_email = field_validator("email", mode="before")(_normalize_email)


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone_number: Optional[str] = None
    country: Optional[str] = Field(None, max_length=2)
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    business_type: Optional[str] = None

    _norm_country = field_validator("country", mode="before")(_normalize_country)

    @field_validator("business_type")
    @classmethod
    def validate_business_type(cls, v):
        allowed = {"freelancer", "kdp_author", "creator", "other"}
        if v and v not in allowed:
            raise ValueError(f"business_type must be one of {allowed}")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    country: Optional[str]
    phone_number: Optional[str]
    date_of_birth: Optional[date]
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    business_type: Optional[str]
    is_active: bool
    is_kyc_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshRequest(BaseModel):
    refresh_token: str