"""
Webhook handlers for payment providers.

Webhooks are HTTP POST requests that providers send to your server
when a payment event happens — transfer completed, failed, etc.

Security: Every webhook must be verified with a signature
before processing. Never trust webhook data without verification.
"""

import hmac
import hashlib
import json
import logging
from fastapi import APIRouter, Request, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.config import settings
from app.models.withdrawal import Withdrawal
from app.models.wallet import Wallet, Transaction
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks"])


def verify_flutterwave_signature(
    payload: bytes,
    signature: str,
    secret: str
) -> bool:
    """
    Verify that the webhook actually came from Flutterwave.
    Without this check, anyone could fake a payment confirmation.
    """
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/flutterwave")
async def flutterwave_webhook(
    request: Request,
    db: Session = Depends(get_db),
    verif_hash: Optional[str] = Header(None, alias="verif-hash")
):
    """
    Receive payment event notifications from Flutterwave.

    Events we handle:
    - transfer.completed → mark withdrawal as completed
    - transfer.failed → mark withdrawal as failed, refund wallet
    """
    payload = await request.body()

    # Verify webhook signature if secret is configured
    if settings.FLUTTERWAVE_WEBHOOK_SECRET:
        if not verif_hash or verif_hash != settings.FLUTTERWAVE_WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        data = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event = data.get("event")
    event_data = data.get("data", {})

    if event == "transfer.completed":
        await handle_transfer_completed(db, event_data)

    elif event == "transfer.failed":
        await handle_transfer_failed(db, event_data)

    # Always return 200 to Flutterwave even if we don't handle the event
    # Otherwise Flutterwave will keep retrying
    return {"status": "received"}


async def handle_transfer_completed(db: Session, data: dict):
    """Mark withdrawal as completed when Flutterwave confirms success."""
    reference = data.get("reference", "")

    withdrawal = db.query(Withdrawal).filter(
        Withdrawal.reference == reference
    ).first()

    if not withdrawal:
        return

    if withdrawal.status == "completed":
        return  # Already processed — idempotency check

    withdrawal.status = "completed"
    withdrawal.status_message = "Transfer completed successfully by Flutterwave"
    withdrawal.provider_reference = str(data.get("id", ""))
    db.add(withdrawal)
    db.commit()


async def handle_transfer_failed(db: Session, data: dict):
    """
    Mark withdrawal as failed and refund the wallet.
    This is critical — never leave money in limbo.
    """
    reference = data.get("reference", "")

    withdrawal = db.query(Withdrawal).filter(
        Withdrawal.reference == reference
    ).first()

    if not withdrawal:
        return

    if withdrawal.status in ["completed", "cancelled"]:
        return  # Do not process already settled withdrawals

    # Mark as failed
    withdrawal.status = "failed"
    withdrawal.status_message = (
        f"Transfer failed: {data.get('complete_message', 'Unknown error')}"
    )
    db.add(withdrawal)

    # Refund wallet
    wallet = db.query(Wallet).filter(
        Wallet.id == withdrawal.wallet_id
    ).first()

    if wallet:
        balance_before = wallet.balance
        wallet.balance = balance_before + withdrawal.amount
        db.add(wallet)

        # Record refund transaction
        refund_tx = Transaction(
            wallet_id=wallet.id,
            transaction_type="credit",
            amount=withdrawal.amount,
            balance_before=balance_before,
            balance_after=wallet.balance,
            category="refund",
            description=(
                f"Automatic refund for failed withdrawal {reference}"
            ),
            reference=f"RFD-{uuid.uuid4().hex.upper()[:16]}",
            status="success"
        )
        db.add(refund_tx)

    db.commit()


@router.post("/grey")
async def grey_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Receive payment notifications from Grey.
    Grey sends webhooks when USD funds arrive in a virtual account.
    In Phase 9 this credits the user's wallet automatically.
    """
    payload = await request.body()

    try:
        data = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = data.get("event")

    if event == "collection.successful":
        await handle_grey_collection(db, data)

    return {"status": "received"}


async def handle_grey_collection(db: Session, data: dict):
    """
    Credit user wallet when money arrives in their Grey virtual account.
    This is the webhook that makes your platform truly automatic.
    """
    # In real integration:
    # 1. Find user by virtual account number
    # 2. Credit their wallet
    # 3. Send notification
    # For now we log it — full implementation comes with Grey API access
    print(f"Grey collection received: {data}")

@router.post("/paystack")
async def paystack_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle Paystack transfer webhook events.
    Paystack sends events when transfers complete or fail.
    """
    import hmac
    import hashlib

    payload = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

    # Verify webhook signature
    paystack_secret = settings.PAYSTACK_SECRET_KEY
    expected = hmac.new(
        paystack_secret.encode(),
        payload,
        hashlib.sha512
    ).hexdigest()

    if signature != expected:
        logger.warning("Invalid Paystack webhook signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    data = await request.json()
    event = data.get("event", "")
    event_data = data.get("data", {})
    reference = event_data.get("reference", "")

    logger.info(f"Paystack webhook: {event} for {reference}")

    if event == "transfer.success":
        withdrawal = db.query(Withdrawal).filter(
            Withdrawal.reference == reference
        ).first()
        if withdrawal:
            withdrawal.status = "completed"
            db.add(withdrawal)
            db.commit()
            logger.info(f"Paystack transfer completed: {reference}")

    elif event == "transfer.failed":
        withdrawal = db.query(Withdrawal).filter(
            Withdrawal.reference == reference
        ).first()
        if withdrawal:
            withdrawal.status = "failed"
            db.add(withdrawal)
            db.commit()
            logger.warning(f"Paystack transfer failed: {reference}")

    return {"status": "ok"}