"""The booking cancellation and refund policy (PRD policy table, FR-44, FR-45).

Every number comes from the club's settings (NFR Configurability); nothing here is a
default. The windows, counted back from the Booking's start:

- free: before the payment cutoff (`booking_payment_cutoff_hours`) and before payment was
  ever taken for it. Cancel: nothing charged (anything paid early, e.g. cash, comes back
  in full as credit). Reschedule: free.
- late: from the cutoff (or once payment was taken) to `booking_late_cancel_hours` before.
  Cancel: `booking_late_cancel_credit_percent` of what was paid back as credit.
  Reschedule: free, `booking_reschedules_allowed` times, to a slot starting within
  `booking_reschedule_window_days` days of the current start.
- very_late: under the late-cancel hours, until it starts. Cancel:
  `booking_no_show_credit_percent` of what was paid as credit. Reschedule: not allowed.
  A no-show (ended, never scanned in) gets the same percent (services.settle_no_shows).
- club: an Admin cancels for the club. `booking_club_cancel_credit_percent` of what was
  paid back as credit.

Value comes back as credit, never cash (the policy). Credit is spent before card on the
next booking (FR-46).
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from django.db import models
from django.utils import timezone

from clubs.models import ClubSettings

from . import money
from .models import Booking, BookingEvent


class Window(models.TextChoices):
    FREE = "free", "Before payment is taken"
    LATE = "late", "After payment is taken"
    VERY_LATE = "very_late", "Close to the start"
    STARTED = "started", "Started"
    CLUB = "club", "The club cancels"


POLICY_WINDOWS = Window  # One name for the enum in the OpenAPI schema.


def _hours(n: int) -> dt.timedelta:
    return dt.timedelta(hours=n)


def _settings(booking: Booking) -> ClubSettings:
    return ClubSettings.objects.get(club_id=booking.club_id)


def payment_due_at(booking: Booking, club_settings: ClubSettings | None = None) -> dt.datetime:
    """When payment is taken for the Booking's current slot (FR-34)."""
    club_settings = club_settings or _settings(booking)
    return booking.starts_at - _hours(club_settings.booking_payment_cutoff_hours)


def late_cancel_at(booking: Booking, club_settings: ClubSettings | None = None) -> dt.datetime:
    club_settings = club_settings or _settings(booking)
    return booking.starts_at - _hours(club_settings.booking_late_cancel_hours)


def window(
    booking: Booking, now: dt.datetime | None = None, club_settings: ClubSettings | None = None
) -> str:
    now = now or timezone.now()
    club_settings = club_settings or _settings(booking)
    if now >= booking.starts_at:
        return Window.STARTED
    if now < payment_due_at(booking, club_settings) and booking.payment_taken_at is None:
        return Window.FREE
    if now < late_cancel_at(booking, club_settings):
        return Window.LATE
    return Window.VERY_LATE


def credit_percent(window_: str, club_settings: ClubSettings) -> int:
    return {
        Window.FREE: 100,  # Free: nothing is kept.
        Window.LATE: club_settings.booking_late_cancel_credit_percent,
        Window.VERY_LATE: club_settings.booking_no_show_credit_percent,
        Window.CLUB: club_settings.booking_club_cancel_credit_percent,
    }.get(window_, 0)


@dataclass(frozen=True)
class CancelOutcome:
    window: str
    allowed: bool
    paid: Decimal
    credit_percent: int
    credit: Decimal
    kept: Decimal
    summary: str


def _credit_text(percent: int) -> str:
    if percent <= 0:
        return "No credit"
    return f"{percent}% back as credit"


def cancel_outcome(
    booking: Booking, *, by_club: bool = False, now: dt.datetime | None = None
) -> CancelOutcome:
    """What cancelling the Booking now would return as credit and what the club keeps."""
    now = now or timezone.now()
    club_settings = _settings(booking)
    current = Window.CLUB if by_club else window(booking, now, club_settings)
    if by_club:  # The club can cancel until it ends (a pitch or weather problem).
        allowed = booking.holds_field and booking.ends_at > now
    else:
        allowed = booking.holds_field and current != Window.STARTED
    paid = money.paid(booking)
    percent = credit_percent(current, club_settings)
    credit = money.percent_of(paid, percent) if paid > 0 else Decimal("0.00")
    kept = paid - credit
    if not allowed:
        summary = "This booking can't be cancelled now."
    elif current == Window.FREE and paid <= 0:
        summary = "Cancelling now is free. Nothing is charged."
    elif paid <= 0:
        summary = "Nothing has been paid, so nothing is charged or returned."
    elif credit <= 0:
        summary = f"You have paid {money.rand(paid)}. Cancelling now returns no credit."
    elif kept <= 0:
        summary = f"You get all {money.rand(paid)} you paid back as credit."
    else:
        summary = (
            f"You get {money.rand(credit)} of the {money.rand(paid)} you paid back as credit "
            f"({percent}%). The club keeps {money.rand(kept)}."
        )
    return CancelOutcome(current, allowed, paid, percent, credit, kept, summary)


def late_reschedules_used(booking: Booking) -> int:
    return booking.events.filter(kind=BookingEvent.Kind.RESCHEDULED, window=Window.LATE).count()


@dataclass(frozen=True)
class RescheduleOutcome:
    window: str
    allowed: bool
    reschedules_left: int | None
    latest_start: dt.datetime | None
    summary: str


def reschedule_outcome(booking: Booking, now: dt.datetime | None = None) -> RescheduleOutcome:
    """Whether the Booking can be moved now, how often still, and how far."""
    club_settings = _settings(booking)
    current = window(booking, now, club_settings)
    if not booking.holds_field or current == Window.STARTED:
        return RescheduleOutcome(current, False, None, None, "This booking can't be moved now.")
    if current == Window.FREE:
        return RescheduleOutcome(current, True, None, None, "Moving it now is free.")
    if current == Window.VERY_LATE:
        hours = club_settings.booking_late_cancel_hours
        return RescheduleOutcome(
            current, False, 0, None, f"It can't be moved less than {hours} hours before it starts."
        )
    left = max(club_settings.booking_reschedules_allowed - late_reschedules_used(booking), 0)
    if left == 0:
        return RescheduleOutcome(
            current, False, 0, None, "It has been moved as often as the club allows."
        )
    days = club_settings.booking_reschedule_window_days
    latest = booking.starts_at + dt.timedelta(days=days)
    times = "once more" if left == 1 else f"{left} more times"
    return RescheduleOutcome(
        current,
        True,
        left,
        latest,
        f"You can move it for free {times}, to a time starting within {days} days of it.",
    )


@dataclass(frozen=True)
class PolicyRow:
    window: str
    when: str
    cancel: str
    reschedule: str


def _times(n: int) -> str:
    return {1: "once", 2: "twice"}.get(n, f"{n} times")


def rows(club_settings: ClubSettings) -> list[PolicyRow]:
    """The club's policy table, as the PRD lays it out (FR-45)."""
    cutoff = club_settings.booking_payment_cutoff_hours
    late = club_settings.booking_late_cancel_hours
    allowed = club_settings.booking_reschedules_allowed
    days = club_settings.booking_reschedule_window_days
    found = [
        PolicyRow(
            Window.FREE,
            f"Before payment is taken ({cutoff}h before)",
            "Free; nothing charged",
            "Free",
        )
    ]
    if late < cutoff:
        found.append(
            PolicyRow(
                Window.LATE,
                f"{cutoff}h to {late}h before",
                _credit_text(club_settings.booking_late_cancel_credit_percent),
                f"Free, {_times(allowed)}, to a slot within {days} days"
                if allowed
                else "Not allowed",
            )
        )
    found.append(
        PolicyRow(
            Window.VERY_LATE,
            f"Under {min(late, cutoff)}h before, or no-show",
            _credit_text(club_settings.booking_no_show_credit_percent),
            "Not allowed",
        )
    )
    found.append(
        PolicyRow(
            Window.CLUB,
            "The club cancels (pitch, weather, operational)",
            _credit_text(club_settings.booking_club_cancel_credit_percent)
            + ". Ask the club about a card refund.",
            "Free",
        )
    )
    return found
