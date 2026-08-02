from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.schemas.virtual_account import VirtualAccountOut
from app.services.virtual_account_service import (
    get_or_create_virtual_account,
    get_virtual_account_details
)
from app.providers.flutterwave import FlutterwaveProvider

router = APIRouter(prefix="/api/v1/virtual-account", tags=["Virtual Account"])

class BankVerifyRequest(BaseModel):
    account_number: str
    bank_code: str = ""  # Optional — empty means auto-detect


@router.post("/verify-bank")
def verify_bank_account_endpoint(
    data: BankVerifyRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Verify bank account.
    If bank_code is empty, automatically detects the bank.
    Never exposes which payment provider was used.
    """
    from app.services.account_verification_service import verify_bank_account
    result = verify_bank_account(
        data.account_number,
        data.bank_code if data.bank_code else None
    )

    # Strip provider info — never expose to frontend
    result.pop("verified_by", None)
    result.pop("provider", None)

    return result