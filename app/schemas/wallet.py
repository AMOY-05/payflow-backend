import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class WalletOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    balance: Decimal
    currency: str
    created_at: datetime

    class Config:
        from_attributes = True


class DepositRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Amount must be greater than 0")
    description: Optional[str] = None

    class Config:
        # Allows Decimal values to be passed correctly
        json_encoders = {Decimal: str}


class TransactionOut(BaseModel):
    id: uuid.UUID
    wallet_id: uuid.UUID
    transaction_type: str
    amount: Decimal
    balance_before: Decimal
    balance_after: Decimal
    category: str
    description: Optional[str]
    reference: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionListOut(BaseModel):
    total: int
    transactions: List[TransactionOut]