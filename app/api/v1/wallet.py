from decimal import Decimal
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.models.wallet import Wallet, Transaction
from app.schemas.wallet import WalletOut, TransactionOut, TransactionListOut

router = APIRouter(prefix="/api/v1/wallet", tags=["Wallet"])


@router.get("/balance", response_model=WalletOut)
def get_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.services.wallet_service import get_wallet_balance
    return get_wallet_balance(db, current_user)


@router.get("/transactions", response_model=TransactionListOut)
def get_transactions(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.services.wallet_service import get_transaction_history
    return get_transaction_history(db, current_user, limit, offset)


@router.get("/statement")
def get_statement(
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    end_date: str = Query(..., description="End date YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get transactions within a date range for financial statement."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD."
        )

    wallet = db.query(Wallet).filter(
        Wallet.user_id == current_user.id
    ).first()

    if not wallet:
        return {
            "user": {
                "full_name": current_user.full_name,
                "email": current_user.email,
                "country": current_user.country or "",
                "account_id": str(current_user.id)[:8].upper(),
            },
            "period": {"start_date": start_date, "end_date": end_date},
            "summary": {
                "opening_balance": "0.00",
                "closing_balance": "0.00",
                "total_credits": "0.00",
                "total_debits": "0.00",
                "total_fees": "0.00",
                "transaction_count": 0,
            },
            "transactions": []
        }

    transactions = db.query(Transaction).filter(
        and_(
            Transaction.wallet_id == wallet.id,
            Transaction.created_at >= start,
            Transaction.created_at <= end
        )
    ).order_by(Transaction.created_at.asc()).all()

    first_tx = transactions[0] if transactions else None
    opening_balance = first_tx.balance_before if first_tx else wallet.balance

    total_credits = sum(
        t.amount for t in transactions if t.transaction_type == "credit"
    )
    total_debits = sum(
        t.amount for t in transactions if t.transaction_type == "debit"
    )

    from app.models.withdrawal import Withdrawal
    withdrawals_in_period = db.query(Withdrawal).filter(
        and_(
            Withdrawal.user_id == current_user.id,
            Withdrawal.created_at >= start,
            Withdrawal.created_at <= end,
            Withdrawal.status == "completed"
        )
    ).all()
    total_fees = sum(w.fee for w in withdrawals_in_period)

    closing_balance = (
        transactions[-1].balance_after if transactions else wallet.balance
    )

    return {
        "user": {
            "full_name": current_user.full_name,
            "email": current_user.email,
            "country": current_user.country or "",
            "account_id": str(current_user.id)[:8].upper(),
        },
        "period": {"start_date": start_date, "end_date": end_date},
        "summary": {
            "opening_balance": str(opening_balance),
            "closing_balance": str(closing_balance),
            "total_credits": str(total_credits),
            "total_debits": str(total_debits),
            "total_fees": str(total_fees),
            "transaction_count": len(transactions),
        },
        "transactions": [
            {
                "id": str(t.id),
                "date": t.created_at.isoformat(),
                "type": t.transaction_type,
                "category": t.category,
                "description": t.description,
                "amount": str(t.amount),
                "balance_before": str(t.balance_before),
                "balance_after": str(t.balance_after),
                "reference": t.reference,
                "status": t.status,
            }
            for t in transactions
        ]
    }


# Admin-only deposit endpoint — not accessible to regular users
@router.post("/admin-deposit", include_in_schema=False)
def admin_deposit(
    amount: float,
    user_id: str,
    description: str = "Admin credit",
    x_admin_key: str = None,
    db: Session = Depends(get_db)
):
    """
    Admin-only endpoint to credit a user wallet.
    Used when real payment is received via webhook.
    Hidden from API docs.
    """
    from app.core.config import settings
    if x_admin_key != settings.ADMIN_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized"
        )
    from app.models.user import User as UserModel
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    from app.services.wallet_service import deposit_funds
    from decimal import Decimal
    return deposit_funds(db, user, Decimal(str(amount)), description)