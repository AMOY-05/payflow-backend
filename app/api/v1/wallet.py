from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.schemas.wallet import WalletOut, DepositRequest, TransactionOut, TransactionListOut
from app.services.wallet_service import (
    get_wallet_balance,
    deposit_funds,
    get_transaction_history
)

router = APIRouter(prefix="/api/v1/wallet", tags=["Wallet"])


@router.get("/balance", response_model=WalletOut)
def get_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_wallet_balance(db, current_user)


@router.post("/deposit", response_model=TransactionOut)
def deposit(
    data: DepositRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return deposit_funds(db, current_user, data.amount, data.description)


@router.get("/transactions", response_model=TransactionListOut)
def get_transactions(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_transaction_history(db, current_user, limit, offset)