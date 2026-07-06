from decimal import Decimal
from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, Field


class FXQuoteRequest(BaseModel):
    from_amount: Decimal = Field(..., gt=0, description="Amount in USD to convert")
    to_currency: str = Field(..., min_length=3, max_length=3, description="Target currency e.g. NGN")


class FXQuoteResponse(BaseModel):
    from_currency: str
    from_amount: Decimal
    to_currency: str
    to_amount: Decimal
    interbank_rate: Decimal
    platform_rate: Decimal
    spread_percent: Decimal
    fee_usd: Decimal
    currency_symbol: str
    currency_name: str
    rate_note: str


class FXConvertRequest(BaseModel):
    from_amount: Decimal = Field(..., gt=0)
    to_currency: str = Field(..., min_length=3, max_length=3)


class FXConvertResponse(BaseModel):
    status: str
    reference: str
    from_currency: str
    from_amount: Decimal
    to_currency: str
    to_amount: Decimal
    platform_rate: Decimal
    fee_usd: Decimal
    currency_symbol: str
    new_wallet_balance: Decimal
    message: str


class SupportedCurrency(BaseModel):
    code: str
    name: str
    symbol: str
    mock_rate: str