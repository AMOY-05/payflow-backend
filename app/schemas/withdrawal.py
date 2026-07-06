import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class BankDetails(BaseModel):
    bank_name: str = Field(..., min_length=2, description="Name of the bank")
    account_number: str = Field(..., min_length=6, description="Bank account number")
    account_name: str = Field(..., min_length=2, description="Account holder full name")
    bank_code: Optional[str] = None   # required for Nigerian banks (e.g. 058 for GTBank)
    destination_country: str = Field(..., min_length=2, max_length=2)
    destination_currency: str = Field(..., min_length=3, max_length=3)


class WithdrawalRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Amount in USD to withdraw")
    bank_details: BankDetails
    urgent: bool = False
    preferred_provider: Optional[str] = None
    narration: Optional[str] = None


class WithdrawalOut(BaseModel):
    id: uuid.UUID
    amount: Decimal
    fee: Decimal
    amount_after_fee: Decimal
    currency: str
    provider: str
    method: str
    estimated_delivery: str
    bank_name: str
    account_number: str
    account_name: str
    destination_country: str
    destination_currency: str
    reference: str
    status: str
    status_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class WithdrawalListOut(BaseModel):
    total: int
    withdrawals: List[WithdrawalOut]


class WithdrawalReceiptOut(BaseModel):
    reference: str
    status: str
    amount: Decimal
    fee: Decimal
    amount_after_fee: Decimal
    currency: str
    provider: str
    estimated_delivery: str
    delivery_note: str
    bank_name: str
    account_number: str
    account_name: str
    destination_country: str
    destination_currency: str
    created_at: datetime
    message: str