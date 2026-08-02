"""
Paystack provider.

Bank codes are ALWAYS fetched live from Paystack API.
Never hardcoded — bank codes change, merge, and vary by country.
"""

import httpx
import time
from decimal import Decimal
from app.core.config import settings
from app.providers.base import BaseProvider, TransferResult
import logging

logger = logging.getLogger("fintech.paystack")

# Cache bank lists per country to avoid hammering the API
# Format: { "NG": {"banks": [...], "fetched_at": timestamp} }
_bank_cache: dict = {}
BANK_CACHE_TTL = 3600  # Refresh bank list every 1 hour


class PaystackProvider(BaseProvider):

    def __init__(self):
        self.base_url = settings.PAYSTACK_BASE_URL
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

    def _is_configured(self) -> bool:
        return bool(self.secret_key and self.secret_key != "")

    def get_banks(self, country: str = "NG") -> list:
        """
        Fetch live bank list from Paystack.
        Cached for 1 hour to avoid excessive API calls.
        Bank codes are dynamic — never use hardcoded codes.
        """
        if not self._is_configured():
            logger.warning("Paystack not configured — cannot fetch banks")
            return []

        country_upper = country.upper()
        now = time.time()

        # Return cached list if still fresh
        cached = _bank_cache.get(country_upper)
        if cached and (now - cached["fetched_at"]) < BANK_CACHE_TTL:
            logger.debug(
                f"Returning cached bank list for {country_upper} "
                f"({len(cached['banks'])} banks)"
            )
            return cached["banks"]

        # Map country code to Paystack country name
        country_name_map = {
            "NG": "nigeria",
            "GH": "ghana",
            "KE": "kenya",
            "ZA": "south africa",
            "US": "united states",
        }
        country_name = country_name_map.get(country_upper, country_upper.lower())

        try:
            response = httpx.get(
                f"{self.base_url}/bank",
                headers=self.headers,
                params={
                    "country": country_name,
                    "use_cursor": False,
                    "perPage": 200,  # Get all banks in one request
                },
                timeout=15.0
            )
            data = response.json()

            if data.get("status") is True:
                banks = [
                    {
                        "id": b.get("id"),
                        "code": str(b.get("code", "")).strip(),
                        "name": b.get("name", "").strip(),
                        "type": b.get("type", ""),
                        "country": b.get("country", country_upper),
                        "currency": b.get("currency", ""),
                        "active": b.get("active", True),
                    }
                    for b in data.get("data", [])
                    if b.get("code") and b.get("name")
                    and b.get("active", True)  # Only include active banks
                ]

                # Update cache
                _bank_cache[country_upper] = {
                    "banks": banks,
                    "fetched_at": now
                }

                logger.info(
                    f"Fetched {len(banks)} active banks for "
                    f"{country_upper} from Paystack"
                )
                return banks

            logger.error(
                f"Paystack banks error: {data.get('message', 'Unknown error')}"
            )
            return []

        except httpx.TimeoutException:
            logger.error("Paystack banks request timed out")
            # Return cached data even if stale
            if cached:
                logger.warning("Returning stale bank cache due to timeout")
                return cached["banks"]
            return []

        except Exception as e:
            logger.error(f"Paystack get_banks error: {e}")
            if cached:
                return cached["banks"]
            return []

    def get_bank_by_code(self, bank_code: str, country: str = "NG") -> dict:
        """
        Look up a single bank by its code.
        Uses the cached bank list to avoid extra API calls.
        """
        banks = self.get_banks(country)
        for bank in banks:
            if str(bank.get("code", "")).strip() == str(bank_code).strip():
                return bank
        return {}

    def get_bank_by_name(self, name: str, country: str = "NG") -> dict:
        """
        Fuzzy search for a bank by name.
        Useful when user types a bank name manually.
        """
        banks = self.get_banks(country)
        name_lower = name.lower()
        for bank in banks:
            if name_lower in bank.get("name", "").lower():
                return bank
        return {}

    def verify_account(
        self,
        account_number: str,
        bank_code: str
    ) -> dict:
        """
        Verify Nigerian bank account via Paystack.
        Bank code must be from the live Paystack bank list.
        """
        if not self._is_configured():
            return {
                "success": False,
                "account_name": None,
                "message": "manual_entry"
            }

        # Validate bank code exists in live list before calling
        bank_info = self.get_bank_by_code(bank_code)
        if not bank_info:
            logger.warning(
                f"Bank code {bank_code} not found in Paystack bank list"
            )
            # Still try anyway — Paystack might accept it
        else:
            logger.debug(
                f"Verifying account at {bank_info.get('name')} "
                f"(code: {bank_code})"
            )

        try:
            response = httpx.get(
                f"{self.base_url}/bank/resolve",
                headers=self.headers,
                params={
                    "account_number": account_number,
                    "bank_code": bank_code
                },
                timeout=15.0
            )
            data = response.json()

            if data.get("status") is True:
                return {
                    "success": True,
                    "account_name": data["data"]["account_name"],
                    "account_number": data["data"]["account_number"],
                    "message": "verified",
                    "provider": "paystack",
                    "bank_name": bank_info.get("name", "")
                }

            return {
                "success": False,
                "account_name": None,
                "message": data.get("message", "Could not verify")
            }

        except httpx.TimeoutException:
            return {
                "success": False,
                "account_name": None,
                "message": "manual_entry"
            }
        except Exception as e:
            logger.error(f"Paystack verify error: {e}")
            return {
                "success": False,
                "account_name": None,
                "message": "manual_entry"
            }

    def initiate_transfer(
        self,
        amount: Decimal,
        account_number: str,
        account_name: str,
        bank_code: str,
        bank_name: str,
        currency: str,
        reference: str,
        narration: str = "Payout"
    ) -> TransferResult:
        """
        Send money via Paystack.
        Requires funded Paystack balance and whitelisted IP.
        """
        if not self._is_configured():
            return TransferResult(
                success=False,
                provider_reference="",
                status="failed",
                message="Paystack not configured",
                estimated_delivery="",
                raw_response={}
            )

        try:
            # Step 1 — Create transfer recipient
            recipient_response = httpx.post(
                f"{self.base_url}/transferrecipient",
                headers=self.headers,
                json={
                    "type": "nuban",
                    "name": account_name,
                    "account_number": account_number,
                    "bank_code": bank_code,
                    "currency": "NGN"
                },
                timeout=15.0
            )
            recipient_data = recipient_response.json()

            if not recipient_data.get("status"):
                return TransferResult(
                    success=False,
                    provider_reference="",
                    status="failed",
                    message=recipient_data.get(
                        "message", "Failed to create recipient"
                    ),
                    estimated_delivery="",
                    raw_response=recipient_data
                )

            recipient_code = recipient_data["data"]["recipient_code"]
            logger.info(
                f"Paystack recipient created: {recipient_code} "
                f"for {account_name}"
            )

            # Step 2 — Initiate transfer
            # Paystack amount is in kobo (multiply by 100)
            amount_kobo = int(amount * 100)

            transfer_response = httpx.post(
                f"{self.base_url}/transfer",
                headers=self.headers,
                json={
                    "source": "balance",
                    "amount": amount_kobo,
                    "recipient": recipient_code,
                    "reason": narration,
                    "reference": reference
                },
                timeout=30.0
            )
            transfer_data = transfer_response.json()

            if transfer_data.get("status"):
                transfer = transfer_data["data"]
                transfer_status = transfer.get("status", "pending")

                return TransferResult(
                    success=True,
                    provider_reference=transfer.get(
                        "transfer_code", reference
                    ),
                    status="processing",
                    message=(
                        f"Transfer initiated via Paystack. "
                        f"Status: {transfer_status}"
                    ),
                    estimated_delivery="instant to 30 minutes",
                    raw_response=transfer_data
                )

            return TransferResult(
                success=False,
                provider_reference="",
                status="failed",
                message=transfer_data.get("message", "Transfer failed"),
                estimated_delivery="",
                raw_response=transfer_data
            )

        except httpx.TimeoutException:
            return TransferResult(
                success=False,
                provider_reference="",
                status="failed",
                message="Paystack request timed out",
                estimated_delivery="",
                raw_response={}
            )
        except Exception as e:
            logger.error(f"Paystack transfer error: {e}")
            return TransferResult(
                success=False,
                provider_reference="",
                status="failed",
                message=str(e),
                estimated_delivery="",
                raw_response={}
            )

    def verify_transfer(self, provider_reference: str) -> dict:
        return {"status": "unknown"}