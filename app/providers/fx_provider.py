"""
Live FX rate provider.
Uses ExchangeRate-API free tier (1,500 requests/month).
Falls back to mock rates if API is unavailable.
Your key: already configured in .env as EXCHANGE_RATE_API_KEY
"""

import httpx
import time
from decimal import Decimal
from app.core.config import settings
from app.services.fx_service import MOCK_INTERBANK_RATES

# In-memory cache — avoids burning free tier quota on every request
_rate_cache: dict = {}
_cache_timestamp: dict = {}
CACHE_TTL_SECONDS = 300  # refresh every 5 minutes


def get_live_rate(to_currency: str) -> Decimal:
    """
    Fetch live exchange rate from ExchangeRate-API.
    Returns cached rate if still fresh (within 5 minutes).
    Falls back to mock rate if API fails or key is missing.
    """
    currency = to_currency.upper()
    now = time.time()

    # Return cached rate if still fresh
    if (
        currency in _rate_cache
        and now - _cache_timestamp.get(currency, 0) < CACHE_TTL_SECONDS
    ):
        return _rate_cache[currency]

    # Try live API
    if settings.EXCHANGE_RATE_API_KEY:
        try:
            response = httpx.get(
                f"https://v6.exchangerate-api.com/v6/"
                f"{settings.EXCHANGE_RATE_API_KEY}/pair/USD/{currency}",
                timeout=5.0
            )
            data = response.json()
            if data.get("result") == "success":
                rate = Decimal(str(data["conversion_rate"]))
                # Store in cache
                _rate_cache[currency] = rate
                _cache_timestamp[currency] = now
                return rate
        except Exception:
            pass  # Fall through to mock

    # Fallback to mock rate
    return MOCK_INTERBANK_RATES.get(currency, Decimal("1.00"))


def get_all_live_rates() -> dict:
    """Get live rates for all supported currencies."""
    currencies = list(MOCK_INTERBANK_RATES.keys())
    return {currency: get_live_rate(currency) for currency in currencies}