"""
Bank list endpoint.
Frontend uses this to populate the bank dropdown
so users don't have to type bank codes manually.
"""

from fastapi import APIRouter, HTTPException, status
from app.providers.flutterwave import FlutterwaveProvider

router = APIRouter(prefix="/api/v1/banks", tags=["Banks"])

# Only African countries we support
SUPPORTED_COUNTRIES = {
    "NG": "Nigeria",
    "GH": "Ghana",
    "KE": "Kenya",
    "ZA": "South Africa",
    "UG": "Uganda",
    "TZ": "Tanzania",
    "RW": "Rwanda",
    "ZM": "Zambia",
    "CM": "Cameroon",
    "CI": "Ivory Coast",
    "SN": "Senegal",
    "ET": "Ethiopia",
}


@router.get("/supported-countries")
def get_supported_countries():
    """
    Get the list of all countries we currently support.
    Show this as a dropdown on the frontend.
    """
    return {
        "total": len(SUPPORTED_COUNTRIES),
        "countries": [
            {"code": code, "name": name}
            for code, name in SUPPORTED_COUNTRIES.items()
        ]
    }

@router.get("/{country}")
def get_banks(country: str):
    country_upper = country.upper()

    if country_upper not in SUPPORTED_COUNTRIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Country not supported",
                "supported_countries": list(SUPPORTED_COUNTRIES.keys())
            }
        )

    from app.services.account_verification_service import get_all_banks
    banks = get_all_banks(country_upper)

    return {
        "country": country_upper,
        "country_name": SUPPORTED_COUNTRIES[country_upper],
        "total": len(banks),
        "source": "paystack_live",
        "banks": banks
    }