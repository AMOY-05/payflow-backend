"""
Smart account verification service.

The user only types their account number.
We automatically detect which bank it belongs to
by trying all active banks until one resolves.

No provider names are ever exposed to users.
PayFlow is the only brand users see.
"""

import httpx
import os
import time
import logging

logger = logging.getLogger("fintech.verification")

# Cache the full bank list — refreshed every hour
_bank_list_cache = {"banks": [], "fetched_at": 0}
CACHE_TTL = 3600


def get_live_bank_list() -> list:
    """
    Fetch all active Nigerian banks from Paystack.
    Cached for 1 hour.
    """
    now = time.time()
    if (
        _bank_list_cache["banks"]
        and now - _bank_list_cache["fetched_at"] < CACHE_TTL
    ):
        return _bank_list_cache["banks"]

    key = os.getenv("PAYSTACK_SECRET_KEY", "")
    if not key:
        return []

    try:
        r = httpx.get(
            "https://api.paystack.co/bank",
            headers={"Authorization": f"Bearer {key}"},
            params={"country": "nigeria", "perPage": 200},
            timeout=15.0
        )
        data = r.json()
        if data.get("status"):
            banks = [
                {
                    "code": str(b["code"]).strip(),
                    "name": b["name"].strip(),
                }
                for b in data.get("data", [])
                if b.get("active") and b.get("code") and b.get("name")
            ]
            _bank_list_cache["banks"] = banks
            _bank_list_cache["fetched_at"] = now
            logger.info(f"Loaded {len(banks)} active banks from Paystack")
            return banks
    except Exception as e:
        logger.error(f"Failed to load bank list: {e}")

    return _bank_list_cache.get("banks", [])


def auto_detect_bank(account_number: str) -> dict:
    """
    Automatically detect which bank an account number belongs to.

    Strategy:
    1. Try the most common banks first (GTBank, Access, Zenith, UBA,
       First Bank, Kuda, Opay, Moniepoint, Palmpay) for speed
    2. If not found, try all remaining banks in the live list
    3. Return bank code + account name when found

    User never selects a bank — PayFlow detects it automatically.
    """
    if not account_number or len(account_number) != 10:
        return {"success": False, "account_name": None, "bank_code": None}

    # Priority banks — try these first for speed
    # These cover 90% of Nigerian users
    priority_banks = [
        {"code": "058", "name": "GTBank"},
        {"code": "057", "name": "Zenith Bank"},
        {"code": "044", "name": "Access Bank"},
        {"code": "033", "name": "UBA"},
        {"code": "011", "name": "First Bank"},
        {"code": "50211", "name": "Kuda Bank"},
        {"code": "999992", "name": "Opay"},
        {"code": "50515", "name": "Moniepoint"},
        {"code": "999991", "name": "Palmpay"},
        {"code": "070", "name": "Fidelity Bank"},
        {"code": "032", "name": "Union Bank"},
        {"code": "214", "name": "FCMB"},
        {"code": "232", "name": "Sterling Bank"},
        {"code": "221", "name": "Stanbic IBTC"},
        {"code": "035", "name": "Wema Bank"},
        {"code": "063", "name": "Access Bank (Diamond)"},
        {"code": "076", "name": "Polaris Bank"},
    ]

    # Try priority banks first
    result = _try_banks_batch(account_number, priority_banks)
    if result["success"]:
        return result

    # Get full live bank list and try remaining banks
    all_banks = get_live_bank_list()
    priority_codes = {b["code"] for b in priority_banks}
    remaining_banks = [
        b for b in all_banks
        if b["code"] not in priority_codes
    ]

    if remaining_banks:
        result = _try_banks_batch(account_number, remaining_banks)
        if result["success"]:
            return result

    return {
        "success": False,
        "account_name": None,
        "bank_code": None,
        "bank_name": None,
        "message": "Could not detect bank automatically"
    }


def _try_banks_batch(account_number: str, banks: list) -> dict:
    """
    Try resolving account number against a list of banks.
    Returns immediately when first match is found.
    """
    key = os.getenv("PAYSTACK_SECRET_KEY", "")
    if not key:
        return {"success": False, "account_name": None}

    for bank in banks:
        result = _resolve_with_paystack(
            account_number, bank["code"], key
        )
        if result["success"]:
            result["bank_code"] = bank["code"]
            result["bank_name"] = bank.get("name", "")
            return result

    return {"success": False, "account_name": None}


def _resolve_with_paystack(
    account_number: str,
    bank_code: str,
    key: str
) -> dict:
    """Single Paystack account resolution attempt."""
    try:
        r = httpx.get(
            "https://api.paystack.co/bank/resolve",
            headers={"Authorization": f"Bearer {key}"},
            params={
                "account_number": account_number,
                "bank_code": bank_code
            },
            timeout=8.0
        )
        data = r.json()
        if data.get("status") is True:
            return {
                "success": True,
                "account_name": data["data"]["account_name"],
                "account_number": data["data"]["account_number"],
                "message": "verified"
            }
    except Exception:
        pass
    return {"success": False, "account_name": None}


def verify_bank_account(
    account_number: str,
    bank_code: str = None
) -> dict:
    """
    Verify bank account.

    If bank_code is provided (user selected manually), use it directly.
    If bank_code is None or empty, auto-detect the bank.
    """
    account_number = account_number.strip()

    if bank_code and bank_code.strip():
        # User selected a bank — verify directly
        bank_code = bank_code.strip()
        result = _resolve_with_paystack(
            account_number,
            bank_code,
            os.getenv("PAYSTACK_SECRET_KEY", "")
        )
        if result["success"]:
            return result

        # Paystack failed — try Flutterwave
        flw_result = _try_flutterwave(account_number, bank_code)
        if flw_result["success"]:
            return flw_result

        # All failed — manual entry
        return {
            "success": False,
            "account_name": None,
            "message": "manual_entry"
        }
    else:
        # No bank selected — auto-detect
        return auto_detect_bank(account_number)


def _try_flutterwave(account_number: str, bank_code: str) -> dict:
    """Flutterwave fallback."""
    secret_key = os.getenv("FLUTTERWAVE_SECRET_KEY", "")
    if not secret_key:
        return {"success": False, "account_name": None}

    try:
        r = httpx.post(
            "https://api.flutterwave.com/v3/accounts/resolve",
            headers={
                "Authorization": f"Bearer {secret_key}",
                "Content-Type": "application/json"
            },
            json={
                "account_number": account_number,
                "account_bank": bank_code
            },
            timeout=15.0
        )
        data = r.json()
        if data.get("status") == "success":
            return {
                "success": True,
                "account_name": data["data"]["account_name"],
                "account_number": data["data"]["account_number"],
                "message": "verified"
            }
    except Exception:
        pass
    return {"success": False, "account_name": None}


def get_all_banks(country: str = "NG") -> list:
    """Get deduplicated live bank list."""
    if country.upper() == "NG":
        banks = get_live_bank_list()
        if banks:
            return sorted(banks, key=lambda x: x.get("name", ""))

    # Fallback to Flutterwave for other countries
    from app.providers.flutterwave import FlutterwaveProvider
    try:
        flw = FlutterwaveProvider()
        return flw.get_banks(country)
    except Exception:
        return []


def clear_bank_cache():
    """Force refresh bank list on next request."""
    _bank_list_cache["banks"] = []
    _bank_list_cache["fetched_at"] = 0
    logger.info("Bank cache cleared")