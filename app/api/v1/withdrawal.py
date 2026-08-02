from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.schemas.withdrawal import (
    WithdrawalRequest,
    WithdrawalOut,
    WithdrawalListOut,
    WithdrawalReceiptOut
)
from app.services.withdrawal_service import (
    initiate_withdrawal,
    get_withdrawal_history,
    get_withdrawal_by_reference,
    cancel_withdrawal
)

router = APIRouter(prefix="/api/v1/withdraw", tags=["Withdrawal"])


@router.post("/initiate", response_model=WithdrawalReceiptOut)
def initiate(
    data: WithdrawalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initiate a withdrawal to a local bank account.
    The routing engine automatically picks the best provider.
    """
    return initiate_withdrawal(db, current_user, data)


@router.get("/history", response_model=WithdrawalListOut)
def withdrawal_history(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_withdrawal_history(db, current_user, limit, offset)


@router.get("/{reference}", response_model=WithdrawalOut)
def get_withdrawal(
    reference: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_withdrawal_by_reference(db, current_user, reference)


@router.post("/cancel/{reference}")
def cancel(
    reference: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return cancel_withdrawal(db, current_user, reference)

@router.post("/simulate-complete/{reference}")
def simulate_completion(
    reference: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    FOR TESTING ONLY — simulates a completed webhook from Flutterwave.
    Remove this endpoint before going to production.
    """
    from app.models.withdrawal import Withdrawal
    withdrawal = db.query(Withdrawal).filter(
        Withdrawal.reference == reference,
        Withdrawal.user_id == current_user.id
    ).first()

    if not withdrawal:
        raise HTTPException(
            status_code=404,
            detail="Withdrawal not found"
        )

    withdrawal.status = "completed"
    withdrawal.status_message = "Transfer completed successfully (simulated)"
    db.add(withdrawal)
    db.commit()

    return {
        "message": "Withdrawal marked as completed",
        "reference": reference,
        "status": "completed"
    }

def sanitize_withdrawal_response(withdrawal_data: dict) -> dict:
    """
    Remove all third-party provider names from user-facing responses.
    Users only see PayFlow branding.
    """
    # Map internal provider names to PayFlow branded names
    provider_display = {
        "paystack":      "PayFlow Transfer",
        "flutterwave":   "PayFlow Transfer",
        "chipper_cash":  "PayFlow Express",
        "grey":          "PayFlow Transfer",
        "lemfi":         "PayFlow Transfer",
        "wise":          "PayFlow Global",
        "wire":          "PayFlow Wire",
        "ach":           "PayFlow ACH",
        "budpay":        "PayFlow Transfer",
    }

    provider = withdrawal_data.get("provider", "")
    withdrawal_data["provider"] = provider_display.get(
        provider, "PayFlow Transfer"
    )
    return withdrawal_data