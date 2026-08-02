from decimal import Decimal
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.models.wallet import Wallet, Transaction
from app.schemas.wallet import WalletOut, DepositRequest, TransactionOut, TransactionListOut

router = APIRouter(prefix="/api/v1/wallet", tags=["Wallet"])


@router.get("/balance", response_model=WalletOut)
def get_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.services.wallet_service import get_wallet_balance
    return get_wallet_balance(db, current_user)


@router.post("/deposit", response_model=TransactionOut)
def deposit(
    data: DepositRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.services.wallet_service import deposit_funds
    return deposit_funds(db, current_user, data.amount, data.description)


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
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all transactions within a date range for financial statement.
    Returns raw data — PDF is generated on the frontend.
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )
    except ValueError:
        from fastapi import HTTPException, status
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
                "country": current_user.country,
                "account_id": str(current_user.id)[:8].upper(),
            },
            "period": {
                "start_date": start_date,
                "end_date": end_date,
            },
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

    # Get transactions in range
    transactions = db.query(Transaction).filter(
        and_(
            Transaction.wallet_id == wallet.id,
            Transaction.created_at >= start,
            Transaction.created_at <= end
        )
    ).order_by(Transaction.created_at.asc()).all()

    # Get opening balance (balance before start date)
    first_tx_in_range = transactions[0] if transactions else None
    opening_balance = Decimal("0.00")

    if first_tx_in_range:
        opening_balance = first_tx_in_range.balance_before
    else:
        opening_balance = wallet.balance

    # Calculate totals
    total_credits = sum(
        t.amount for t in transactions
        if t.transaction_type == "credit"
    )
    total_debits = sum(
        t.amount for t in transactions
        if t.transaction_type == "debit"
    )

    # Get fees from withdrawals in this period
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
        transactions[-1].balance_after
        if transactions
        else wallet.balance
    )

    return {
        "user": {
            "full_name": current_user.full_name,
            "email": current_user.email,
            "country": current_user.country or "",
            "account_id": str(current_user.id)[:8].upper(),
        },
        "period": {
            "start_date": start_date,
            "end_date": end_date,
        },
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