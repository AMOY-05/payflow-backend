"""
Celery background task queue.

Why Celery for a fintech app:
- Withdrawal processing should not block the HTTP response
- Webhook processing should be async and retryable
- Sending notifications, reconciliation, and reports
  should run in the background
- If a provider API is slow, the user should not wait
"""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "fintech",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Retry failed tasks automatically
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Task time limits
    task_soft_time_limit=60,    # warn after 60 seconds
    task_time_limit=120,        # kill after 2 minutes

    # Beat schedule for periodic tasks
    beat_schedule={
        "reconcile-pending-withdrawals": {
            "task": "app.tasks.reconcile_pending_withdrawals",
            "schedule": 300.0,  # every 5 minutes
        },
        "update-fx-rates": {
            "task": "app.tasks.update_fx_rates",
            "schedule": 300.0,  # every 5 minutes
        },
    }
)