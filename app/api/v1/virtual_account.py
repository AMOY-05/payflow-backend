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
    bank_code: str

@router.post("/verify-bank")
def verify_bank_account(
    data: BankVerifyRequest,
    current_user: User = Depends(get_current_user),
):
    flw = FlutterwaveProvider()
    result = flw.verify_account(data.account_number, data.bank_code)
    return result

@router.post("/create", response_model=VirtualAccountOut)
def create_virtual_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a virtual USD account for the user.
    Safe to call multiple times — returns existing account if already created.
    """
    account = get_or_create_virtual_account(db, current_user)
    return account


@router.get("/details")
def get_account_details(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get full account details with platform-specific instructions
    for Amazon KDP, Upwork, Fiverr, and wire transfers.
    """
    return get_virtual_account_details(db, current_user)