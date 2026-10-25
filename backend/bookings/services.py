"""Booking a field, and deciding, cancelling and rescheduling a Booking (FR-28 to FR-31).

Rules (docs/DECISIONS.md, chunk 23, provisional):

- A club takes bookings once its Admin has set the booking hourly fee and the match length
  (`ClubSettings.takes_bookings`); both are data, never constants.
- A Booking starts on the hour (South African time), still to come, for 1 to 24 whole
  hours, and ends by midnight of the day it starts.
- It may not overlap a pending or accepted Booking of the same Field, nor a Fixture on that
  Field that isn't cancelled (a Fixture holds its pitch for the club's match length from
  kick-off). The Field's row is locked while checking, so two requests can't take one slot.
- Every Admin of the club gets a Booking Notification (Confirm / Decline) on a request or a
  reschedule; answering it, or deciding on the club's bookings screen, accepts or declines
  it. Once decided, every Admin's Notification for it closes.
- Accepting issues the Booking User's Barcode (FR-30). Cancelling or rescheduling revokes
  it; a reschedule waits for an Admin again.
- Payment is taken at the club's payment cutoff (FR-34, `take_due_payments`, on Celery
  Beat): the Booking User's credit first (FR-46), then they are asked to pay the rest by
  card on the gateway's page, or to the club in cash (an Admin records it, FR-44).
- What a cancellation or reschedule costs is the club's policy (bookings/policy.py):
  what comes back is credit, never cash. An Admin can cancel for the club.

Locks are taken in one order everywhere: Booking, then Field, then Notifications.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import DurationField, ExpressionWrapper, F
from django.dispatch import receiver
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import User
from clubs.models import Club, ClubSettings, Field
from core.exceptions import Conflict
from fixtures.models import Fixture
from ledger import services as ledger
from notifications import targeting
from notifications.models import Answer, Kind, Notification
from notifications.services import close, match_day, match_time, notification_answered, notify

from . import money, policy
from .models import MOST_HOURS, Booking, BookingEvent

S = Booking.Status
E = BookingEvent.Kind

NOT_TAKING = "This club isn't taking bookings yet."
ON_THE_HOUR = "Bookings start on the hour."
IN_THE_PAST = "Pick a time that is still to come."
PAST_MIDNIGHT = "A booking must end by midnight."
TAKEN = "This field is already taken for some of that time. Pick another time or field."
CLASHES_WITH_MATCH = "A league match is on this field for some of that time."
NOTHING_CHANGED = "Pick a different field, time or number of hours."
STARTED = "This booking has already started."
ADMINS_ONLY = "Only an Admin of this club can decide a booking."
REASON_NEEDED = "Give a reason. The Booking User is told."
TOO_FAR = "A late move must start by {latest}."
NOT_DUE = "Payment for this booking isn't due yet."
NOTHING_OWED = "This booking has nothing left to pay."
NOT_ACCEPTED = "Only an accepted booking is paid for."
MORE_THAN_OWED = "That is more than the booking still owes."


def _now() -> dt.datetime:
    return timezone.now()


def day_bounds(date: dt.date) -> tuple[dt.datetime, dt.datetime]:
    """Midnight to midnight of a South African date, as aware datetimes."""
    start = timezone.make_aware(dt.datetime.combine(date, dt.time()))
    return start, timezone.make_aware(dt.datetime.combine(date + dt.timedelta(days=1), dt.time()))


def match_length(club_settings: ClubSettings) -> dt.timedelta:
    return dt.timedelta(minutes=club_settings.match_length_minutes)


def _settings(club: Club) -> ClubSettings:
    club_settings = ClubSettings.objects.get(club_id=club.pk)
    if not club_settings.takes_bookings:
        raise Conflict(NOT_TAKING)
    return club_settings


def _ends_at(starts_at: dt.datetime, hours: int) -> dt.datetime:
    return starts_at + dt.timedelta(hours=hours)


def check_slot(starts_at: dt.datetime, hours: int, now: dt.datetime | None = None) -> None:
    """The time rules for a Booking's slot. ValidationError naming the field at fault."""
    now = now or _now()
    local = timezone.localtime(starts_at)
    if local.minute or local.second or local.microsecond:
        raise ValidationError({"starts_at": [ON_THE_HOUR]})
    if starts_at <= now:
        raise ValidationError({"starts_at": [IN_THE_PAST]})
    if not 1 <= hours <= MOST_HOURS:
        raise ValidationError({"hours": [f"Book 1 to {MOST_HOURS} hours."]})
    if _ends_at(starts_at, hours) > day_bounds(local.date())[1]:
        raise ValidationError({"hours": [PAST_MIDNIGHT]})


def clashing_bookings(field: Field, starts_at, ends_at, exclude: Booking | None = None):
    found = Booking.objects.filter(
        field=field,
        status__in=Booking.HOLDS_FIELD,
        starts_at__lt=ends_at,
        ends_at__gt=starts_at,
    )
    return found.exclude(pk=exclude.pk) if exclude is not None else found


def clashing_fixtures(field: Field, starts_at, ends_at, club_settings: ClubSettings):
    """Fixtures on `field` that aren't cancelled and hold it for part of the time."""
    return Fixture.objects.filter(
        pitch=field,
        kick_off__lt=ends_at,
        kick_off__gt=starts_at - match_length(club_settings),
    ).exclude(status=Fixture.Status.CANCELLED)


def _check_free(field, starts_at, ends_at, club_settings, exclude=None) -> None:
    if clashing_fixtures(field, starts_at, ends_at, club_settings).exists():
        raise Conflict(CLASHES_WITH_MATCH)
    if clashing_bookings(field, starts_at, ends_at, exclude).exists():
        raise Conflict(TAKEN)


# Availability (FR-28)


@dataclass(frozen=True)
class FieldSlots:
    field: Field
    starts: list[dt.datetime]


@dataclass(frozen=True)
class Availability:
    date: dt.date
    hours: int
    hourly_fee: Decimal
    price: Decimal
    fields: list[FieldSlots]


def availability(
    club: Club, date: dt.date, hours: int, *, exclude: Booking | None = None
) -> Availability:
    """Every start time on `date` (South African) when each of the club's Fields is free
    for `hours`: on the hour, still to come, ending by midnight, clashing with no pending
    or accepted Booking (but `exclude`, the one being rescheduled) and no Fixture."""
    club_settings = _settings(club)
    if not 1 <= hours <= MOST_HOURS:
        raise ValidationError({"hours": [f"Book 1 to {MOST_HOURS} hours."]})
    day_start, day_end = day_bounds(date)
    now = _now()
    length = match_length(club_settings)
    fields = list(Field.objects.filter(club=club).order_by("name", "pk"))
    busy: dict[int, list[tuple[dt.datetime, dt.datetime]]] = {f.pk: [] for f in fields}
    bookings = Booking.objects.filter(
        club=club,
        status__in=Booking.HOLDS_FIELD,
        starts_at__lt=day_end,
        ends_at__gt=day_start,
    )
    if exclude is not None:
        bookings = bookings.exclude(pk=exclude.pk)
    for start, end, field_id in bookings.values_list("starts_at", "ends_at", "field_id"):
        busy[field_id].append((start, end))
    fixtures = Fixture.objects.filter(
        club=club, kick_off__lt=day_end, kick_off__gt=day_start - length
    ).exclude(status=Fixture.Status.CANCELLED)
    for kick_off, field_id in fixtures.values_list("kick_off", "pitch_id"):
        if field_id in busy:
            busy[field_id].append((kick_off, kick_off + length))

    result = []
    for field in fields:
        starts = []
        for hour in range(0, 24 - hours + 1):
            start = timezone.make_aware(dt.datetime.combine(date, dt.time(hour)))
            end = _ends_at(start, hours)
            if start <= now or end > day_end:
                continue
            if any(b_start < end and b_end > start for b_start, b_end in busy[field.pk]):
                continue
            starts.append(start)
        result.append(FieldSlots(field, starts))
    # A reschedule keeps the hourly fee the Booking was requested at (see `reschedule`),
    # so the price shown is the one it will cost.
    fee = exclude.hourly_fee if exclude is not None else club_settings.booking_hourly_fee
    return Availability(date, hours, fee, money.price(fee, hours), result)


# Telling people


def slot_text(booking: Booking) -> str:
    """ "Tue 27 Oct, 18:00 to 20:00 (2 hours)" """
    hours = "1 hour" if booking.hours == 1 else f"{booking.hours} hours"
    return (
        f"{match_day(booking.starts_at)}, {match_time(booking.starts_at)} to "
        f"{match_time(booking.ends_at)} ({hours})"
    )


def _admin_notifications(booking: Booking):
    return Notification.objects.filter(booking=booking, kind=Kind.BOOKING)


def _ask_admins(booking: Booking, *, rescheduled: bool) -> None:
    """FR-29: a Booking Notification to every Admin of the club, answerable until it starts."""
    what = "Booking moved" if rescheduled else "Booking request"
    notify(
        Kind.BOOKING,
        targeting.booking_recipients(booking.club),
        club=booking.club,
        title=f"{what}: {booking.field.name}",
        body=(
            f"{booking.user.name}, {slot_text(booking)}, {money.rand(booking.price)}. "
            "Confirm or decline."
        ),
        booking=booking,
        answer_by=booking.starts_at,
    )


def _tell_user(booking: Booking, title: str, body: str) -> None:
    notify(Kind.UPDATE, [booking.user], club=booking.club, title=title, body=body, booking=booking)


def _tell_admins(booking: Booking, title: str, body: str) -> None:
    notify(
        Kind.UPDATE,
        targeting.booking_recipients(booking.club),
        club=booking.club,
        title=title,
        body=body,
        booking=booking,
    )


def _log(booking: Booking, kind: str, actor: User | None, note: str = "", window: str = "") -> None:
    BookingEvent.objects.create(
        booking=booking,
        kind=kind,
        at=_now(),
        actor=actor,
        field=booking.field,
        starts_at=booking.starts_at,
        hours=booking.hours,
        note=note[:300],
        window=window,
    )


def _return_credit(booking: Booking, amount: Decimal, reason: str, by: User | None) -> None:
    if amount > 0:
        ledger.return_booking_payments(booking, amount, reason=reason, recorded_by=by)


def _close_pending_payments(booking: Booking) -> None:
    """Card payments not yet made for it can't be made any more. One the gateway confirms
    anyway comes back in full as credit (payments.services)."""
    from payments.models import Payment  # payments imports this app's models.

    booking.payments.filter(status=Payment.Status.PENDING).update(status=Payment.Status.CANCELLED)


def _sentence(text: str) -> str:
    return text if text.endswith((".", "!", "?")) else f"{text}."


def _credit_line(credit: Decimal) -> str:
    return f" {money.rand(credit)} is back as credit." if credit > 0 else ""


def _lock(booking: Booking) -> Booking:
    return (
        Booking.objects.select_for_update(of=("self",))
        .select_related("club", "field", "user")
        .get(pk=booking.pk)
    )


def _lock_field(field: Field) -> Field:
    return Field.objects.select_for_update().get(pk=field.pk)


# Booking User


@transaction.atomic
def request(*, user: User, club: Club, field: Field, starts_at: dt.datetime, hours: int):
    """FR-28: a Booking User asks for `field` from `starts_at` for `hours`. It waits for an
    Admin; every Admin of the club is asked."""
    if field.club_id != club.pk:
        raise ValidationError({"field": ["Pick one of this club's fields."]})
    club_settings = _settings(club)
    field = _lock_field(field)
    check_slot(starts_at, hours)
    ends_at = _ends_at(starts_at, hours)
    _check_free(field, starts_at, ends_at, club_settings)
    fee = club_settings.booking_hourly_fee
    booking = Booking.objects.create(
        club=club,
        field=field,
        user=user,
        starts_at=starts_at,
        hours=hours,
        ends_at=ends_at,
        hourly_fee=fee,
        price=money.price(fee, hours),
        status=S.PENDING,
    )
    _log(booking, E.REQUESTED, user)
    _ask_admins(booking, rescheduled=False)
    return booking


def _still_open(booking: Booking, doing: str) -> None:
    if not booking.holds_field:
        raise Conflict(f"This booking is {booking.status}, so it can't be {doing}.")
    if booking.starts_at <= _now():
        raise Conflict(STARTED)


def _revoke_barcode(booking: Booking, by: User, reason: str) -> None:
    from barcodes import services as barcodes  # barcodes imports this app's models.

    barcodes.revoke_for_booking(booking, by=by, reason=reason)


@transaction.atomic
def cancel(booking: Booking, *, by: User) -> Booking:
    """FR-31: the Booking User cancels before it starts. The Barcode no longer counts.
    The club's policy decides how much of what was paid comes back as credit."""
    booking = _lock(booking)
    _still_open(booking, "cancelled")
    outcome = policy.cancel_outcome(booking)
    was_accepted = booking.status == S.ACCEPTED
    booking.status = S.CANCELLED
    booking.cancelled_at = _now()
    booking.save(update_fields=["status", "cancelled_at"])
    _log(booking, E.CANCELLED, by, outcome.summary, window=outcome.window)
    _revoke_barcode(booking, by, "The booking was cancelled.")
    _close_pending_payments(booking)
    _return_credit(booking, outcome.credit, f"Booking cancelled, {slot_text(booking)}", by)
    close(_admin_notifications(booking))
    if outcome.paid > 0:
        _tell_user(booking, f"Booking cancelled: {booking.field.name}", outcome.summary)
    if was_accepted:
        _tell_admins(
            booking,
            f"Booking cancelled: {booking.field.name}",
            f"{booking.user.name} cancelled {slot_text(booking)}.",
        )
    return booking


@transaction.atomic
def club_cancel(booking: Booking, *, by: User, reason: str) -> Booking:
    """The club cancels (pitch, weather, operational; the policy's last row): an Admin of
    the club, before it ends, with a reason. The club's percent of what was paid comes
    back as credit, and the Booking User is told why."""
    booking = _lock(booking)
    if not is_admin(by, booking.club_id):
        raise Conflict("Only an Admin of this club can cancel it for the club.")
    reason = (reason or "").strip()[:300]
    if not reason:
        raise ValidationError({"reason": [REASON_NEEDED]})
    outcome = policy.cancel_outcome(booking, by_club=True)
    if not outcome.allowed:
        raise Conflict(f"This booking is {booking.status}, so it can't be cancelled.")
    booking.status = S.CANCELLED
    booking.cancelled_at = _now()
    booking.cancelled_by_club = True
    booking.save(update_fields=["status", "cancelled_at", "cancelled_by_club"])
    _log(booking, E.CLUB_CANCELLED, by, reason, window=policy.Window.CLUB)
    _revoke_barcode(booking, by, "The club cancelled the booking.")
    _close_pending_payments(booking)
    _return_credit(booking, outcome.credit, f"The club cancelled: {reason}", by)
    close(_admin_notifications(booking))
    _tell_user(
        booking,
        f"The club cancelled your booking: {booking.field.name}",
        f"{slot_text(booking)}. {_sentence(reason)}{_credit_line(outcome.credit)}",
    )
    return booking


@transaction.atomic
def reschedule(
    booking: Booking, *, by: User, field: Field, starts_at: dt.datetime, hours: int
) -> Booking:
    """FR-31: the Booking User moves it to another time, field or number of hours of the
    same club. It waits for an Admin again, and the Barcode no longer counts until then.
    The price is the hourly fee it was booked at times the new hours."""
    booking = _lock(booking)
    _still_open(booking, "rescheduled")
    if field.club_id != booking.club_id:
        raise ValidationError({"field": ["Pick one of this club's fields."]})
    club_settings = _settings(booking.club)
    if (field.pk, starts_at, hours) == (booking.field_id, booking.starts_at, booking.hours):
        raise ValidationError({"starts_at": [NOTHING_CHANGED]})
    outcome = policy.reschedule_outcome(booking)
    if not outcome.allowed:
        raise Conflict(outcome.summary)
    if outcome.latest_start is not None and starts_at > outcome.latest_start:
        latest = f"{match_day(outcome.latest_start)}, {match_time(outcome.latest_start)}"
        raise ValidationError({"starts_at": [TOO_FAR.format(latest=latest)]})
    field = _lock_field(field)
    check_slot(starts_at, hours)
    ends_at = _ends_at(starts_at, hours)
    _check_free(field, starts_at, ends_at, club_settings, exclude=booking)
    was_accepted = booking.status == S.ACCEPTED
    booking.field = field
    booking.starts_at = starts_at
    booking.hours = hours
    booking.ends_at = ends_at
    booking.price = money.price(booking.hourly_fee, hours)
    booking.status = S.PENDING
    booking.decided_at = None
    booking.decided_by = None
    booking.payment_requested_at = None  # Taken again at the new slot's cutoff if owed.
    booking.save(
        update_fields=[
            "field",
            "starts_at",
            "hours",
            "ends_at",
            "price",
            "status",
            "decided_at",
            "decided_by",
            "payment_requested_at",
        ]
    )
    _log(booking, E.RESCHEDULED, by, outcome.summary, window=outcome.window)
    _close_pending_payments(booking)
    # Moved to fewer hours: what was paid over the new price comes back as credit.
    over = money.paid(booking) - booking.price
    _return_credit(booking, over, f"Booking moved to {slot_text(booking)}", by)
    if was_accepted:
        _revoke_barcode(booking, by, "The booking was rescheduled.")
    close(_admin_notifications(booking))
    _ask_admins(booking, rescheduled=True)
    return booking


# Admin


def is_admin(user: User, club_id: int) -> bool:
    return user.is_club_admin(club_id)


@transaction.atomic
def accept(booking: Booking, *, by: User) -> Booking:
    """FR-29, FR-30: an Admin of the club accepts a waiting Booking that is still to come
    and still clashes with nothing. The Booking User gets the Barcode."""
    from barcodes import services as barcodes

    booking = _lock(booking)
    if not is_admin(by, booking.club_id):
        raise Conflict(ADMINS_ONLY)
    if booking.status != S.PENDING:
        raise Conflict(f"This booking is {booking.status}, so it can't be accepted.")
    if booking.starts_at <= _now():
        raise Conflict(STARTED)
    club_settings = _settings(booking.club)
    _check_free(booking.field, booking.starts_at, booking.ends_at, club_settings, exclude=booking)
    booking.status = S.ACCEPTED
    booking.decided_at = _now()
    booking.decided_by = by
    booking.decline_reason = ""
    booking.save(update_fields=["status", "decided_at", "decided_by", "decline_reason"])
    _log(booking, E.ACCEPTED, by)
    close(_admin_notifications(booking))
    barcodes.issue_for_booking(booking)
    _tell_user(
        booking,
        f"Booking accepted: {booking.field.name}",
        f"{slot_text(booking)}. Your Barcode for the gate is in My bookings.",
    )
    return booking


@transaction.atomic
def decline(booking: Booking, *, by: User, reason: str = "") -> Booking:
    """FR-29: an Admin of the club declines a waiting Booking. The field is free again."""
    booking = _lock(booking)
    if not is_admin(by, booking.club_id):
        raise Conflict(ADMINS_ONLY)
    if booking.status != S.PENDING:
        raise Conflict(f"This booking is {booking.status}, so it can't be declined.")
    reason = reason.strip()[:300]
    outcome = policy.cancel_outcome(booking, by_club=True)  # Paid before a reschedule.
    booking.status = S.DECLINED
    booking.decided_at = _now()
    booking.decided_by = by
    booking.decline_reason = reason
    booking.save(update_fields=["status", "decided_at", "decided_by", "decline_reason"])
    _log(booking, E.DECLINED, by, reason, window=policy.Window.CLUB if outcome.paid else "")
    _close_pending_payments(booking)
    _return_credit(booking, outcome.credit, f"Booking declined, {slot_text(booking)}", by)
    close(_admin_notifications(booking))
    body = f"{slot_text(booking)}." + (f" {_sentence(reason)}" if reason else "")
    body += _credit_line(outcome.credit)
    _tell_user(booking, f"Booking declined: {booking.field.name}", body)
    return booking


@receiver(notification_answered, dispatch_uid="bookings.booking_answered")
def booking_answered(sender, notification: Notification, previous: str, **kwargs) -> None:
    """Answering a Booking Notification decides the Booking (same transaction)."""
    if notification.kind != Kind.BOOKING or notification.booking_id is None:
        return
    booking = notification.booking
    if notification.answer == Answer.CONFIRM:
        accept(booking, by=notification.recipient)
    else:
        decline(booking, by=notification.recipient)


# Payment (FR-33, FR-34, FR-44, FR-46)


def _card_options(club: Club) -> tuple[bool, Decimal | None]:
    from payments import services as payments  # payments imports this app's models.

    return payments.club_card_options(club)


def can_pay_in_app(booking: Booking) -> bool:
    """The Booking User can pay what is left in the app now: payment is due, and their
    credit covers it or the club takes cards for what credit leaves (the same rules as
    payments.services.start_booking_payment). Otherwise they pay the club in cash."""
    if (
        booking.status != S.ACCEPTED
        or booking.payment_requested_at is None
        or booking.ends_at <= _now()
    ):
        return False
    owed = money.outstanding(booking)
    if owed <= 0:
        return False
    if ledger.booking_credit(booking.club, booking.user) >= owed:
        return True
    card_enabled, minimum = _card_options(booking.club)
    return card_enabled and owed >= minimum


def due_for_payment(now: dt.datetime | None = None):
    """Accepted Bookings still to come whose payment cutoff has passed and whose payment
    hasn't been taken for their current slot."""
    now = now or _now()
    cutoff = ExpressionWrapper(
        F("club__settings__booking_payment_cutoff_hours") * dt.timedelta(hours=1),
        output_field=DurationField(),
    )
    return (
        Booking.objects.filter(
            status=S.ACCEPTED, payment_requested_at__isnull=True, starts_at__gt=now
        )
        .alias(due_at=F("starts_at") - cutoff)
        .filter(due_at__lte=now)
    )


def _credit_to_spend(owed: Decimal, held: Decimal, club: Club) -> Decimal:
    """Credit first (FR-46), but leave at least the gateway's smallest card amount for
    the card, so what is left can still be paid by card."""
    spend = min(held, owed)
    card_enabled, minimum = _card_options(club)
    if card_enabled and 0 < owed - spend < minimum:
        spend = max(owed - minimum, Decimal("0.00"))
    return spend


@transaction.atomic
def take_payment(booking: Booking) -> bool:
    """FR-34: at the club's payment cutoff, the Booking User's credit at the club pays
    first (FR-46); they are asked to pay the rest by card in the app, or to the club in
    cash. From now on cancelling is never free (the policy). Once per slot."""
    booking = _lock(booking)
    now = _now()
    if (
        booking.status != S.ACCEPTED
        or booking.payment_requested_at is not None
        or booking.starts_at <= now
        or now < policy.payment_due_at(booking)
    ):
        return False
    owed = money.outstanding(booking)
    spent = Decimal("0.00")
    if owed > 0:
        held = ledger.booking_credit(booking.club, booking.user)
        spent = _credit_to_spend(owed, held, booking.club)
        if spent > 0:
            ledger.spend_booking_credit(
                booking=booking,
                amount=spent,
                spent_by=None,
                reason=f"Credit towards the booking, {slot_text(booking)}",
            )
    booking.payment_requested_at = now
    booking.payment_taken_at = booking.payment_taken_at or now
    booking.save(update_fields=["payment_requested_at", "payment_taken_at"])
    left = money.outstanding(booking)
    from_credit = f" {money.rand(spent)} came from your credit." if spent > 0 else ""
    _log(booking, E.PAYMENT_DUE, None, f"Owed {money.rand(owed)}.{from_credit}")
    if left > 0:
        card_enabled, minimum = _card_options(booking.club)
        if card_enabled and left >= minimum:
            how = f"Pay {money.rand(left)} by card in My bookings before you play."
        else:
            how = f"Pay {money.rand(left)} to the club before you play."
        _tell_user(
            booking,
            f"Payment due: {booking.field.name}",
            f"{slot_text(booking)}.{from_credit} {how}",
        )
    elif spent > 0:
        _tell_user(
            booking,
            f"Booking paid: {booking.field.name}",
            f"{slot_text(booking)}. Paid from your credit: {money.rand(spent)}. "
            "Your Barcode works at the gate.",
        )
    return True


def take_due_payments(now: dt.datetime | None = None) -> int:
    """Celery Beat: takes payment for every Booking whose cutoff has passed."""
    taken = 0
    for booking_id in due_for_payment(now).values_list("pk", flat=True):
        taken += take_payment(Booking(pk=booking_id))
    return taken


@transaction.atomic
def record_cash(booking: Booking, *, by: User, amount: Decimal, reason: str = ""):
    """FR-44: cash paid to the club for an accepted Booking, recorded by one of its
    Admins, up to what it still owes. The policy applies to it like any payment."""
    booking = _lock(booking)
    if not is_admin(by, booking.club_id):
        raise Conflict("Only an Admin of this club can record cash for it.")
    if booking.status != S.ACCEPTED:
        raise Conflict(NOT_ACCEPTED)
    owed = money.outstanding(booking)
    if owed <= 0:
        raise Conflict(NOTHING_OWED)
    if amount > owed:
        raise Conflict(MORE_THAN_OWED)
    return ledger.record_booking_payment(
        booking=booking,
        amount=amount,
        method=ledger.Method.CASH,
        recorded_by=by,
        reason=reason.strip() or "Cash paid to the club",
    )


def card_payment_recorded(booking: Booking, entry) -> None:
    """A card payment the gateway confirmed (payments.services, Booking locked). Money
    already taken is never lost: for a Booking cancelled or declined meanwhile it all
    comes back as credit, and anything over the price comes back as credit."""
    if not booking.holds_field:
        ledger.return_as_credit(
            entry, reason="Paid after the booking was cancelled", recorded_by=None
        )
        return
    over = money.paid(booking) - booking.price
    _return_credit(booking, over, "Paid more than the booking costs", None)


# After it ends


@transaction.atomic
def settle(booking: Booking) -> bool:
    """Once an accepted Booking has ended: never scanned in at the gate is a no-show,
    and gets the club's no-show percent of what was paid back as credit (the policy)."""
    from barcodes.models import BarcodeScan

    booking = _lock(booking)
    now = _now()
    if booking.status != S.ACCEPTED or booking.settled_at is not None or booking.ends_at > now:
        return False
    booking.settled_at = now
    booking.save(update_fields=["settled_at"])
    came = BarcodeScan.objects.filter(
        barcode__booking=booking, result=BarcodeScan.Result.PAID
    ).exists()
    if came:
        return True
    club_settings = ClubSettings.objects.get(club_id=booking.club_id)
    paid = money.paid(booking)
    percent = club_settings.booking_no_show_credit_percent
    credit = money.percent_of(paid, percent) if paid > 0 else Decimal("0.00")
    _log(booking, E.NO_SHOW, None, f"Not scanned in. Credit {money.rand(credit)}.", "very_late")
    if credit > 0:
        _return_credit(booking, credit, f"No-show, {slot_text(booking)}", None)
        _tell_user(
            booking,
            f"Missed booking: {booking.field.name}",
            f"{slot_text(booking)}. {money.rand(credit)} is back as credit ({percent}%).",
        )
    return True


def settle_ended(now: dt.datetime | None = None) -> int:
    """Celery Beat: settles every accepted Booking that has ended."""
    now = now or _now()
    ended = Booking.objects.filter(status=S.ACCEPTED, ends_at__lte=now, settled_at__isnull=True)
    return sum(settle(Booking(pk=pk)) for pk in ended.values_list("pk", flat=True))
