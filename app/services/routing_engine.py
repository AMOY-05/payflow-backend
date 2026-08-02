"""
PayFlow Routing Engine

Automatically selects the best payment provider based on:
- Destination country
- Transfer amount
- Urgency
- User preference

Provider names are NEVER exposed to users.
All user-facing labels use PayFlow branding only.
"""

from decimal import Decimal
from typing import Optional
import logging

logger = logging.getLogger("fintech.routing")

# ============================================================
# PROVIDER CONFIGURATION
# Internal use only — never sent to frontend
# ============================================================

PROVIDER_CONFIG = {
    "paystack": {
        "display_name": "PayFlow Transfer",
        "fee_type": "percentage",
        "fee_percent": Decimal("1.5"),
        "fee_cap_ngn": Decimal("2000"),   # Paystack caps at ₦2,000
        "flat_fee": Decimal("0"),
        "min_amount": Decimal("1"),
        "max_amount": Decimal("50000"),
        "countries": ["NG"],
        "delivery": "instant to 30 minutes",
        "supports_fintechs": True,
    },
    "flutterwave": {
        "display_name": "PayFlow Transfer",
        "fee_type": "percentage",
        "fee_percent": Decimal("1.4"),
        "flat_fee": Decimal("1.50"),
        "min_amount": Decimal("1"),
        "max_amount": Decimal("50000"),
        "countries": ["NG", "GH", "KE", "UG", "TZ", "ZA"],
        "delivery": "15 minutes to 2 hours",
        "supports_fintechs": True,
    },
    "chipper_cash": {
        "display_name": "PayFlow Express",
        "fee_type": "percentage",
        "fee_percent": Decimal("1.3"),
        "flat_fee": Decimal("0"),
        "min_amount": Decimal("1"),
        "max_amount": Decimal("500"),
        "countries": ["NG", "GH", "KE", "UG", "TZ", "ZA"],
        "delivery": "instant to 30 minutes",
        "supports_fintechs": True,
    },
    "grey": {
        "display_name": "PayFlow Plus",
        "fee_type": "percentage",
        "fee_percent": Decimal("1.0"),
        "flat_fee": Decimal("0"),
        "min_amount": Decimal("1"),
        "max_amount": Decimal("10000"),
        "countries": ["NG", "KE"],
        "delivery": "1 to 3 hours",
        "supports_fintechs": False,
    },
    "lemfi": {
        "display_name": "PayFlow Plus",
        "fee_type": "percentage",
        "fee_percent": Decimal("1.5"),
        "flat_fee": Decimal("0"),
        "min_amount": Decimal("1"),
        "max_amount": Decimal("5000"),
        "countries": ["NG", "GH", "KE"],
        "delivery": "1 to 2 hours",
        "supports_fintechs": False,
    },
    "wise": {
        "display_name": "PayFlow Global",
        "fee_type": "percentage",
        "fee_percent": Decimal("0.65"),
        "flat_fee": Decimal("0"),
        "min_amount": Decimal("100"),
        "max_amount": Decimal("1000000"),
        "countries": ["NG", "GH", "KE", "ZA", "US"],
        "delivery": "1 to 2 business days",
        "supports_fintechs": False,
    },
    "wire": {
        "display_name": "PayFlow Wire",
        "fee_type": "flat",
        "fee_percent": Decimal("0"),
        "flat_fee": Decimal("25"),
        "min_amount": Decimal("1000"),
        "max_amount": Decimal("10000000"),
        "countries": ["NG", "GH", "KE", "ZA", "US"],
        "delivery": "same business day",
        "supports_fintechs": False,
    },
    "ach": {
        "display_name": "PayFlow Direct",
        "fee_type": "percentage",
        "fee_percent": Decimal("0.8"),
        "flat_fee": Decimal("0.25"),
        "min_amount": Decimal("1"),
        "max_amount": Decimal("100000"),
        "countries": ["US"],
        "delivery": "2 to 3 business days",
        "supports_fintechs": False,
    },
}


# ============================================================
# FEE CALCULATION
# ============================================================

def calculate_fee(provider: str, amount: Decimal) -> Decimal:
    """Calculate the transfer fee for a given provider and amount."""
    config = PROVIDER_CONFIG.get(provider)
    if not config:
        return Decimal("0")

    if config["fee_type"] == "flat":
        return config["flat_fee"]

    # Percentage fee
    fee = (amount * config["fee_percent"] / Decimal("100")) + config["flat_fee"]

    # Apply Paystack NGN cap
    if provider == "paystack" and config.get("fee_cap_ngn"):
        # Convert cap to USD equivalent (approximate — use ₦1600 rate)
        cap_usd = config["fee_cap_ngn"] / Decimal("1600")
        fee = min(fee, cap_usd)

    return fee.quantize(Decimal("0.01"))


# ============================================================
# PROVIDER ELIGIBILITY
# ============================================================

def get_eligible_providers(
    amount: Decimal,
    destination_country: str,
    urgent: bool = False,
    preferred_provider: str = None
) -> list:
    """
    Get all providers eligible for this transfer.
    Returns sorted by fee (cheapest first).
    """
    eligible = []

    for provider, config in PROVIDER_CONFIG.items():
        # Check country support
        if destination_country not in config["countries"]:
            continue

        # Check amount limits
        if amount < config["min_amount"]:
            continue
        if amount > config["max_amount"]:
            continue

        # Calculate fee
        fee = calculate_fee(provider, amount)

        eligible.append({
            "provider": provider,
            "display_name": config["display_name"],
            "estimated_fee": str(fee),
            "estimated_fee_decimal": fee,
            "estimated_delivery": config["delivery"],
            "method": "bank_transfer",
            "reason": _get_reason(provider, amount, destination_country),
            "is_recommended": False,
        })

    # Sort by fee — cheapest first
    eligible.sort(key=lambda x: x["estimated_fee_decimal"])
    return eligible


def _get_reason(
    provider: str,
    amount: Decimal,
    country: str
) -> str:
    """Generate a user-friendly reason for provider selection."""
    reasons = {
        "paystack": "Best coverage for all Nigerian banks including Kuda, Opay, and Moniepoint",
        "flutterwave": "Wide coverage across Africa with fast processing",
        "chipper_cash": "Fastest option for small amounts — typically instant",
        "grey": "Excellent NGN rates with reliable delivery",
        "lemfi": "Competitive rates for Nigeria, Ghana, and Kenya",
        "wise": "Best for large transfers — lowest percentage fee globally",
        "wire": "Most reliable for urgent large transfers — same day delivery",
        "ach": "Cheapest option for US bank accounts",
    }
    return reasons.get(provider, "Competitive rates and fast delivery")


# ============================================================
# ROUTING LOGIC
# ============================================================

def get_recommended_provider(
    amount: Decimal,
    destination_country: str,
    urgent: bool = False,
    preferred_provider: str = None
) -> Optional[str]:
    """
    Select the best provider for a transfer.
    Logic is country and amount based.
    Returns internal provider name (never shown to user).
    """
    # Urgent always routes via Wire
    if urgent:
        if amount >= PROVIDER_CONFIG["wire"]["min_amount"]:
            return "wire"

    # User-specified preferred provider
    if preferred_provider:
        config = PROVIDER_CONFIG.get(preferred_provider)
        if (
            config
            and destination_country in config["countries"]
            and amount >= config["min_amount"]
            and amount <= config["max_amount"]
        ):
            return preferred_provider

    # Nigeria routing
    if destination_country == "NG":
        if amount <= Decimal("500"):
            return "paystack"    # Fast, covers all 278 banks
        elif amount <= Decimal("5000"):
            return "paystack"    # Best coverage + reasonable fee
        elif amount <= Decimal("50000"):
            return "flutterwave" # Large NGN transfers
        else:
            return "wire"        # Very large amounts

    # Ghana routing
    if destination_country == "GH":
        if amount <= Decimal("500"):
            return "chipper_cash"
        elif amount <= Decimal("5000"):
            return "flutterwave"
        else:
            return "wise"

    # Kenya routing
    if destination_country == "KE":
        if amount <= Decimal("1000"):
            return "chipper_cash"
        elif amount <= Decimal("10000"):
            return "grey"
        else:
            return "wise"

    # South Africa routing
    if destination_country == "ZA":
        if amount < Decimal("1000"):
            return "flutterwave"
        return "wise"

    # US routing
    if destination_country == "US":
        if amount < Decimal("1000"):
            return "ach"
        return "wire"

    # Uganda and Tanzania
    if destination_country in ["UG", "TZ"]:
        return "flutterwave"

    # Default — cheapest available
    eligible = get_eligible_providers(amount, destination_country)
    if eligible:
        return eligible[0]["provider"]

    return None


# ============================================================
# PUBLIC API — These functions are called by the API routes
# ============================================================

def get_payout_route(
    amount: float,
    destination_country: str,
    urgent: bool = False,
    preferred_provider: str = None
) -> dict:
    """
    Get recommended payout route.
    All provider names in response use PayFlow branding.
    """
    amount_decimal = Decimal(str(amount))

    recommended = get_recommended_provider(
        amount_decimal,
        destination_country,
        urgent,
        preferred_provider
    )

    if not recommended:
        return {
            "success": False,
            "message": (
                f"No transfer options available for "
                f"{destination_country} with amount ${amount:.2f}"
            ),
            "recommended_route": None
        }

    config = PROVIDER_CONFIG[recommended]
    fee = calculate_fee(recommended, amount_decimal)

    route = {
        "provider": recommended,              # Internal — used by backend only
        "display_name": config["display_name"], # PayFlow branded
        "method": "bank_transfer",
        "estimated_fee": str(fee),
        "estimated_delivery": config["delivery"],
        "delivery_note": config["delivery"],
        "reason": _get_reason(recommended, amount_decimal, destination_country),
        "is_recommended": True,
        "amount": str(amount_decimal),
        "amount_after_fee": str(amount_decimal - fee),
    }

    logger.info(
        f"Route selected: {recommended} for "
        f"${amount} to {destination_country} "
        f"(fee: ${fee})"
    )

    return {
        "success": True,
        "recommended_route": route
    }


def compare_all_routes(
    amount: float,
    destination_country: str
) -> dict:
    """
    Compare all available routes for a transfer.
    All provider names use PayFlow branding.
    """
    amount_decimal = Decimal(str(amount))
    eligible = get_eligible_providers(amount_decimal, destination_country)

    if not eligible:
        return {
            "success": False,
            "routes": [],
            "message": f"No routes available for {destination_country}"
        }

    # Mark the cheapest as recommended
    if eligible:
        eligible[0]["is_recommended"] = True

    # Clean response — remove internal decimal field
    for route in eligible:
        route.pop("estimated_fee_decimal", None)
        # Replace provider name with display name for frontend
        # but keep internal provider for selection
        route["display_name"] = PROVIDER_CONFIG.get(
            route["provider"], {}
        ).get("display_name", "PayFlow Transfer")

    logger.info(
        f"Compared {len(eligible)} routes for "
        f"${amount} to {destination_country}"
    )

    return {
        "success": True,
        "total": len(eligible),
        "routes": eligible
    }


def validate_transfer(
    amount: float,
    destination_country: str,
    provider: str = None
) -> dict:
    """
    Validate that a transfer can proceed.
    Returns validation result with any errors.
    """
    amount_decimal = Decimal(str(amount))
    errors = []

    if amount_decimal <= Decimal("0"):
        errors.append("Amount must be greater than zero")

    if amount_decimal < Decimal("1"):
        errors.append("Minimum transfer amount is $1.00")

    supported_countries = set()
    for config in PROVIDER_CONFIG.values():
        supported_countries.update(config["countries"])

    if destination_country not in supported_countries:
        errors.append(
            f"Transfers to {destination_country} are not yet supported"
        )

    if provider:
        config = PROVIDER_CONFIG.get(provider)
        if not config:
            errors.append(f"Invalid provider selected")
        elif destination_country not in config["countries"]:
            errors.append(
                f"Selected provider does not support {destination_country}"
            )
        elif amount_decimal > config["max_amount"]:
            errors.append(
                f"Amount exceeds maximum for selected route "
                f"(max: ${config['max_amount']})"
            )

    return {
        "valid": len(errors) == 0,
        "errors": errors
    }