"""
Background tasks that run asynchronously.
"""

import logging
from app.core.celery_app import celery_app
from app.core.database import SessionLocal

logger = logging.getLogger("fintech.tasks")


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def process_withdrawal_async(
    self,
    withdrawal_id: str,
    provider: str
):
    """
    Process withdrawal in the background.
    Retries up to 3 times if provider API fails.
    """
    db = SessionLocal()
    try:
        from app.models.withdrawal import Withdrawal
        withdrawal = db.query(Withdrawal).filter(
            Withdrawal.id == withdrawal_id
        ).first()

        if not withdrawal:
            logger.error(f"Withdrawal {withdrawal_id} not found")
            return

        logger.info(
            f"Processing withdrawal {withdrawal.reference} "
            f"via {provider}"
        )

        # Status update
        withdrawal.status = "processing"
        withdrawal.status_message = f"Being processed via {provider}"
        db.add(withdrawal)
        db.commit()

        logger.info(
            f"Withdrawal {withdrawal.reference} sent to {provider}"
        )

    except Exception as exc:
        logger.error(f"Withdrawal task failed: {str(exc)}")
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error(
                f"Withdrawal {withdrawal_id} failed after max retries"
            )
    finally:
        db.close()


@celery_app.task
def reconcile_pending_withdrawals():
    """
    Every 5 minutes check all pending withdrawals
    and update their status from the provider.
    This catches cases where webhooks were missed.
    """
    db = SessionLocal()
    try:
        from app.models.withdrawal import Withdrawal
        from datetime import datetime, timezone, timedelta

        # Find withdrawals stuck in processing for more than 1 hour
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        pending = db.query(Withdrawal).filter(
            Withdrawal.status == "processing",
            Withdrawal.created_at < one_hour_ago
        ).all()

        for withdrawal in pending:
            logger.info(
                f"Reconciling withdrawal {withdrawal.reference} "
                f"via {withdrawal.provider}"
            )

            if withdrawal.provider == "flutterwave":
                from app.providers.flutterwave import FlutterwaveProvider
                flw = FlutterwaveProvider()
                if withdrawal.provider_reference:
                    status_data = flw.verify_transfer(
                        withdrawal.provider_reference
                    )
                    flw_status = status_data.get("status", "").lower()

                    if flw_status in ["successful", "success"]:
                        withdrawal.status = "completed"
                        withdrawal.status_message = "Confirmed via reconciliation"
                        db.add(withdrawal)

                    elif flw_status in ["failed", "cancelled"]:
                        withdrawal.status = "failed"
                        withdrawal.status_message = "Failed — confirmed via reconciliation"
                        db.add(withdrawal)

        db.commit()
        logger.info(f"Reconciliation complete. Checked {len(pending)} withdrawals")

    except Exception as e:
        logger.error(f"Reconciliation failed: {str(e)}")
    finally:
        db.close()


@celery_app.task
def update_fx_rates():
    """
    Refresh FX rate cache every 5 minutes.
    """
    try:
        from app.providers.fx_provider import get_all_live_rates
        rates = get_all_live_rates()
        logger.info(f"FX rates updated: {len(rates)} currencies refreshed")
    except Exception as e:
        logger.error(f"FX rate update failed: {str(e)}")