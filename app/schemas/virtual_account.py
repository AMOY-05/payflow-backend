import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class VirtualAccountOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    account_number: str
    routing_number: str
    account_name: str
    bank_name: str
    account_type: str
    currency: str
    provider: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class VirtualAccountDetailOut(BaseModel):
    """
    Full details shown to user so they can share with
    Amazon KDP, Upwork, Fiverr, clients etc.
    """
    account_number: str
    routing_number: str
    account_name: str
    bank_name: str
    account_type: str
    currency: str
    swift_code: str = "LDBKUS44"   # Lead Bank's SWIFT code (for international wires)
    bank_address: str = "1801 Main Street, Kansas City, MO 64108, USA"

    # Instructions for common platforms
    how_to_use: dict

    class Config:
        from_attributes = True