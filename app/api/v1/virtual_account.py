from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/virtual-account", tags=["Virtual Account"])


class BankVerifyRequest(BaseModel):
    account_number: str
    bank_code: str = ""


@router.get("/details")
def get_account_details(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's virtual USD account details.
    Creates one automatically if it does not exist yet.
    """
    from app.models.virtual_account import VirtualAccount
    account = db.query(VirtualAccount).filter(
        VirtualAccount.user_id == current_user.id
    ).first()

    if not account:
        # Return None instead of 404 so frontend can show create button
        return None

    return {
        "account_number": account.account_number,
        "routing_number": account.routing_number,
        "bank_name": account.bank_name,
        "account_type": account.account_type,
        "account_holder_name": current_user.full_name,
        "swift_code": getattr(account, "swift_code", "WFBIUS6S"),
        "bank_address": getattr(
            account, "bank_address",
            "420 Montgomery Street, San Francisco, CA 94104"
        ),
        "status": account.status,
    }


@router.post("/create")
def create_virtual_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a USD virtual account for the user."""
    from app.models.virtual_account import VirtualAccount
    from app.services.virtual_account_service import get_or_create_virtual_account

    account = get_or_create_virtual_account(db, current_user)

    return {
        "account_number": account.account_number,
        "routing_number": account.routing_number,
        "bank_name": account.bank_name,
        "account_type": account.account_type,
        "account_holder_name": current_user.full_name,
        "swift_code": getattr(account, "swift_code", "WFBIUS6S"),
        "bank_address": getattr(
            account, "bank_address",
            "420 Montgomery Street, San Francisco, CA 94104"
        ),
        "status": account.status,
    }


@router.post("/verify-bank")
def verify_bank_account_endpoint(
    data: BankVerifyRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Verify bank account using multiple providers.
    Auto-detects bank if no bank_code provided.
    """
    from app.services.account_verification_service import verify_bank_account
    result = verify_bank_account(
        data.account_number,
        data.bank_code if data.bank_code else None
    )
    result.pop("verified_by", None)
    result.pop("provider", None)
    return result