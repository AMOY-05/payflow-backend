import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.wallet import Wallet, Transaction
from app.models.withdrawal import Withdrawal
from app.models.user import User
from app.schemas.withdrawal import WithdrawalRequest
from app.services.routing_engine import get_payout_route
from app.providers.flutterwave import FlutterwaveProvider
from app.providers.flutterwave import FlutterwaveProvider
from app.providers.wise import WiseProvider
from app.providers.stripe_ach import StripeACHProvider
from app.providers.budpay import BudPayProvider


MIN_WITHDRAWAL = Decimal("5.00")
MAX_WITHDRAWAL = Decimal("50000.00")


def validate_withdrawal(db: Session, user: User, amount: Decimal) -> Wallet:
    if amount < MIN_WITHDRAWAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum withdrawal amount is ${MIN_WITHDRAWAL}"
        )
    if amount > MAX_WITHDRAWAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum withdrawal amount is ${MAX_WITHDRAWAL}"
        )

    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    if wallet.balance < amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Insufficient balance. "
                f"Your balance is ${wallet.balance:.2f} "
                f"but you tried to withdraw ${amount:.2f}."
            )
    )
    # KYC limit enforcement
    from app.services.security_service import detect_suspicious_activity
    detect_suspicious_activity(
        db=db,
        user=user,
        action="withdrawal",
        ip_address="system",
        amount=float(amount)
    )
    return wallet


def initiate_withdrawal(
    db: Session,
    user: User,
    data: WithdrawalRequest
) -> dict:
    amount = data.amount
    bank = data.bank_details

    # Step 1 — Validate
    wallet = validate_withdrawal(db, user, amount)

    # Step 2 — Get best route
    route = get_payout_route(
        amount=float(amount),
        destination_country=destination_country,
        urgent=urgent
    )

    fee = route.estimated_fee
    amount_after_fee = amount - fee

    if amount_after_fee <= Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Amount too small. After the ${fee} fee, recipient would receive nothing."
        )

    # Step 3 — Verify bank account before sending (Flutterwave)
    if route.provider == "flutterwave" and bank.bank_code:
        flw = FlutterwaveProvider()
        verification = flw.verify_account(bank.account_number, bank.bank_code)
        if not verification.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Bank account verification failed: {verification.get('message')}"
            )

    # Step 4 — Debit wallet BEFORE sending to provider
    # This is the correct order — debit first, then send
    # If provider fails we refund (see webhook handler)
    balance_before = wallet.balance
    balance_after = balance_before - amount
    wallet.balance = balance_after
    db.add(wallet)

    # Step 5 — Record wallet transaction
    reference = f"WDR-{uuid.uuid4().hex.upper()[:16]}"
    transaction = Transaction(
        wallet_id=wallet.id,
        transaction_type="debit",
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
        category="withdrawal",
        description=(
            f"Withdrawal to {bank.account_name} "
            f"({bank.bank_name}) via {route.provider.title()}"
        ),
        reference=reference,
        status="success"
    )
    db.add(transaction)

    # Step 6 — Call real provider API based on routing decision
    provider_reference = ""
    provider_status = "processing"

    from app.providers.flutterwave import FlutterwaveProvider
    from app.providers.wise import WiseProvider
    from app.providers.stripe_ach import StripeACHProvider

    # Select the right provider
    if route.provider == "flutterwave":
        provider = FlutterwaveProvider()
    elif route.provider == "wire":
        # Wise API coming soon — using Flutterwave international transfer for now
        provider = FlutterwaveProvider()
    elif route.provider == "ach":
        provider = StripeACHProvider()
    elif route.provider == "budpay":
        provider = BudPayProvider()
    elif route.provider in ["grey", "chipper_cash", "lemfi"]:
        provider = FlutterwaveProvider()
    else:
        # Default fallback
        provider = FlutterwaveProvider()

    # Execute transfer
    result = provider.initiate_transfer(
        amount=amount_after_fee,
        account_number=bank.account_number,
        account_name=bank.account_name,
        bank_code=bank.bank_code or "",
        bank_name=bank.bank_name,
        currency=bank.destination_currency,
        reference=reference,
        narration=data.narration or f"Payout to {bank.account_name}"
    )

    provider_reference = result.provider_reference
    provider_status = result.status

    if not result.success:
        # Refund wallet immediately on failure
        wallet.balance = balance_before
        db.add(wallet)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Transfer failed: {result.message}"
        )

    # Step 7 — Record withdrawal
    withdrawal = Withdrawal(
        user_id=user.id,
        wallet_id=wallet.id,
        amount=amount,
        fee=fee,
        amount_after_fee=amount_after_fee,
        currency="USD",
        provider=route.provider,
        method=route.method,
        estimated_delivery=route.estimated_delivery,
        bank_name=bank.bank_name,
        account_number=bank.account_number,
        account_name=bank.account_name,
        bank_code=bank.bank_code,
        destination_country=bank.destination_country.upper(),
        destination_currency=bank.destination_currency.upper(),
        reference=reference,
        provider_reference=provider_reference,
        status=provider_status,
        status_message=f"Transfer initiated via {route.provider.title()}"
    )
    db.add(withdrawal)
    db.commit()

    # Check for suspicious activity
    from app.services.security_service import (
        detect_suspicious_activity, log_audit_event
    )
    activity = detect_suspicious_activity(
        db=db,
        user=user,
        action="withdrawal",
        ip_address="system",
        amount=float(amount)
    )
    if activity["is_suspicious"]:
        log_audit_event(
            db,
            action="suspicious_withdrawal",
            user_id=str(user.id),
            ip_address="system",
            details={
                "amount": float(amount),
                "flags": activity["flags"]
            },
            risk_level="high"
        )

    return {
        "reference": reference,
        "status": provider_status,
        "amount": amount,
        "fee": fee,
        "amount_after_fee": amount_after_fee,
        "currency": "USD",
        "provider": route.provider,
        "estimated_delivery": route.estimated_delivery,
        "delivery_note": route.delivery_note,
        "bank_name": bank.bank_name,
        "account_number": bank.account_number,
        "account_name": bank.account_name,
        "destination_country": bank.destination_country.upper(),
        "destination_currency": bank.destination_currency.upper(),
        "created_at": withdrawal.created_at,
        "message": (
            f"Your withdrawal of ${amount:.2f} has been sent via "
            f"{route.provider.title()}. "
            f"Expected delivery: {route.estimated_delivery}. "
            f"Reference: {reference}"
        )
    }


def get_withdrawal_history(
    db: Session,
    user: User,
    limit: int = 20,
    offset: int = 0
) -> dict:
    total = db.query(Withdrawal).filter(
        Withdrawal.user_id == user.id
    ).count()

    withdrawals = db.query(Withdrawal).filter(
        Withdrawal.user_id == user.id
    ).order_by(
        Withdrawal.created_at.desc()
    ).limit(limit).offset(offset).all()

    return {"total": total, "withdrawals": withdrawals}


def get_withdrawal_by_reference(
    db: Session,
    user: User,
    reference: str
) -> Withdrawal:
    withdrawal = db.query(Withdrawal).filter(
        Withdrawal.reference == reference,
        Withdrawal.user_id == user.id
    ).first()

    if not withdrawal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Withdrawal {reference} not found"
        )
    return withdrawal


def cancel_withdrawal(
    db: Session,
    user: User,
    reference: str
) -> dict:
    withdrawal = get_withdrawal_by_reference(db, user, reference)

    if withdrawal.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel a withdrawal with status '{withdrawal.status}'"
        )

    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
    balance_before = wallet.balance
    wallet.balance = balance_before + withdrawal.amount
    db.add(wallet)

    refund_reference = f"RFD-{uuid.uuid4().hex.upper()[:16]}"
    transaction = Transaction(
        wallet_id=wallet.id,
        transaction_type="credit",
        amount=withdrawal.amount,
        balance_before=balance_before,
        balance_after=wallet.balance,
        category="refund",
        description=f"Refund for cancelled withdrawal {reference}",
        reference=refund_reference,
        status="success"
    )
    db.add(transaction)

    withdrawal.status = "cancelled"
    withdrawal.status_message = "Cancelled by user"
    db.add(withdrawal)
    db.commit()

    return {
        "message": f"Withdrawal cancelled. ${withdrawal.amount:.2f} refunded to wallet.",
        "refund_reference": refund_reference,
        "new_balance": wallet.balance
    }