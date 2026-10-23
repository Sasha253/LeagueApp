"""Celery tasks of the fixtures app. Celery Beat starts them (CELERY_BEAT_SCHEDULE)."""

from celery import shared_task

from . import checkpoints, replacements


@shared_task(name="fixtures.run_checkpoints")
def run_checkpoints() -> dict[str, int]:
    """The timed checkpoints: T-36h Confirmations, their resend, the T-6h readiness check
    and Reminders; then replacement offers that closed with no Team (chunk 14)."""
    ran = checkpoints.run_due()
    ended = replacements.lapse_due()
    return {**ran, **{f"replacement_{status}": count for status, count in ended.items()}}
