from decimal import Decimal
from dataclasses import dataclass
from typing import Optional


@dataclass
class RouteResult:
    provider: str
    method: str
    estimated_fee: Decimal
    fee_currency: str
    estimated_delivery: str
    delivery_note: str        # honest explanation of the timing
    reason: str
    priority: int
    is_recommended: bool
    provider_logo: str        # for frontend display
    supported_countries: list


# ---------------------------------------------------------------------------
# Provider fee schedules (real published rates)
# ---------------------------------------------------------------------------

PROVIDER_FEES = {
    "grey": {
        "flat_fee": Decimal("0.00"),
        "percent_fee": Decimal("0.01"),      # 1%
        "max_fee": Decimal("30.00"),
        "min_amount": Decimal("5.00"),
        "max_amount": Decimal("50000.00"),
        "delivery": "1 - 3 hours",
        "delivery_note": (
            "Grey processes payouts within 1-3 hours on business days. "
            "Transfers initiated after 5PM WAT may arrive the next business day."
        ),
        "logo": "grey.png",
    },
    "flutterwave": {
        "flat_fee": Decimal("1.50"),
        "percent_fee": Decimal("0.014"),     # 1.4%
        "max_fee": Decimal("10.00"),
        "min_amount": Decimal("1.00"),
        "max_amount": Decimal("10000.00"),
        "delivery": "15 minutes - 2 hours",
        "delivery_note": (
            "Flutterwave sends to most African banks within 15 minutes. "
            "Some smaller banks may take up to 2 hours. "
            "Available 24/7 including weekends."
        ),
        "logo": "flutterwave.png",
    },
    "chipper_cash": {
        "flat_fee": Decimal("0.00"),
        "percent_fee": Decimal("0.013"),     # 1.3%
        "max_fee": Decimal("20.00"),
        "min_amount": Decimal("1.00"),
        "max_amount": Decimal("5000.00"),
        "delivery": "instant to 30 minutes",
        "delivery_note": (
            "Chipper Cash uses a float-based model. "
            "Your recipient gets credited almost instantly from Chipper's local reserve. "
            "Available 24/7 but maximum $5,000 per transaction."
        ),
        "logo": "chipper_cash.png",
    },
    "lemfi": {
        "flat_fee": Decimal("0.00"),
        "percent_fee": Decimal("0.015"),     # 1.5%
        "max_fee": Decimal("25.00"),
        "min_amount": Decimal("5.00"),
        "max_amount": Decimal("20000.00"),
        "delivery": "1 - 2 hours",
        "delivery_note": (
            "LemFi (formerly Lemonade Finance) delivers to Nigerian, "
            "Ghanaian and Kenyan banks within 1-2 hours. "
            "Known for very competitive NGN rates."
        ),
        "logo": "lemfi.png",
    },
    "wise": {
        "flat_fee": Decimal("0.00"),
        "percent_fee": Decimal("0.0065"),    # 0.65% — Wise is cheapest for large amounts
        "max_fee": Decimal("45.00"),
        "min_amount": Decimal("1.00"),
        "max_amount": Decimal("1000000.00"),
        "delivery": "instant to 2 business days",
        "delivery_note": (
            "Wise (Transferwise) is often the cheapest for large amounts. "
            "Many transfers arrive instantly via local payment rails. "
            "Larger amounts and new accounts may take 1-2 business days."
        ),
        "logo": "wise.png",
    },
    "ach": {
        "flat_fee": Decimal("0.25"),
        "percent_fee": Decimal("0.008"),     # 0.8%
        "max_fee": Decimal("5.00"),
        "min_amount": Decimal("1.00"),
        "max_amount": Decimal("25000.00"),
        "delivery": "2 - 3 business days",
        "delivery_note": (
            "ACH (Automated Clearing House) is the standard US bank transfer network. "
            "Transfers are processed in batches during US banking hours (Mon-Fri). "
            "Cheapest option for US bank accounts but not available on weekends."
        ),
        "logo": "ach.png",
    },
    "wire": {
        "flat_fee": Decimal("25.00"),
        "percent_fee": Decimal("0.00"),
        "max_fee": Decimal("25.00"),
        "min_amount": Decimal("100.00"),
        "max_amount": Decimal("1000000.00"),
        "delivery": "same day (before 3PM EST) or next business day",
        "delivery_note": (
            "Wire transfers are the most reliable for large international payments. "
            "Initiated before 3PM EST arrive same day. "
            "After 3PM EST or on weekends they arrive the next US business day. "
            "Flat $25 fee regardless of amount — best value for transfers above $5,000."
        ),
        "logo": "wire.png",
    },
    "payoneer": {
        "flat_fee": Decimal("0.00"),
        "percent_fee": Decimal("0.02"),      # 2%
        "max_fee": Decimal("50.00"),
        "min_amount": Decimal("20.00"),
        "max_amount": Decimal("100000.00"),
        "delivery": "instant to 3 business days",
        "delivery_note": (
            "Payoneer to Payoneer transfers are instant and free. "
            "Payoneer to local bank takes 1-3 business days depending on country. "
            "Widely accepted by Amazon KDP, Upwork, Fiverr, and other platforms."
        ),
        "logo": "payoneer.png",
    },
}


# Countries each provider supports
PROVIDER_COUNTRIES = {
    "grey":         ["NG", "GH", "KE"],
    "flutterwave":  ["NG", "GH", "KE", "ZA", "UG", "TZ", "RW", "ZM", "CM", "CI", "SN", "ET"],
    "chipper_cash": ["NG", "GH", "KE", "ZA", "UG", "TZ", "RW", "ZM"],
    "lemfi":        ["NG", "GH", "KE", "GB", "US", "CA"],
    "wise":         ["*"],   # supports almost all countries
    "ach":          ["US"],
    "wire":         ["*"],   # supports all countries
    "payoneer":     ["*"],   # supports 190+ countries
}

# Human-readable provider names for display
PROVIDER_NAMES = {
    "grey":         "Grey",
    "flutterwave":  "Flutterwave",
    "chipper_cash": "Chipper Cash",
    "lemfi":        "LemFi",
    "wise":         "Wise",
    "ach":          "ACH Bank Transfer",
    "wire":         "International Wire",
    "payoneer":     "Payoneer",
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def calculate_fee(provider: str, amount: Decimal) -> Decimal:
    config = PROVIDER_FEES[provider]
    fee = config["flat_fee"] + (amount * config["percent_fee"])
    return min(fee, config["max_fee"]).quantize(Decimal("0.01"))


def provider_supports_country(provider: str, country_code: str) -> bool:
    supported = PROVIDER_COUNTRIES.get(provider, [])
    return "*" in supported or country_code.upper() in supported


def provider_supports_amount(provider: str, amount: Decimal) -> bool:
    config = PROVIDER_FEES[provider]
    return config["min_amount"] <= amount <= config["max_amount"]


# ---------------------------------------------------------------------------
# Core routing logic
# ---------------------------------------------------------------------------

def get_best_route(
    amount: Decimal,
    destination_country: str,
    urgent: bool = False,
    preferred_provider: Optional[str] = None
) -> RouteResult:
    """
    Returns the single best route for this transfer.

    Priority logic:
    1. Urgent → Wire (guaranteed same day if before 3PM EST)
    2. Preferred provider → use it if valid
    3. US destination → ACH (cheapest) or Wire (if large)
    4. Nigeria/Ghana/Kenya small amount → Chipper Cash (fastest)
    5. Nigeria/Ghana/Kenya mid amount → Grey (best FX rate)
    6. Nigeria/Ghana/Kenya large amount → Wire (most reliable)
    7. Other African countries → Flutterwave
    8. Global fallback → Wise (cheapest percentage fee globally)
    9. Final fallback → Wire (always available everywhere)
    """
    country = destination_country.upper()

    # Rule 1 — Urgent always goes Wire
    if urgent:
        fee = calculate_fee("wire", amount)
        config = PROVIDER_FEES["wire"]
        return RouteResult(
            provider="wire",
            method="wire_transfer",
            estimated_fee=fee,
            fee_currency="USD",
            estimated_delivery=config["delivery"],
            delivery_note=config["delivery_note"],
            reason="Wire selected: urgent transfer — guaranteed fastest delivery",
            priority=1,
            is_recommended=True,
            provider_logo=config["logo"],
            supported_countries=["*"]
        )

    # Rule 2 — Preferred provider requested and valid
    if preferred_provider and preferred_provider in PROVIDER_FEES:
        if (
            provider_supports_country(preferred_provider, country)
            and provider_supports_amount(preferred_provider, amount)
        ):
            fee = calculate_fee(preferred_provider, amount)
            config = PROVIDER_FEES[preferred_provider]
            return RouteResult(
                provider=preferred_provider,
                method="bank_transfer",
                estimated_fee=fee,
                fee_currency="USD",
                estimated_delivery=config["delivery"],
                delivery_note=config["delivery_note"],
                reason=f"Your preferred provider: {PROVIDER_NAMES[preferred_provider]}",
                priority=1,
                is_recommended=True,
                provider_logo=config["logo"],
                supported_countries=PROVIDER_COUNTRIES[preferred_provider]
            )

    # Rule 3 — US destination
    if country == "US":
        if amount <= Decimal("25000.00"):
            fee = calculate_fee("ach", amount)
            config = PROVIDER_FEES["ach"]
            return RouteResult(
                provider="ach",
                method="ach",
                estimated_fee=fee,
                fee_currency="USD",
                estimated_delivery=config["delivery"],
                delivery_note=config["delivery_note"],
                reason="ACH selected: cheapest option for US bank accounts",
                priority=1,
                is_recommended=True,
                provider_logo=config["logo"],
                supported_countries=["US"]
            )
        else:
            fee = calculate_fee("wire", amount)
            config = PROVIDER_FEES["wire"]
            return RouteResult(
                provider="wire",
                method="wire_transfer",
                estimated_fee=fee,
                fee_currency="USD",
                estimated_delivery=config["delivery"],
                delivery_note=config["delivery_note"],
                reason="Wire selected: amount too large for ACH, wire is most reliable",
                priority=1,
                is_recommended=True,
                provider_logo=config["logo"],
                supported_countries=["*"]
            )

    # Rule 4 — Nigeria/Ghana/Kenya small amount → Chipper Cash (fastest)
    if (
        country in ["NG", "GH", "KE", "ZA", "UG", "TZ", "RW", "ZM"]
        and amount <= Decimal("500.00")
        and provider_supports_amount("chipper_cash", amount)
    ):
        fee = calculate_fee("chipper_cash", amount)
        config = PROVIDER_FEES["chipper_cash"]
        return RouteResult(
            provider="chipper_cash",
            method="bank_transfer",
            estimated_fee=fee,
            fee_currency="USD",
            estimated_delivery=config["delivery"],
            delivery_note=config["delivery_note"],
            reason="Chipper Cash selected: fastest delivery for small African payouts",
            priority=1,
            is_recommended=True,
            provider_logo=config["logo"],
            supported_countries=PROVIDER_COUNTRIES["chipper_cash"]
        )

    # Rule 5 — Nigeria/Ghana/Kenya mid amount → Grey (best FX)
    if (
        country in ["NG", "GH", "KE"]
        and Decimal("500.00") < amount <= Decimal("5000.00")
        and provider_supports_amount("grey", amount)
    ):
        fee = calculate_fee("grey", amount)
        config = PROVIDER_FEES["grey"]
        return RouteResult(
            provider="grey",
            method="bank_transfer",
            estimated_fee=fee,
            fee_currency="USD",
            estimated_delivery=config["delivery"],
            delivery_note=config["delivery_note"],
            reason="Grey selected: best NGN/GHS/KES exchange rate for mid-range amounts",
            priority=1,
            is_recommended=True,
            provider_logo=config["logo"],
            supported_countries=PROVIDER_COUNTRIES["grey"]
        )

    # Rule 6 — Large amounts Nigeria/Ghana/Kenya → Wire
    if (
        country in ["NG", "GH", "KE"]
        and amount > Decimal("5000.00")
    ):
        fee = calculate_fee("wire", amount)
        config = PROVIDER_FEES["wire"]
        return RouteResult(
            provider="wire",
            method="wire_transfer",
            estimated_fee=fee,
            fee_currency="USD",
            estimated_delivery=config["delivery"],
            delivery_note=config["delivery_note"],
            reason="Wire selected: most reliable and cost-effective for large NGN payouts",
            priority=1,
            is_recommended=True,
            provider_logo=config["logo"],
            supported_countries=["*"]
        )

    # Rule 7 — Other African countries → Flutterwave
    if provider_supports_country("flutterwave", country):
        fee = calculate_fee("flutterwave", amount)
        config = PROVIDER_FEES["flutterwave"]
        return RouteResult(
            provider="flutterwave",
            method="bank_transfer",
            estimated_fee=fee,
            fee_currency="USD",
            estimated_delivery=config["delivery"],
            delivery_note=config["delivery_note"],
            reason="Flutterwave selected: widest African bank coverage",
            priority=1,
            is_recommended=True,
            provider_logo=config["logo"],
            supported_countries=PROVIDER_COUNTRIES["flutterwave"]
        )

    # Rule 8 — Global → Wise (cheapest percentage globally)
    if provider_supports_amount("wise", amount):
        fee = calculate_fee("wise", amount)
        config = PROVIDER_FEES["wise"]
        return RouteResult(
            provider="wise",
            method="bank_transfer",
            estimated_fee=fee,
            fee_currency="USD",
            estimated_delivery=config["delivery"],
            delivery_note=config["delivery_note"],
            reason="Wise selected: lowest fees for international transfers globally",
            priority=1,
            is_recommended=True,
            provider_logo=config["logo"],
            supported_countries=["*"]
        )

    # Rule 9 — Final fallback → Wire
    fee = calculate_fee("wire", amount)
    config = PROVIDER_FEES["wire"]
    return RouteResult(
        provider="wire",
        method="wire_transfer",
        estimated_fee=fee,
        fee_currency="USD",
        estimated_delivery=config["delivery"],
        delivery_note=config["delivery_note"],
        reason="Wire selected: universal fallback, works for all countries",
        priority=1,
        is_recommended=True,
        provider_logo=config["logo"],
        supported_countries=["*"]
    )


def get_all_routes(
    amount: Decimal,
    destination_country: str,
) -> list:
    """
    Return every available provider for this transfer
    sorted by fee so user can compare and choose.
    """
    country = destination_country.upper()
    routes = []

    for provider, config in PROVIDER_FEES.items():
        if (
            provider_supports_country(provider, country)
            and provider_supports_amount(provider, amount)
        ):
            fee = calculate_fee(provider, amount)
            routes.append(RouteResult(
                provider=provider,
                method=(
                    "wire_transfer" if provider == "wire"
                    else "ach" if provider == "ach"
                    else "bank_transfer"
                ),
                estimated_fee=fee,
                fee_currency="USD",
                estimated_delivery=config["delivery"],
                delivery_note=config["delivery_note"],
                reason=f"{PROVIDER_NAMES[provider]}: available for this transfer",
                priority=0,
                is_recommended=False,
                provider_logo=config["logo"],
                supported_countries=PROVIDER_COUNTRIES[provider]
            ))

    # Sort by fee cheapest first
    routes.sort(key=lambda r: r.estimated_fee)

    # Mark cheapest as recommended
    if routes:
        routes[0].is_recommended = True

    return routes