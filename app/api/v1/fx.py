from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.schemas.fx import (
    FXQuoteRequest, FXQuoteResponse,
    FXConvertRequest, FXConvertResponse,
    SupportedCurrency
)
from app.services.fx_service import (
    get_fx_quote,
    execute_fx_conversion,
    get_supported_currencies
)
from typing import List

router = APIRouter(prefix="/api/v1/fx", tags=["FX Conversion"])


@router.get("/currencies", response_model=List[SupportedCurrency])
def list_supported_currencies():
    """
    Get all supported currencies with their current mock rates.
    No auth required — public endpoint for the frontend.
    """
    return get_supported_currencies()


@router.post("/quote", response_model=FXQuoteResponse)
def get_quote(
    data: FXQuoteRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Get a conversion quote before executing.
    Show this to the user so they see exactly what they will get.
    No money moves at this step.
    """
    return get_fx_quote(
        from_amount=data.from_amount,
        to_currency=data.to_currency
    )


@router.post("/convert", response_model=FXConvertResponse)
def convert_currency(
    data: FXConvertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Execute the FX conversion.
    Debits USD wallet and records the converted amount.
    User confirms this after seeing the quote.
    """
    return execute_fx_conversion(
        db=db,
        user=current_user,
        from_amount=data.from_amount,
        to_currency=data.to_currency
    )

@router.get("/supported-currencies")
def get_supported_currencies():
    """
    Get all supported currencies with live rates for the frontend dropdown.
    No auth required — public endpoint.
    """
    from app.services.fx_service import MOCK_INTERBANK_RATES, CURRENCY_NAMES, CURRENCY_SYMBOLS
    from app.providers.fx_provider import get_live_rate

    return {
        "total": len(MOCK_INTERBANK_RATES),
        "currencies": [
            {
                "code": code,
                "name": CURRENCY_NAMES.get(code, code),
                "symbol": CURRENCY_SYMBOLS.get(code, ""),
                "indicative_rate": str(get_live_rate(code))
            }
            for code in MOCK_INTERBANK_RATES.keys()
        ]
    }