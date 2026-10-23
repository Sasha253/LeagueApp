"""The timed checkpoints (PRD "Confirmation and readiness"; FR-1, FR-2, FR-4).

Celery Beat starts `run_due()` every minute (fixtures/tasks.py). Each pass looks at every
Club's own hours (ClubSettings, FR-42) and runs whatever is due:

- Confirmation, `confirmation_hours_before` kick-off (T-36h): a `scheduled` Fixture moves
  to `confirming`, and every Player of both Teams gets a Confirmation they can answer
  until the cutoff, `readiness_hours_before` kick-off (T-6h, FR-3).
- Resend, `confirmation_resend_after_hours` after the Confirmation went out: the same
  Confirmation is pushed again to the Players of both Teams who haven't answered. Once.
- Readiness, `readiness_hours_before` kick-off (T-6h): each Team below its Division's
  minimum is out, and each unpaid Team waits for the Admin (FR-5, FR-6). See
  fixtures/readiness.py. Runs before the Reminder in the same pass, so a match that is out
  isn't reminded.
- Reminder, `readiness_hours_before` kick-off (T-6h): Players and Captains of both Teams,
  the Night's Admins and the pitch's Referee.

Exactly once: each run locks its Fixture and claims a FixtureCheckpoint row in the same
transaction; the row is unique per Fixture, kind and kick-off, so a second run (a duplicate
task, two workers, a retry) finds it and does nothing. A rolled-back run claims nothing and
notifies no one, and the next pass tries again.

Late: a checkpoint missed while Beat or the worker was down runs on the next pass, while it
still makes sense: a Confirmation or resend only before the T-6h cutoff (it couldn't be
answered after), the readiness check and a Reminder only before kick-off. A Fixture that
missed its Confirmation altogether stays `scheduled`, and at T-6h both its Teams wait for
the Admin.
"""

import logging
from collections import Counter
from datetime import datetime, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from clubs.models import ClubSettings
from notifications import services as notifications
from notifications import targeting
from notifications.models import Kind, Notification

from . import lifecycle
from .models import Fixture, FixtureCheckpoint, FixtureTransition

logger = logging.getLogger(__name__)

S = Fixture.Status
Checkpoint = FixtureCheckpoint.Kind

# A Reminder goes only to a match that may still be played as a league match. A Fixture
# that is out, offered to a replacement, a friendly, cancelled or played is told by the
# chunk that moved it there.
REMINDER_STATUSES = (S.SCHEDULED, S.CONFIRMING, S.READY)

# The readiness check runs on a match still on its way to being played (fixtures/readiness.py).
READINESS_STATUSES = (S.SCHEDULED, S.CONFIRMING)


def _hours(value: int) -> timedelta:
    return timedelta(hours=value)


def confirmation_cutoff(fixture: Fixture, club_settings: ClubSettings) -> datetime:
    """T-6h: Confirmations can be answered until then (FR-3)."""
    return fixture.kick_off - _hours(club_settings.readiness_hours_before)


def _done(kind: str):
    return Exists(
        FixtureCheckpoint.objects.filter(
            fixture=OuterRef("pk"), kind=kind, kick_off=OuterRef("kick_off")
        )
    )


def due(club_settings: ClubSettings, now: datetime) -> dict[str, list[int]]:
    """The ids of this Club's Fixtures each checkpoint is due for now."""
    fixtures = Fixture.objects.filter(club_id=club_settings.club_id)
    cutoff = now + _hours(club_settings.readiness_hours_before)
    first_sent = FixtureCheckpoint.objects.filter(
        fixture=OuterRef("pk"),
        kind=Checkpoint.CONFIRMATION,
        kick_off=OuterRef("kick_off"),
        ran_at__lte=now - _hours(club_settings.confirmation_resend_after_hours),
    )

    def ids(queryset) -> list[int]:
        return list(queryset.order_by("kick_off", "pk").values_list("pk", flat=True))

    return {
        Checkpoint.CONFIRMATION: ids(
            fixtures.filter(
                status=S.SCHEDULED,
                kick_off__gt=cutoff,
                kick_off__lte=now + _hours(club_settings.confirmation_hours_before),
            ).exclude(_done(Checkpoint.CONFIRMATION))
        ),
        Checkpoint.RESEND: ids(
            fixtures.filter(status=S.CONFIRMING, kick_off__gt=cutoff)
            .filter(Exists(first_sent))
            .exclude(_done(Checkpoint.RESEND))
        ),
        # Before the Reminder: run_due() runs the kinds in this order.
        Checkpoint.READINESS: ids(
            fixtures.filter(
                status__in=READINESS_STATUSES, kick_off__gt=now, kick_off__lte=cutoff
            ).exclude(_done(Checkpoint.READINESS))
        ),
        Checkpoint.REMINDER: ids(
            fixtures.filter(
                status__in=REMINDER_STATUSES, kick_off__gt=now, kick_off__lte=cutoff
            ).exclude(_done(Checkpoint.REMINDER))
        ),
    }


def claim(fixture: Fixture, kind: str, now: datetime, notified: int) -> bool:
    """Records that this checkpoint ran. False when it already had (exactly once)."""
    try:
        with transaction.atomic():
            FixtureCheckpoint.objects.create(
                fixture=fixture, kind=kind, kick_off=fixture.kick_off, ran_at=now, notified=notified
            )
    except IntegrityError:
        return False
    return True


def _locked(fixture_id: int) -> tuple[Fixture, ClubSettings]:
    fixture = lifecycle.lock(
        fixture_id, "home_team", "away_team", "pitch", "division__night", "club__settings"
    )
    return fixture, fixture.club.settings


@transaction.atomic
def send_confirmations(fixture_id: int, now: datetime | None = None) -> bool:
    """T-36h (FR-1). True when it ran now; False when not due or it already ran."""
    now = now or timezone.now()
    fixture, club_settings = _locked(fixture_id)
    cutoff = confirmation_cutoff(fixture, club_settings)
    opens = fixture.kick_off - _hours(club_settings.confirmation_hours_before)
    if fixture.status != S.SCHEDULED or not opens <= now < cutoff:
        return False
    recipients = list(targeting.confirmation_recipients(fixture))
    if not claim(fixture, Checkpoint.CONFIRMATION, now, len(recipients)):
        return False
    lifecycle.transition(
        fixture,
        S.CONFIRMING,
        cause=FixtureTransition.Cause.CHECKPOINT,
        note=f"T-{club_settings.confirmation_hours_before}h: Confirmations sent.",
    )
    title, body = notifications.confirmation_content(fixture)
    notifications.notify(
        Kind.CONFIRMATION,
        recipients,
        club=fixture.club,
        title=title,
        body=body,
        fixture=fixture,
        answer_by=cutoff,
    )
    return True


@transaction.atomic
def resend_confirmations(fixture_id: int, now: datetime | None = None) -> bool:
    """FR-2: once, to the Players of both Teams who haven't answered yet."""
    now = now or timezone.now()
    fixture, club_settings = _locked(fixture_id)
    first = FixtureCheckpoint.objects.filter(
        fixture=fixture, kind=Checkpoint.CONFIRMATION, kick_off=fixture.kick_off
    ).first()
    if (
        fixture.status != S.CONFIRMING
        or first is None
        or now < first.ran_at + _hours(club_settings.confirmation_resend_after_hours)
        or now >= confirmation_cutoff(fixture, club_settings)
    ):
        return False
    unanswered = Notification.objects.filter(
        fixture=fixture,
        kind=Kind.CONFIRMATION,
        created_at__gte=first.ran_at,
        answer="",
        closed_at__isnull=True,
        answer_by__gt=now,
        recipient__in=targeting.confirmation_recipients(fixture),
    )
    # Locked, so a Player answering at this moment is either seen as answered or answers
    # after the resend; never pushed again (and shown unread) just after answering.
    ids = list(unanswered.select_for_update(of=("self",)).values_list("pk", flat=True))
    if not claim(fixture, Checkpoint.RESEND, now, len(ids)):
        return False
    notifications.resend(Notification.objects.filter(pk__in=ids))
    return True


@transaction.atomic
def check_readiness(fixture_id: int, now: datetime | None = None) -> bool:
    """T-6h (FR-5, FR-6): who is out, and who waits for the Admin. fixtures/readiness.py."""
    # Imported here: readiness counts answers with fixtures.confirmations, which imports this.
    from . import readiness

    now = now or timezone.now()
    fixture, club_settings = _locked(fixture_id)
    if fixture.status not in READINESS_STATUSES or not (
        confirmation_cutoff(fixture, club_settings) <= now < fixture.kick_off
    ):
        return False
    if not claim(fixture, Checkpoint.READINESS, now, 0):
        return False
    readiness.assess(fixture, now)
    return True


@transaction.atomic
def send_reminders(fixture_id: int, now: datetime | None = None) -> bool:
    """T-6h (FR-4): date, time and field."""
    now = now or timezone.now()
    fixture, club_settings = _locked(fixture_id)
    if fixture.status not in REMINDER_STATUSES or not (
        confirmation_cutoff(fixture, club_settings) <= now < fixture.kick_off
    ):
        return False
    recipients = list(targeting.reminder_recipients(fixture))
    if not claim(fixture, Checkpoint.REMINDER, now, len(recipients)):
        return False
    title, body = notifications.reminder_content(fixture)
    notifications.notify(
        Kind.REMINDER, recipients, club=fixture.club, title=title, body=body, fixture=fixture
    )
    return True


RUNNERS = {
    Checkpoint.CONFIRMATION: send_confirmations,
    Checkpoint.RESEND: resend_confirmations,
    Checkpoint.READINESS: check_readiness,
    Checkpoint.REMINDER: send_reminders,
}


def run_due(now: datetime | None = None) -> dict[str, int]:
    """Runs every checkpoint that is due, for every Club. Returns how many ran, by kind.

    One Fixture failing is logged and never stops the rest; it is tried again next pass.
    """
    ran: Counter[str] = Counter()
    for club_settings in ClubSettings.objects.order_by("club_id"):
        for kind, fixture_ids in due(club_settings, now or timezone.now()).items():
            for fixture_id in fixture_ids:
                try:
                    # Each run checks the time again, so a long pass never acts on a stale clock.
                    if RUNNERS[kind](fixture_id, now):
                        ran[kind] += 1
                except Exception:
                    logger.exception("Checkpoint %s failed for Fixture %s", kind, fixture_id)
    return {kind: ran[kind] for kind in Checkpoint.values}
