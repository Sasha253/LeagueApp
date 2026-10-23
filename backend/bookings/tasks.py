"""Celery tasks of the bookings app. Celery Beat starts them (CELERY_BEAT_SCHEDULE)."""

from celery import shared_task

from . import services


@shared_task(name="bookings.run_payments")
def run_payments() -> dict[str, int]:
    """Takes payment for Bookings past the club's payment cutoff (FR-34), then settles
    the ones that have ended (no-show credit, the policy)."""
    return {"taken": services.take_due_payments(), "settled": services.settle_ended()}
