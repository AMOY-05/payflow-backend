"""
Wise Business API provider for international wire transfers.

Wise is the best partner for wire transfers because:
- 0.65% fee (lowest in the market)
- Supports 80+ currencies
- No minimum amount
- Regulatory licenses in Nigeria, UK, US, EU

Get API access at: https://wise.com/gb/business/api
Sandbox is free and immediate — no business verification needed for testing.
"""

import httpx
from decimal import Decimal
from app.core.config import settings
from app.providers.base import BaseProvider, TransferResult


class WiseProvider(BaseProvider):

    def __init__(self):
        self.base_url = settings.WISE_BASE_URL
        self.api_key = settings.WISE_API_KEY
        self.profile_id = settings.WISE_PROFILE_ID
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _is_configured(self) -> bool:
        return bool(
            self.api_key
            and self.api_key != ""
            and self.profile_id
            and self.profile_id != ""
        )

    def get_banks(self, country: str) -> list:
        return []

    def get_exchange_rate(
        self,
        source_currency: str,
        target_currency: str,
        amount: Decimal
    ) -> dict:
        """
        Get Wise's real-time exchange rate for a transfer.
        This is the actual rate the recipient will receive.
        """
        if not self._is_configured():
            from app.services.fx_service import MOCK_INTERBANK_RATES
            mock_rate = MOCK_INTERBANK_RATES.get(target_currency, Decimal("1"))
            return {
                "rate": float(mock_rate * Decimal("0.9935")),
                "fee": float(amount * Decimal("0.0065")),
                "source_amount": float(amount),
                "target_amount": float(amount * mock_rate * Decimal("0.9935")),
                "mock": True
            }

        try:
            response = httpx.get(
                f"{self.base_url}/v1/rates",
                headers=self.headers,
                params={
                    "source": source_currency,
                    "target": target_currency
                },
                timeout=10.0
            )
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                rate = data[0].get("rate", 1)
                return {
                    "rate": rate,
                    "fee": float(amount * Decimal("0.0065")),
                    "source_amount": float(amount),
                    "target_amount": float(amount) * rate,
                    "mock": False
                }
        except Exception:
            pass

        return {"rate": 1, "fee": 0, "mock": True}

    def create_quote(
        self,
        source_currency: str,
        target_currency: str,
        source_amount: Decimal
    ) -> dict:
        """
        Step 1 of Wise transfer — create a quote.
        The quote locks in the rate for 30 minutes.
        """
        if not self._is_configured():
            return {"id": f"MOCK-QUOTE-{source_amount}", "mock": True}

        try:
            response = httpx.post(
                f"{self.base_url}/v3/profiles/{self.profile_id}/quotes",
                headers=self.headers,
                json={
                    "sourceCurrency": source_currency,
                    "targetCurrency": target_currency,
                    "sourceAmount": float(source_amount),
                    "profile": self.profile_id
                },
                timeout=15.0
            )
            return response.json()
        except Exception as e:
            return {"error": str(e), "mock": True}

    def create_recipient(
        self,
        account_number: str,
        account_name: str,
        bank_code: str,
        currency: str,
        country: str
    ) -> dict:
        """
        Step 2 of Wise transfer — create or find recipient.
        """
        if not self._is_configured():
            return {
                "id": f"MOCK-RECIPIENT-{account_number}",
                "mock": True
            }

        # Split account name into first and last
        name_parts = account_name.strip().split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else first_name

        payload = {
            "profile": self.profile_id,
            "accountHolderName": account_name,
            "currency": currency,
            "type": "sort_code" if currency == "GBP" else "iban",
            "details": {
                "legalType": "PRIVATE",
                "firstName": first_name,
                "lastName": last_name,
                "accountNumber": account_number,
                "bankCode": bank_code,
                "address": {
                    "country": country,
                }
            }
        }

        try:
            response = httpx.post(
                f"{self.base_url}/v1/accounts",
                headers=self.headers,
                json=payload,
                timeout=15.0
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}

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
        Full Wise transfer flow:
        1. Create quote
        2. Create recipient
        3. Create transfer
        4. Fund transfer
        """
        if not self._is_configured():
            return TransferResult(
                success=True,
                provider_reference=f"WISE-MOCK-{reference}",
                status="processing",
                message=(
                    "Wire transfer initiated via Wise (sandbox). "
                    "No real money moved."
                ),
                estimated_delivery="Same day if before 3PM EST, "
                                   "otherwise next business day",
                raw_response={"mock": True}
            )

        try:
            # Step 1 — Quote
            quote = self.create_quote("USD", currency, amount)
            if "error" in quote:
                raise Exception(f"Quote failed: {quote['error']}")

            quote_id = quote.get("id")

            # Step 2 — Recipient
            recipient = self.create_recipient(
                account_number=account_number,
                account_name=account_name,
                bank_code=bank_code,
                currency=currency,
                country=bank_code[:2] if len(bank_code) >= 2 else "NG"
            )
            recipient_id = recipient.get("id")

            # Step 3 — Transfer
            transfer_response = httpx.post(
                f"{self.base_url}/v1/transfers",
                headers=self.headers,
                json={
                    "targetAccount": recipient_id,
                    "quoteUuid": quote_id,
                    "customerTransactionId": reference,
                    "details": {
                        "reference": narration,
                        "transferPurpose": "verification.transfers.purpose.pay.bills",
                        "sourceOfFunds": "verification.source.of.funds.salary"
                    }
                },
                timeout=30.0
            )
            transfer_data = transfer_response.json()
            transfer_id = transfer_data.get("id")

            # Step 4 — Fund the transfer
            fund_response = httpx.post(
                f"{self.base_url}/v3/profiles/{self.profile_id}"
                f"/transfers/{transfer_id}/payments",
                headers=self.headers,
                json={"type": "BALANCE"},
                timeout=30.0
            )
            fund_data = fund_response.json()

            return TransferResult(
                success=True,
                provider_reference=str(transfer_id),
                status="processing",
                message="Wire transfer initiated via Wise",
                estimated_delivery=(
                    "Same day if initiated before 3PM EST, "
                    "otherwise next business day"
                ),
                raw_response=fund_data
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
            return {"status": "outgoing_payment_sent", "mock": True}

        try:
            response = httpx.get(
                f"{self.base_url}/v1/transfers/{provider_reference}",
                headers=self.headers,
                timeout=10.0
            )
            return response.json()
        except Exception as e:
            return {"status": "unknown", "error": str(e)}