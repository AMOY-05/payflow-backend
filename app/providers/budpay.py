"""
BudPay provider integration.

BudPay is a Nigerian payment company with excellent
coverage for local bank transfers and account verification.

Get API key at: https://merchant.budpay.com
"""

import httpx
from decimal import Decimal
from app.core.config import settings
from app.providers.base import BaseProvider, TransferResult
import logging

logger = logging.getLogger("fintech.budpay")


class BudPayProvider(BaseProvider):

    def __init__(self):
        self.base_url = "https://api.budpay.com/api/v2"
        self.secret_key = getattr(settings, 'BUDPAY_SECRET_KEY', '')
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

    def _is_configured(self) -> bool:
        return bool(self.secret_key and self.secret_key != "")

    def verify_account(
        self,
        account_number: str,
        bank_code: str
    ) -> dict:
        """Verify Nigerian bank account via BudPay."""
        if not self._is_configured():
            return {"success": False, "account_name": None,
                    "message": "manual_entry"}

        try:
            response = httpx.post(
                f"{self.base_url}/bank/account/verify",
                headers=self.headers,
                json={
                    "bank_code": bank_code,
                    "account_number": account_number,
                    "currency": "NGN"
                },
                timeout=15.0
            )
            data = response.json()

            if data.get("success") is True:
                return {
                    "success": True,
                    "account_name": data["data"]["account_name"],
                    "account_number": account_number,
                    "message": "verified",
                    "provider": "budpay"
                }

            return {
                "success": False,
                "account_name": None,
                "message": data.get("message", "Verification failed")
            }

        except Exception as e:
            logger.error(f"BudPay verification error: {e}")
            return {"success": False, "account_name": None,
                    "message": "manual_entry"}

    def get_banks(self, country: str = "NG") -> list:
        """Get Nigerian banks from BudPay."""
        if not self._is_configured():
            return []

        try:
            response = httpx.get(
                f"{self.base_url}/bank/list",
                headers=self.headers,
                timeout=10.0
            )
            data = response.json()
            if data.get("success") is True:
                return [
                    {
                        "id": b.get("id"),
                        "code": b.get("bankCode") or b.get("code"),
                        "name": b.get("bankName") or b.get("name"),
                    }
                    for b in data.get("data", [])
                    if b.get("bankCode") or b.get("code")
                ]
        except Exception as e:
            logger.error(f"BudPay banks error: {e}")
        return []

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
        """Send money via BudPay."""
        if not self._is_configured():
            return TransferResult(
                success=True,
                provider_reference=f"BUDPAY-MOCK-{reference}",
                status="processing",
                message="BudPay transfer (mock mode)",
                estimated_delivery="instant to 30 minutes",
                raw_response={"mock": True}
            )

        try:
            response = httpx.post(
                f"{self.base_url}/bank/transfer",
                headers=self.headers,
                json={
                    "bank_code": bank_code,
                    "account_number": account_number,
                    "account_name": account_name,
                    "amount": str(amount),
                    "currency": currency,
                    "reference": reference,
                    "narration": narration
                },
                timeout=30.0
            )
            data = response.json()

            if data.get("success") is True:
                return TransferResult(
                    success=True,
                    provider_reference=str(
                        data.get("data", {}).get("reference", reference)
                    ),
                    status="processing",
                    message="Transfer initiated via BudPay",
                    estimated_delivery="instant to 30 minutes",
                    raw_response=data
                )

            return TransferResult(
                success=False,
                provider_reference="",
                status="failed",
                message=data.get("message", "Transfer failed"),
                estimated_delivery="",
                raw_response=data
            )

        except Exception as e:
            return TransferResult(
                success=False,
                provider_reference="",
                status="failed",
                message=str(e),
                estimated_delivery="",
                raw_response={}
            )

    def verify_transfer(self, provider_reference: str) -> dict:
        if not self._is_configured():
            return {"status": "successful", "mock": True}

        try:
            response = httpx.get(
                f"{self.base_url}/transaction/{provider_reference}",
                headers=self.headers,
                timeout=10.0
            )
            return response.json()
        except Exception:
            return {"status": "unknown"}