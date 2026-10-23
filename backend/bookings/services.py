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
- What a cancellation or late reschedule costs (the policy) is chunk 24.

Locks are taken in one order everywhere: Booking, then Field, then Notifications.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.dispatch import receiver
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import ClubRole, User
from clubs.models import Club, ClubSettings, Field
from core.exceptions import Conflict
from fixtures.models import Fixture
from notifications import targeting
from notifications.models import Answer, Kind, Notification
from notifications.services import close, match_day, match_time, notification_answered, notify

from . import money
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
    fee = club_settings.booking_hourly_fee
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


def _log(booking: Booking, kind: str, actor: User | None, note: str = "") -> None:
    BookingEvent.objects.create(
        booking=booking,
        kind=kind,
        at=_now(),
        actor=actor,
        field=booking.field,
        starts_at=booking.starts_at,
        hours=booking.hours,
        note=note[:300],
    )


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
    What it costs (the policy) comes with chunk 24."""
    booking = _lock(booking)
    _still_open(booking, "cancelled")
    was_accepted = booking.status == S.ACCEPTED
    booking.status = S.CANCELLED
    booking.cancelled_at = _now()
    booking.save(update_fields=["status", "cancelled_at"])
    _log(booking, E.CANCELLED, by)
    _revoke_barcode(booking, by, "The booking was cancelled.")
    close(_admin_notifications(booking))
    if was_accepted:
        _tell_admins(
            booking,
            f"Booking cancelled: {booking.field.name}",
            f"{booking.user.name} cancelled {slot_text(booking)}.",
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
        ]
    )
    _log(booking, E.RESCHEDULED, by)
    if was_accepted:
        _revoke_barcode(booking, by, "The booking was rescheduled.")
    close(_admin_notifications(booking))
    _ask_admins(booking, rescheduled=True)
    return booking


# Admin


def is_admin(user: User, club_id: int) -> bool:
    return user.club_roles.filter(club_id=club_id, role=ClubRole.Role.ADMIN).exists()


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
    booking.status = S.DECLINED
    booking.decided_at = _now()
    booking.decided_by = by
    booking.decline_reason = reason
    booking.save(update_fields=["status", "decided_at", "decided_by", "decline_reason"])
    _log(booking, E.DECLINED, by, reason)
    close(_admin_notifications(booking))
    body = slot_text(booking) + (f". {reason}" if reason else ".")
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
