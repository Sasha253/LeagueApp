"""The Fixture status state machine (PRD "Match lifecycle").

    scheduled -> confirming           T-36h: Confirmations go out (FR-1)
    confirming -> ready               T-6h: both Teams have their minimum and have paid,
                                      or the Admin let an unpaid Team play (FR-5, FR-6)
    scheduled -> ready                T-6h: the Confirmations never went out and the Admin
                                      let both Teams play
    scheduled | confirming | ready -> one_team_out
                                      one Team is out (FR-5, FR-6) or its Captain's
                                      cancellation is accepted (FR-18)
    scheduled | confirming -> both_teams_out
                                      T-6h: both Teams are out (FR-5, FR-6)
    both_teams_out -> friendly | cancelled   (FR-10, FR-17, FR-43)
    one_team_out -> replacement_offered   the slot is offered to other Teams (FR-15)
    replacement_offered -> scheduled | confirming | ready
                                      a Team accepted (FR-15): before the T-36h
                                      Confirmations, before T-6h, or after it
    any but friendly, cancelled and played -> friendly
                                      only when friendly-eligible (FR-10, FR-17)
    any but cancelled and played -> cancelled   (FR-17, FR-43)
    confirming | ready -> scheduled   an Admin reschedule restarts the process (FR-9)
    ready -> confirming               rescheduled to within the Confirmation window (FR-9)
    ready | friendly -> played

cancelled and played are final. The table below is the whole rule: the checkpoints and the
Admin actions of later chunks call transition(), and nothing else changes a status.
"""

from django.db import transaction
from django.utils import timezone

from core.exceptions import Conflict

from .models import Fixture, FixtureTransition

S = Fixture.Status

TRANSITIONS: dict[str, frozenset[str]] = {
    S.SCHEDULED: frozenset(
        {S.CONFIRMING, S.READY, S.ONE_TEAM_OUT, S.BOTH_TEAMS_OUT, S.FRIENDLY, S.CANCELLED}
    ),
    S.CONFIRMING: frozenset(
        {S.SCHEDULED, S.READY, S.ONE_TEAM_OUT, S.BOTH_TEAMS_OUT, S.FRIENDLY, S.CANCELLED}
    ),
    S.READY: frozenset(
        {S.SCHEDULED, S.CONFIRMING, S.ONE_TEAM_OUT, S.FRIENDLY, S.CANCELLED, S.PLAYED}
    ),
    S.ONE_TEAM_OUT: frozenset({S.REPLACEMENT_OFFERED, S.FRIENDLY, S.CANCELLED}),
    S.BOTH_TEAMS_OUT: frozenset({S.FRIENDLY, S.CANCELLED}),
    S.REPLACEMENT_OFFERED: frozenset({S.SCHEDULED, S.CONFIRMING, S.READY, S.FRIENDLY, S.CANCELLED}),
    S.FRIENDLY: frozenset({S.PLAYED, S.CANCELLED}),
    S.CANCELLED: frozenset(),
    S.PLAYED: frozenset(),
}

# The friendly-eligible flag can change only while the match may still fall through.
FLAG_OPEN = frozenset(
    {
        S.SCHEDULED,
        S.CONFIRMING,
        S.READY,
        S.ONE_TEAM_OUT,
        S.BOTH_TEAMS_OUT,
        S.REPLACEMENT_OFFERED,
    }
)

NOT_ALLOWED = "A {from_} Fixture can't become {to}."
NOT_FRIENDLY_ELIGIBLE = "This Fixture isn't friendly-eligible, so it can't become a friendly."
FLAG_CLOSED = "This Fixture is {status}, so whether it may become a friendly can't change now."


def lock(fixture_id: int, *related: str) -> Fixture:
    """Locks the Fixture row, then loads it with `related`. Call inside a transaction.

    The lock is taken without joins: PostgreSQL rechecks a locked row that changed while it
    waited against the joined rows it read before, so a lock joined to the Teams would find
    nothing once a replacement Team (chunk 14) had just been swapped in.
    """
    Fixture.objects.select_for_update().filter(pk=fixture_id).values_list("pk").get()
    return Fixture.objects.select_related(*related).get(pk=fixture_id)


def can_move(from_status: str, to_status: str) -> bool:
    return to_status in TRANSITIONS.get(from_status, frozenset())


def log_creation(fixture: Fixture, *, cause: str, actor=None, note: str = "") -> None:
    FixtureTransition.objects.create(
        fixture=fixture,
        from_status="",
        to_status=fixture.status,
        at=fixture.created_at or timezone.now(),
        actor=actor,
        cause=cause,
        note=note,
    )


@transaction.atomic
def transition(
    fixture: Fixture, to_status: str, *, cause: str, actor=None, note: str = ""
) -> Fixture:
    """Moves the Fixture to `to_status` and logs it. 409 when the move isn't allowed."""
    fixture = Fixture.objects.select_for_update().get(pk=fixture.pk)
    if not can_move(fixture.status, to_status):
        raise Conflict(
            NOT_ALLOWED.format(from_=S(fixture.status).label.lower(), to=S(to_status).label.lower())
        )
    if to_status == S.FRIENDLY and not fixture.friendly_eligible:
        raise Conflict(NOT_FRIENDLY_ELIGIBLE)
    FixtureTransition.objects.create(
        fixture=fixture,
        from_status=fixture.status,
        to_status=to_status,
        at=timezone.now(),
        actor=actor,
        cause=cause,
        note=note,
    )
    fixture.status = to_status
    fixture.save(update_fields=["status"])
    return fixture


@transaction.atomic
def set_friendly_eligible(fixture: Fixture, eligible: bool, admin) -> Fixture:
    fixture = Fixture.objects.select_for_update().get(pk=fixture.pk)
    if fixture.status not in FLAG_OPEN:
        raise Conflict(FLAG_CLOSED.format(status=S(fixture.status).label.lower()))
    if fixture.friendly_eligible != eligible:
        fixture.friendly_eligible = eligible
        fixture.friendly_eligible_changed_by = admin
        fixture.friendly_eligible_changed_at = timezone.now()
        fixture.save(
            update_fields=[
                "friendly_eligible",
                "friendly_eligible_changed_by",
                "friendly_eligible_changed_at",
            ]
        )
    return fixture
