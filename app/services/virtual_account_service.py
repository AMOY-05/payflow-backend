import random
import string
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.virtual_account import VirtualAccount
from app.models.user import User


def generate_account_number() -> str:
    """
    Generate a realistic-looking 10-digit US account number.
    In production this comes from the BaaS provider's API response.
    """
    return "".join([str(random.randint(0, 9)) for _ in range(10)])


def generate_routing_number() -> str:
    """
    We use Lead Bank's real routing number as the mock value.
    This is the actual routing number that will be used in Phase 9.
    """
    return "101019644"  # Lead Bank routing number


def get_or_create_virtual_account(db: Session, user: User) -> VirtualAccount:
    """
    Get existing virtual account or create a new one.
    In Phase 9 we replace the mock generation with a real API call
    to Grey or Stripe Treasury.
    """
    existing = db.query(VirtualAccount).filter(
        VirtualAccount.user_id == user.id
    ).first()

    if existing:
        return existing

    # Mock account creation
    # In Phase 9: response = grey_api.create_account(user)
    account_number = generate_account_number()

    # Make sure account number is unique
    while db.query(VirtualAccount).filter(
        VirtualAccount.account_number == account_number
    ).first():
        account_number = generate_account_number()

    virtual_account = VirtualAccount(
        user_id=user.id,
        account_number=account_number,
        routing_number=generate_routing_number(),
        account_name=user.full_name.upper(),
        bank_name="Lead Bank",
        account_type="checking",
        currency="USD",
        provider="mock",
        provider_account_id=f"MOCK-{account_number}",
        is_active=True
    )

    db.add(virtual_account)
    db.commit()
    db.refresh(virtual_account)
    return virtual_account


def get_virtual_account_details(db: Session, user: User) -> dict:
    """
    Return full account details with instructions for
    major platforms African creators use.
    """
    account = get_or_create_virtual_account(db, user)

    if not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your virtual account has been suspended. Contact support."
        )

    return {
        "account_number": account.account_number,
        "routing_number": account.routing_number,
        "account_name": account.account_name,
        "bank_name": account.bank_name,
        "account_type": account.account_type,
        "currency": account.currency,
        "swift_code": "LDBKUS44",
        "bank_address": "1801 Main Street, Kansas City, MO 64108, USA",
        "how_to_use": {
            "amazon_kdp": {
                "platform": "Amazon KDP",
                "steps": [
                    "Go to KDP → Your Account → Payment Information",
                    "Select Bank Transfer as payment method",
                    "Enter your account number and routing number above",
                    "Set currency to USD",
                    "Amazon pays on the last business day of each month"
                ]
            },
            "upwork": {
                "platform": "Upwork",
                "steps": [
                    "Go to Settings → Get Paid → Add Payment Method",
                    "Select Direct to Local Bank (ACH)",
                    "Enter routing number and account number above",
                    "Minimum withdrawal is $1"
                ]
            },
            "fiverr": {
                "platform": "Fiverr",
                "steps": [
                    "Go to Selling → Earnings → Withdraw",
                    "Select Direct Deposit",
                    "Enter your account details above",
                    "Fiverr pays within 2-5 business days"
                ]
            },
            "wire_transfer": {
                "platform": "International Wire Transfer",
                "steps": [
                    "Bank Name: Lead Bank",
                    "SWIFT/BIC: LDBKUS44",
                    f"Account Name: {account.account_name}",
                    f"Account Number: {account.account_number}",
                    f"Routing Number (ABA): {account.routing_number}",
                    "Bank Address: 1801 Main Street, Kansas City, MO 64108, USA"
                ]
            }
        }
    }