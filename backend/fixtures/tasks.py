"""Celery tasks of the fixtures app. Celery Beat starts them (CELERY_BEAT_SCHEDULE)."""

from celery import shared_task

from . import checkpoints


@shared_task(name="fixtures.run_checkpoints")
def run_checkpoints() -> dict[str, int]:
    """The timed checkpoints: T-36h Confirmations, their resend, T-6h Reminders."""
    return checkpoints.run_due()
