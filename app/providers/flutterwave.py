"""
Flutterwave provider integration.

Flutterwave is the most accessible provider for Nigerian developers.
You can get sandbox API keys immediately after signup with just
a business email and BVN verification.

Current status: Running in MOCK mode because Flutterwave transfer
activation requires additional business verification.

To switch to live mode:
1. Complete business profile on dashboard.flutterwave.com
2. Contact Flutterwave support to enable transfers
3. Change _is_configured() to return the real check:
   return bool(self.secret_key and self.secret_key != "")
"""

import httpx
from decimal import Decimal

from app.core.config import settings
from app.providers.base import BaseProvider, TransferResult


class FlutterwaveProvider(BaseProvider):

    def __init__(self):
        self.base_url = settings.FLUTTERWAVE_BASE_URL
        self.secret_key = settings.FLUTTERWAVE_SECRET_KEY
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

    def _is_configured(self) -> bool:
        """
        Returns False for transfers (not yet activated).
        Changed to False until Flutterwave activates transfers.
        """
        return False

    def _can_verify_accounts(self) -> bool:
        """
        Account verification works with both test and live keys.
        Only requires a valid secret key to be configured.
        """
        return bool(self.secret_key and self.secret_key != "")

    def get_banks(self, country: str = "NG") -> list:
        """
        Get list of supported banks in a country.
        Used to populate the bank dropdown on the frontend.
        Falls back to hardcoded Nigerian bank list if API fails.
        """
        if not self._is_configured():
            return self._mock_nigerian_banks()

        try:
            response = httpx.get(
                f"{self.base_url}/banks/{country}",
                headers=self.headers,
                timeout=10.0
            )
            data = response.json()
            if data.get("status") == "success":
                return data.get("data", [])
            return self._mock_nigerian_banks()
        except Exception:
            return self._mock_nigerian_banks()

    def verify_account(
        self,
        account_number: str,
        bank_code: str
    ) -> dict:
        """
        Verify that a bank account exists.
        Uses real Flutterwave API if live keys are configured.
        Falls back to asking user to enter name manually.
        """
        if not self._can_verify_accounts():
            return {
                "success": False,
                "account_name": None,
                "message": "manual_entry",
                "account_number": account_number
            }

        try:
            response = httpx.post(
                f"{self.base_url}/accounts/resolve",
                headers=self.headers,
                json={
                    "account_number": account_number,
                    "account_bank": bank_code
                },
                timeout=15.0
            )
            data = response.json()
            if data.get("status") == "success":
                return {
                    "success": True,
                    "account_name": data["data"]["account_name"],
                    "account_number": data["data"]["account_number"],
                    "message": "verified"
                }
            return {
                "success": False,
                "account_name": None,
                "message": data.get("message", "Could not verify account")
            }
        except httpx.TimeoutException:
            return {
                "success": False,
                "account_name": None,
                "message": "manual_entry"
            }
        except Exception as e:
            return {
                "success": False,
                "account_name": None,
                "message": str(e)
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
        Send money to a bank account via Flutterwave.

        In mock mode returns a realistic mock response so the
        full withdrawal flow can be tested without real money moving.

        In live mode calls the real Flutterwave Transfer API.

        Flow:
        1. Check if configured (live or mock)
        2. If mock — return success with mock reference
        3. If live — call Flutterwave API and handle response
        4. On timeout — return failed result
        5. On any other error — return failed result

        Note: Always returns a TransferResult object, never None.
        The withdrawal service depends on this guarantee.
        """

        # Mock mode — return realistic mock response
        if not self._is_configured():
            return TransferResult(
                success=True,
                provider_reference=f"FLW-MOCK-{reference}",
                status="processing",
                message=(
                    "Transfer initiated successfully (sandbox mode). "
                    "No real money has been moved."
                ),
                estimated_delivery="15 minutes to 2 hours",
                raw_response={"mock": True, "reference": reference}
            )

        # Live mode — call real Flutterwave API
        payload = {
            "account_bank": bank_code,
            "account_number": account_number,
            "amount": float(amount),
            "narration": narration,
            "currency": currency,
            "reference": reference,
            "callback_url": (
                f"{settings.WEBHOOK_BASE_URL}/api/v1/webhooks/flutterwave"
            ),
            "debit_currency": "USD"
        }

        try:
            response = httpx.post(
                f"{self.base_url}/transfers",
                headers=self.headers,
                json=payload,
                timeout=30.0
            )
            data = response.json()

            if data.get("status") == "success":
                transfer_data = data.get("data", {})
                return TransferResult(
                    success=True,
                    provider_reference=str(transfer_data.get("id", "")),
                    status=transfer_data.get("status", "processing").lower(),
                    message=data.get("message", "Transfer initiated"),
                    estimated_delivery="15 minutes to 2 hours",
                    raw_response=data
                )
            else:
                # Flutterwave returned an error response
                return TransferResult(
                    success=False,
                    provider_reference="",
                    status="failed",
                    message=data.get("message", "Transfer failed"),
                    estimated_delivery="",
                    raw_response=data
                )

        except httpx.TimeoutException:
            # Flutterwave did not respond in time
            # The withdrawal service will refund the wallet
            return TransferResult(
                success=False,
                provider_reference="",
                status="failed",
                message=(
                    "Flutterwave did not respond in time. "
                    "Please try again."
                ),
                estimated_delivery="",
                raw_response={}
            )

        except Exception as e:
            # Any other unexpected error
            return TransferResult(
                success=False,
                provider_reference="",
                status="failed",
                message=str(e),
                estimated_delivery="",
                raw_response={}
            )

    def verify_transfer(self, provider_reference: str) -> dict:
        """
        Check the current status of an existing transfer.
        Called by the reconciliation task every 5 minutes
        to catch transfers that completed without a webhook.
        """
        if not self._is_configured():
            return {"status": "successful", "mock": True}

        try:
            response = httpx.get(
                f"{self.base_url}/transfers/{provider_reference}",
                headers=self.headers,
                timeout=10.0
            )
            data = response.json()
            return data.get("data", {})
        except Exception as e:
            return {"status": "unknown", "error": str(e)}

    def _mock_nigerian_banks(self) -> list:
        return [
            {"id": 1,  "code": "044",    "name": "Access Bank"},
            {"id": 2,  "code": "063",    "name": "Access Bank (Diamond)"},
            {"id": 3,  "code": "035A",   "name": "ALAT by WEMA"},
            {"id": 4,  "code": "023",    "name": "Citibank Nigeria"},
            {"id": 5,  "code": "050",    "name": "EcoBank Nigeria"},
            {"id": 6,  "code": "070",    "name": "Fidelity Bank"},
            {"id": 7,  "code": "011",    "name": "First Bank of Nigeria"},
            {"id": 8,  "code": "214",    "name": "First City Monument Bank"},
            {"id": 9,  "code": "058",    "name": "Guaranty Trust Bank"},
            {"id": 10, "code": "030",    "name": "Heritage Bank"},
            {"id": 11, "code": "301",    "name": "Jaiz Bank"},
            {"id": 12, "code": "082",    "name": "Keystone Bank"},
            {"id": 13, "code": "526",    "name": "Parallex Bank"},
            {"id": 14, "code": "076",    "name": "Polaris Bank"},
            {"id": 15, "code": "101",    "name": "Providus Bank"},
            {"id": 16, "code": "221",    "name": "Stanbic IBTC Bank"},
            {"id": 17, "code": "068",    "name": "Standard Chartered Bank"},
            {"id": 18, "code": "232",    "name": "Sterling Bank"},
            {"id": 19, "code": "032",    "name": "Union Bank of Nigeria"},
            {"id": 20, "code": "033",    "name": "United Bank for Africa"},
            {"id": 21, "code": "215",    "name": "Unity Bank"},
            {"id": 22, "code": "035",    "name": "Wema Bank"},
            {"id": 23, "code": "057",    "name": "Zenith Bank"},
            {"id": 24, "code": "327",    "name": "Opay"},
            {"id": 25, "code": "090405", "name": "Moniepoint"},
            {"id": 26, "code": "50211",  "name": "Kuda Bank"},
            {"id": 27, "code": "090267", "name": "Palmpay"},
            {"id": 28, "code": "100",    "name": "Suntrust Bank"},
            {"id": 29, "code": "090115", "name": "TCF MFB"},
        ]