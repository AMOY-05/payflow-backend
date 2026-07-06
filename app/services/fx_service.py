import uuid
import httpx
from decimal import Decimal, ROUND_DOWN
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.fx import FXConversion
from app.models.wallet import Wallet, Transaction
from app.models.user import User


# ---------------------------------------------------------------------------
# Mock rates — realistic as of mid 2026
# Replace with live API call in Phase 9
# ---------------------------------------------------------------------------

MOCK_INTERBANK_RATES = {
    # 1 USD = X local currency (interbank/mid-market rate)
    "NGN": Decimal("1595.00"),   # Nigerian Naira
    "GHS": Decimal("15.80"),     # Ghanaian Cedi
    "KES": Decimal("129.50"),    # Kenyan Shilling
    "ZAR": Decimal("18.60"),     # South African Rand
    "UGX": Decimal("3720.00"),   # Ugandan Shilling
    "TZS": Decimal("2650.00"),   # Tanzanian Shilling
    "RWF": Decimal("1385.00"),   # Rwandan Franc
    "ETB": Decimal("57.50"),     # Ethiopian Birr
    "XOF": Decimal("615.00"),    # West African CFA (Senegal, Ivory Coast)
    "GBP": Decimal("0.79"),      # British Pound
    "EUR": Decimal("0.93"),      # Euro
    "CAD": Decimal("1.37"),      # Canadian Dollar
}

CURRENCY_SYMBOLS = {
    "NGN": "₦",
    "GHS": "GH₵",
    "KES": "KSh",
    "ZAR": "R",
    "UGX": "USh",
    "TZS": "TSh",
    "RWF": "FRw",
    "ETB": "Br",
    "XOF": "CFA",
    "GBP": "£",
    "EUR": "€",
    "CAD": "C$",
    "USD": "$",
}

CURRENCY_NAMES = {
    "NGN": "Nigerian Naira",
    "GHS": "Ghanaian Cedi",
    "KES": "Kenyan Shilling",
    "ZAR": "South African Rand",
    "UGX": "Ugandan Shilling",
    "TZS": "Tanzanian Shilling",
    "RWF": "Rwandan Franc",
    "ETB": "Ethiopian Birr",
    "XOF": "West African CFA Franc",
    "GBP": "British Pound",
    "EUR": "Euro",
    "CAD": "Canadian Dollar",
    "USD": "US Dollar",
}


def get_interbank_rate(to_currency: str) -> Decimal:
    """
    Get live exchange rate.
    Always tries live API first, falls back to mock if it fails.
    """
    currency = to_currency.upper()

    if currency not in MOCK_INTERBANK_RATES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Currency {currency} is not supported yet."
        )

    # Always try live rate first
    try:
        from app.providers.fx_provider import get_live_rate
        live_rate = get_live_rate(currency)
        if live_rate and live_rate > Decimal("0"):
            return live_rate
    except Exception:
        pass

    # Fall back to mock
    return MOCK_INTERBANK_RATES[currency]


def apply_spread(interbank_rate: Decimal, spread_percent: float) -> Decimal:
    """
    Apply platform spread to the interbank rate.

    Example:
    Interbank rate: 1595 NGN per USD
    Spread: 1.5%
    Platform rate: 1595 × (1 - 0.015) = 1571.075 NGN per USD

    The user gets LESS NGN per dollar — that difference is your revenue.
    """
    spread = Decimal(str(spread_percent)) / Decimal("100")
    platform_rate = interbank_rate * (Decimal("1") - spread)
    return platform_rate.quantize(Decimal("0.0001"))


# Add this at the top of the file after CURRENCY_NAMES dict
SUPPORTED_CURRENCIES = list(MOCK_INTERBANK_RATES.keys())


def get_fx_quote(
    from_amount: Decimal,
    to_currency: str,
    from_currency: str = "USD"
) -> dict:
    """
    Get a conversion quote before executing.
    Returns clear error with full currency list if currency is invalid.
    """
    if from_currency != "USD":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Currently only USD as source currency is supported."
        )

    to_currency = to_currency.upper()

    # Validate currency and return helpful error with full list
    if to_currency not in MOCK_INTERBANK_RATES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid currency",
                "message": (
                    f"'{to_currency}' is not a supported currency. "
                    f"Please select from the list below."
                ),
                "supported_currencies": [
                    {
                        "code": code,
                        "name": CURRENCY_NAMES[code],
                        "symbol": CURRENCY_SYMBOLS[code]
                    }
                    for code in MOCK_INTERBANK_RATES.keys()
                ]
            }
        )

    interbank_rate = get_interbank_rate(to_currency)
    platform_rate = apply_spread(interbank_rate, settings.FX_SPREAD_PERCENT)
    to_amount = (from_amount * platform_rate).quantize(Decimal("0.01"))
    spread_amount = from_amount * (Decimal(str(settings.FX_SPREAD_PERCENT)) / 100)
    fee_usd = spread_amount.quantize(Decimal("0.01"))

    return {
        "from_currency": from_currency,
        "from_amount": from_amount,
        "to_currency": to_currency,
        "to_amount": to_amount,
        "interbank_rate": interbank_rate,
        "platform_rate": platform_rate,
        "spread_percent": Decimal(str(settings.FX_SPREAD_PERCENT)),
        "fee_usd": fee_usd,
        "currency_symbol": CURRENCY_SYMBOLS.get(to_currency, ""),
        "currency_name": CURRENCY_NAMES.get(to_currency, to_currency),
        "rate_note": (
            f"Mid-market rate: 1 USD = {interbank_rate} {to_currency}. "
            f"Your rate includes a {settings.FX_SPREAD_PERCENT}% platform fee."
        )
    }


def execute_fx_conversion(
    db: Session,
    user: User,
    from_amount: Decimal,
    to_currency: str
) -> dict:
    """
    Execute the actual FX conversion:
    1. Verify user has enough balance
    2. Debit USD from wallet
    3. Record FX conversion
    4. Return converted amount details
    """
    to_currency = to_currency.upper()

    # Get quote first
    quote = get_fx_quote(from_amount, to_currency)

    # Check wallet balance
    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found."
        )

    if wallet.balance < from_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Insufficient balance. "
                f"You have ${wallet.balance} but tried to convert ${from_amount}."
            )
        )

    balance_before = wallet.balance
    balance_after = balance_before - from_amount

    # Debit wallet
    wallet.balance = balance_after
    db.add(wallet)

    # Create transaction record
    reference = f"FX-{uuid.uuid4().hex.upper()[:16]}"
    transaction = Transaction(
        wallet_id=wallet.id,
        transaction_type="debit",
        amount=from_amount,
        balance_before=balance_before,
        balance_after=balance_after,
        category="fx_conversion",
        description=(
            f"FX conversion: ${from_amount} USD → "
            f"{quote['currency_symbol']}{quote['to_amount']} {to_currency}"
        ),
        reference=reference,
        status="success"
    )
    db.add(transaction)

    # Record FX conversion details
    fx_record = FXConversion(
        user_id=user.id,
        wallet_id=wallet.id,
        from_currency="USD",
        from_amount=from_amount,
        to_currency=to_currency,
        to_amount=quote["to_amount"],
        interbank_rate=quote["interbank_rate"],
        platform_rate=quote["platform_rate"],
        spread_percent=quote["spread_percent"],
        fee_usd=quote["fee_usd"],
        transaction_reference=reference,
        status="completed"
    )
    db.add(fx_record)
    db.commit()

    return {
        "status": "completed",
        "reference": reference,
        "from_currency": "USD",
        "from_amount": from_amount,
        "to_currency": to_currency,
        "to_amount": quote["to_amount"],
        "platform_rate": quote["platform_rate"],
        "fee_usd": quote["fee_usd"],
        "currency_symbol": quote["currency_symbol"],
        "new_wallet_balance": balance_after,
        "message": (
            f"Successfully converted ${from_amount} USD to "
            f"{quote['currency_symbol']}{quote['to_amount']} {to_currency}"
        )
    }


def get_supported_currencies() -> list:
    """Return all supported currencies with their details."""
    return [
        {
            "code": code,
            "name": CURRENCY_NAMES[code],
            "symbol": CURRENCY_SYMBOLS[code],
            "mock_rate": str(rate),
        }
        for code, rate in MOCK_INTERBANK_RATES.items()
    ]