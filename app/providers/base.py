"""
Base provider interface.
Every payment provider must implement these methods.
This ensures all providers are interchangeable —
swapping Grey for Flutterwave is just changing one line.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from dataclasses import dataclass
from typing import Optional


@dataclass
class TransferResult:
    success: bool
    provider_reference: str
    status: str
    message: str
    estimated_delivery: str
    raw_response: dict


@dataclass
class AccountResult:
    success: bool
    account_number: str
    routing_number: str
    account_name: str
    bank_name: str
    provider_account_id: str
    raw_response: dict


class BaseProvider(ABC):

    @abstractmethod
    def initiate_transfer(
        self,
        amount: Decimal,
        account_number: str,
        account_name: str,
        bank_code: str,
        bank_name: str,
        currency: str,
        reference: str,
        narration: str
    ) -> TransferResult:
        pass

    @abstractmethod
    def verify_transfer(self, provider_reference: str) -> dict:
        pass

    @abstractmethod
    def get_banks(self, country: str) -> list:
        pass