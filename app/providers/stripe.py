"""
Stripe Treasury / ACH provider for US bank transfers.

ACH is US-only and requires a licensed US financial institution.
Stripe Treasury gives you access to ACH through their banking license.

Requirements:
- Stripe account with Treasury enabled
- US business entity (or use a partner)
- Get access at: https://stripe.com/treasury

For non-US founders: You can use Stripe through a US LLC or
partner with a US-based entity. Alternatively use Wise for
US transfers as well.

Sandbox: https://dashboard.stripe.com (test mode, free)
"""

import httpx
from decimal import Decimal
from app.core.config import settings
from app.providers.base import BaseProvider, TransferResult


class StripeACHProvider(BaseProvider):

    def __init__(self):
        self.base_url = "https://api.stripe.com/v1"
        self.secret_key = settings.STRIPE_SECRET_KEY
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

    def _is_configured(self) -> bool:
        return bool(self.secret_key and self.secret_key != "")

    def get_banks(self, country: str) -> list:
        # ACH is US only — no bank list needed, user enters routing number
        return []

    def verify_account(
        self,
        routing_number: str,
        account_number: str,
        account_holder_name: str
    ) -> dict:
        """
        Verify US bank account via Stripe.
        Stripe uses micro-deposits or instant verification.
        """
        if not self._is_configured():
            return {
                "success": True,
                "message": "Account verified (mock)",
                "mock": True
            }

        try:
            # Create bank account token
            response = httpx.post(
                f"{self.base_url}/tokens",
                headers=self.headers,
                data={
                    "bank_account[country]": "US",
                    "bank_account[currency]": "usd",
                    "bank_account[account_holder_name]": account_holder_name,
                    "bank_account[account_holder_type]": "individual",
                    "bank_account[routing_number]": routing_number,
                    "bank_account[account_number]": account_number
                },
                timeout=10.0
            )
            data = response.json()
            if data.get("id"):
                return {
                    "success": True,
                    "token": data["id"],
                    "bank_name": data.get("bank_account", {}).get("bank_name", "")
                }
            return {
                "success": False,
                "message": data.get("error", {}).get("message", "Verification failed")
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def initiate_transfer(
        self,
        amount: Decimal,
        account_number: str,
        account_name: str,
        bank_code: str,         # routing number for ACH
        bank_name: str,
        currency: str,
        reference: str,
        narration: str = "Payout"
    ) -> TransferResult:
        """
        Send ACH transfer via Stripe Treasury.
        Amount is in USD, currency must be USD for ACH.
        """
        if not self._is_configured():
            return TransferResult(
                success=True,
                provider_reference=f"STRIPE-MOCK-{reference}",
                status="processing",
                message=(
                    "ACH transfer initiated via Stripe (sandbox). "
                    "No real money moved."
                ),
                estimated_delivery="2-3 business days",
                raw_response={"mock": True}
            )

        try:
            # Convert to cents for Stripe (Stripe uses smallest currency unit)
            amount_cents = int(amount * 100)

            # Create payout via Stripe Treasury
            response = httpx.post(
                f"{self.base_url}/payouts",
                headers=self.headers,
                data={
                    "amount": amount_cents,
                    "currency": "usd",
                    "method": "standard",   # standard = ACH (2-3 days)
                    "description": narration,
                    "metadata[reference]": reference,
                    "metadata[account_name]": account_name
                },
                timeout=30.0
            )
            data = response.json()

            if data.get("id"):
                return TransferResult(
                    success=True,
                    provider_reference=data["id"],
                    status="processing",
                    message="ACH transfer initiated via Stripe",
                    estimated_delivery="2-3 business days",
                    raw_response=data
                )
            else:
                error_msg = data.get("error", {}).get("message", "Transfer failed")
                return TransferResult(
                    success=False,
                    provider_reference="",
                    status="failed",
                    message=error_msg,
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
            return {"status": "paid", "mock": True}

        try:
            response = httpx.get(
                f"{self.base_url}/payouts/{provider_reference}",
                headers=self.headers,
                timeout=10.0
            )
            return response.json()
        except Exception as e:
            return {"status": "unknown", "error": str(e)}