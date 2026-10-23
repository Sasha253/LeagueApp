"""One Team out: finding a replacement opponent (FR-13 to FR-16; PRD "Match lifecycle").

When the T-6h readiness check settles a Fixture with one Team out (`readiness_settled`,
fixtures/readiness.py), `open_offer()`:

- moves the Fixture to `replacement_offered`;
- sends a General Notification, with "Find a match", to the out Team's Players (FR-13);
- sends an Update to the remaining Team's Players: their opponent withdrew and a new one is
  being found (FR-14);
- offers the slot to every eligible Team: its Captain gets a Confirmation-kind offer,
  answerable until `closes_at` (`replacement_close_hours_before` kick-off, from the Club's
  settings) (FR-15);
- sends an Update to the Night's Admins and the pitch's Referee (FR-16).

An eligible Team (provisional, docs/OPEN_QUESTIONS.md "Chunk 14"): active, in the same
Club, Season and Division as the match, neither of its Teams, owes nothing on the ledger
(it gets no T-6h payment check of its own, FR-6), has no other match that day (South
African date, not cancelled), and its Captain has opted into the Night (targeting rules).

The Captain's "Confirm" on the offer accepts for the Team (`accept()`). The first Team to
accept takes the out Team's place in the Fixture; any later accept gets 409. Its Players get
Confirmations (FR-15) and the remaining Team and the officials get an Update (FR-16). The
Fixture moves to `scheduled` (before the T-36h Confirmations; they go out as usual),
`confirming` (before T-6h) or `ready` (after it; the new Team's Players can answer until
kick-off, fixtures/confirmations.py).

With no eligible Team, or once `closes_at` passes with no Team accepted, the offer lapses
and `replacement_lapsed` is sent: chunk 15 turns the match into a friendly or cancels it
(FR-17). An offer whose match moved on (cancelled, rescheduled) is withdrawn. Either way the
offer Notifications close. `lapse_due()` runs with the timed checkpoints every minute.

Locks: the Fixture, then the offer Notification (notifications/services.py `answer`), then
the offer, then the accepting Team, in every path, so two accepts never both win and never
deadlock. Two different Fixtures accepted by the same Team at once: the second waits for
the first's Team lock and then sees the Team already plays that day.
"""

import logging
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import F, Q
from django.dispatch import Signal, receiver
from django.utils import timezone

from core.exceptions import Conflict
from ledger.services import team_balance
from notifications import services as notifications
from notifications import targeting
from notifications.models import Answer, Kind, Notification
from notifications.services import match_day, match_time, notification_answered
from teams.models import Team

from . import checkpoints, lifecycle
from .models import (
    Fixture,
    FixtureCheckpoint,
    FixtureTransition,
    ReplacementCandidate,
    ReplacementOffer,
)
from .readiness import readiness_settled

logger = logging.getLogger(__name__)

S = Fixture.Status
Status = ReplacementOffer.Status
Slot = ReplacementOffer.Slot

replacement_lapsed = Signal()
"""Sent when no Team accepted the slot in time (or none could be offered it). Arguments:
`fixture` (still `replacement_offered`) and `offer`. Chunk 15 connects: a friendly or a
cancellation (FR-17)."""

RELATED = ("club__settings", "division__night", "pitch", "home_team", "away_team")

TAKEN = "Another Team took this slot first."
CLOSED = "This slot closed at {day}, {time}."
MOVED_ON = "This match has moved on, so the slot can't be taken."
NOT_CAPTAIN = "Only {team}'s Captain can accept for it."
NOT_ELIGIBLE = "{team} can't take this slot: {why}."
WHY_NOT_ACTIVE = "it isn't an active Team in this Division"
WHY_OWES = "it still owes money to the club"
WHY_PLAYING = "it already has a match that day"


def _when(fixture: Fixture) -> str:
    return f"{match_day(fixture.kick_off)}, {match_time(fixture.kick_off)}, {fixture.pitch.name}"


def _day_bounds(moment: datetime) -> tuple[datetime, datetime]:
    """The South African day of `moment`, as [start, end)."""
    start = timezone.localtime(moment).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)  # South Africa has no daylight saving.


def _plays_that_day(team: Team, fixture: Fixture) -> bool:
    start, end = _day_bounds(fixture.kick_off)
    return (
        Fixture.objects.filter(Q(home_team=team) | Q(away_team=team))
        .filter(kick_off__gte=start, kick_off__lt=end)
        .exclude(status=S.CANCELLED)
        .exclude(pk=fixture.pk)
        .exists()
    )


def _why_not(team: Team, fixture: Fixture) -> str | None:
    """Why `team` can't take the Fixture's open slot, or None when it can."""
    if (
        team.status != Team.Status.ACTIVE
        or team.club_id != fixture.club_id
        or team.season_id != fixture.season_id
        or team.division_id != fixture.division_id
        or team.pk in (fixture.home_team_id, fixture.away_team_id)
    ):
        return WHY_NOT_ACTIVE
    if team_balance(team).outstanding > 0:
        return WHY_OWES
    if _plays_that_day(team, fixture):
        return WHY_PLAYING
    return None


def eligible_teams(fixture: Fixture, out_team: Team) -> list[Team]:
    """The Teams the slot can be offered to, by name. Their Captain must have opted into the
    Night to be told, so a Team whose Captain hasn't is left out."""
    teams = (
        Team.objects.filter(
            club_id=fixture.club_id,
            season_id=fixture.season_id,
            division_id=fixture.division_id,
            status=Team.Status.ACTIVE,
            captain__isnull=False,
        )
        .exclude(pk__in=[fixture.home_team_id, fixture.away_team_id, out_team.pk])
        .order_by("name", "pk")
    )
    teams = [team for team in teams if _why_not(team, fixture) is None]
    reachable = set(targeting.opted_in_captains(teams, fixture.night).values_list("pk", flat=True))
    return [team for team in teams if team.captain_id in reachable]


def _close_offer_notifications(offer: ReplacementOffer) -> None:
    notifications.close(Notification.objects.filter(replacement_candidate__offer=offer))


def _lapse(fixture: Fixture, offer: ReplacementOffer, now: datetime) -> None:
    offer.status = Status.LAPSED
    offer.ended_at = now
    offer.save(update_fields=["status", "ended_at"])
    _close_offer_notifications(offer)
    replacement_lapsed.send(sender=Fixture, fixture=fixture, offer=offer)


@transaction.atomic
def open_offer(
    fixture: Fixture, out_team: Team, *, actor=None, now: datetime | None = None
) -> ReplacementOffer:
    """One Team of the Fixture is out: tell everyone and offer the slot (FR-13 to FR-16)."""
    now = now or timezone.now()
    fixture = lifecycle.lock(fixture.pk, *RELATED)
    if out_team.pk == fixture.home_team_id:
        slot, remaining = Slot.HOME, fixture.away_team
    elif out_team.pk == fixture.away_team_id:
        slot, remaining = Slot.AWAY, fixture.home_team
    else:
        raise ValueError("The out Team isn't in this Fixture.")
    lifecycle.transition(
        fixture,
        S.REPLACEMENT_OFFERED,
        cause=FixtureTransition.Cause.ADMIN if actor else FixtureTransition.Cause.SYSTEM,
        actor=actor,
        note=f"{out_team.name} is out; the slot is offered to other Teams."[:300],
    )
    fixture.status = S.REPLACEMENT_OFFERED
    hours = fixture.club.settings.replacement_close_hours_before
    closes_at = fixture.kick_off - timedelta(hours=hours)
    offer = ReplacementOffer.objects.create(
        fixture=fixture,
        kick_off=fixture.kick_off,
        out_team=out_team,
        remaining_team=remaining,
        slot=slot,
        opened_at=now,
        closes_at=closes_at,
        status=Status.OPEN,
    )
    teams = eligible_teams(fixture, out_team) if now < closes_at else []
    club, night, when = fixture.club, fixture.night, _when(fixture)
    match = f"{fixture.home_team.name} vs {fixture.away_team.name}"

    # FR-13: the out Team's Players, with "Find a match".
    notifications.notify(
        Kind.GENERAL,
        targeting.team_players(out_team, night),
        club=club,
        title=f"{out_team.name} is out of {match}"[:120],
        body=f"{when}. Your Team can't play this match. Find a match with another Team.",
        fixture=fixture,
    )
    # FR-14: the remaining Team.
    notifications.notify(
        Kind.UPDATE,
        targeting.team_players(remaining, night),
        club=club,
        title=f"{out_team.name} withdrew"[:120],
        body=f"{when}. We're finding {remaining.name} a new opponent.",
        fixture=fixture,
    )
    # FR-15: each eligible Team's Captain; the first to accept plays.
    captains = {u.pk: u for u in targeting.opted_in_captains(teams, night)}
    for team in teams:
        (sent,) = notifications.notify(
            Kind.CONFIRMATION,
            [captains[team.captain_id]],
            club=club,
            title=f"Open slot: play {remaining.name}"[:120],
            body=f"{when}. The first Team to accept plays. Take it for {team.name}?",
            fixture=fixture,
            answer_by=closes_at,
        )
        ReplacementCandidate.objects.create(offer=offer, team=team, notification=sent)
    # FR-16: the Night's Admins and the pitch's Referee.
    if teams:
        offered = f"Offered to {len(teams)} Team{'s' if len(teams) != 1 else ''} until "
        offered += f"{match_day(closes_at)}, {match_time(closes_at)}."
    else:
        offered = "No other Team can take the slot."
    notifications.notify(
        Kind.UPDATE,
        targeting.officials(fixture),
        club=club,
        title=f"{out_team.name} is out of {match}"[:120],
        body=f"{when}. {offered}",
        fixture=fixture,
    )
    if not teams:
        _lapse(fixture, offer, now)
    return offer


@receiver(readiness_settled, dispatch_uid="fixtures.replacement_on_one_team_out")
def one_team_out(sender, fixture: Fixture, out: list, actor=None, **kwargs) -> None:
    """The T-6h check left one Team out (chunk 13): look for another opponent."""
    if len(out) == 1 and fixture.status == S.ONE_TEAM_OUT:
        open_offer(fixture, out[0], actor=actor)


def _send_confirmations(fixture: Fixture, new_team: Team, status: str, now: datetime) -> None:
    """FR-15: the new opponent's Players get Confirmations (at T-36h when still to come)."""
    club_settings = fixture.club.settings
    cutoff = checkpoints.confirmation_cutoff(fixture, club_settings)
    if status == S.SCHEDULED:
        return  # The T-36h checkpoint sends them to both Teams.
    if status == S.READY:
        recipients, answer_by = targeting.team_players(new_team, fixture.night), fixture.kick_off
    else:
        answer_by = cutoff
        first_sent = FixtureCheckpoint.objects.filter(
            fixture=fixture, kind=FixtureCheckpoint.Kind.CONFIRMATION, kick_off=fixture.kick_off
        ).exists()
        if first_sent:
            recipients = targeting.team_players(new_team, fixture.night)
        else:
            # The T-36h Confirmations never went out for this kick-off: both Teams get them.
            recipients = targeting.confirmation_recipients(fixture)
            checkpoints.claim(fixture, FixtureCheckpoint.Kind.CONFIRMATION, now, 0)
    title, body = notifications.confirmation_content(fixture)
    notifications.notify(
        Kind.CONFIRMATION,
        recipients,
        club=fixture.club,
        title=title,
        body=body,
        fixture=fixture,
        answer_by=answer_by,
    )


def _status_after_accept(fixture: Fixture, now: datetime) -> str:
    club_settings = fixture.club.settings
    opens = fixture.kick_off - timedelta(hours=club_settings.confirmation_hours_before)
    if now < opens:
        return S.SCHEDULED
    if now < checkpoints.confirmation_cutoff(fixture, club_settings):
        return S.CONFIRMING
    return S.READY


@transaction.atomic
def accept(candidate: ReplacementCandidate, captain, now: datetime | None = None) -> Fixture:
    """The candidate Team's Captain takes the slot. The first Team wins; 409 otherwise."""
    now = now or timezone.now()
    offer_id = candidate.offer_id
    fixture_id = ReplacementOffer.objects.values_list("fixture_id", flat=True).get(pk=offer_id)
    fixture = lifecycle.lock(fixture_id, *RELATED)
    offer = ReplacementOffer.objects.select_for_update(of=("self",)).get(pk=offer_id)
    team = Team.objects.select_for_update(of=("self",)).get(pk=candidate.team_id)
    if offer.status == Status.ACCEPTED:
        raise Conflict(TAKEN)
    if (
        offer.status != Status.OPEN
        or fixture.status != S.REPLACEMENT_OFFERED
        or fixture.kick_off != offer.kick_off
    ):
        raise Conflict(MOVED_ON)
    if now >= offer.closes_at:
        closed = offer.closes_at
        raise Conflict(CLOSED.format(day=match_day(closed), time=match_time(closed)))
    if team.captain_id != captain.pk:
        raise Conflict(NOT_CAPTAIN.format(team=team.name))
    why = _why_not(team, fixture)
    if why:
        raise Conflict(NOT_ELIGIBLE.format(team=team.name, why=why))

    remaining, out_team = offer.remaining_team, offer.out_team
    if offer.slot == Slot.HOME:
        fixture.home_team = team
    else:
        fixture.away_team = team
    fixture.save(update_fields=["home_team" if offer.slot == Slot.HOME else "away_team"])
    offer.status = Status.ACCEPTED
    offer.accepted_team = team
    offer.accepted_by = captain
    offer.accepted_at = now
    offer.ended_at = now
    offer.save(update_fields=["status", "accepted_team", "accepted_by", "accepted_at", "ended_at"])
    _close_offer_notifications(offer)

    to_status = _status_after_accept(fixture, now)
    lifecycle.transition(
        fixture,
        to_status,
        cause=FixtureTransition.Cause.CAPTAIN,
        actor=captain,
        note=f"{team.name} replaces {out_team.name}."[:300],
    )
    fixture.status = to_status
    _send_confirmations(fixture, team, to_status, now)

    club, night, when = fixture.club, fixture.night, _when(fixture)
    notifications.notify(
        Kind.UPDATE,
        targeting.team_players(remaining, night),
        club=club,
        title=f"New opponent: {team.name}"[:120],
        body=f"{when}. {team.name} replaces {out_team.name}.",
        fixture=fixture,
    )
    notifications.notify(
        Kind.UPDATE,
        targeting.officials(fixture),
        club=club,
        title=f"{team.name} replaces {out_team.name}"[:120],
        body=f"{fixture.home_team.name} vs {fixture.away_team.name}, {when}.",
        fixture=fixture,
    )
    return fixture


@receiver(notification_answered, dispatch_uid="fixtures.replacement_offer_answered")
def offer_answered(sender, notification: Notification, previous: str, **kwargs) -> None:
    """A Captain's "Confirm" on a replacement offer accepts for the Team (same transaction,
    so a refused accept leaves the answer unsaved). "Decline" only records the answer."""
    candidate = (
        ReplacementCandidate.objects.filter(notification_id=notification.pk)
        .select_related("offer")
        .first()
    )
    if candidate is None or notification.answer != Answer.CONFIRM:
        return
    accept(candidate, notification.recipient)


def is_offer(notification: Notification) -> bool:
    return ReplacementCandidate.objects.filter(notification_id=notification.pk).exists()


@transaction.atomic
def end_offer(offer_id: int, now: datetime | None = None) -> str | None:
    """Ends an open offer that is past its close time (lapsed) or whose match moved on
    (withdrawn). Returns the new status, or None when there was nothing to do."""
    now = now or timezone.now()
    fixture_id = ReplacementOffer.objects.values_list("fixture_id", flat=True).get(pk=offer_id)
    fixture = lifecycle.lock(fixture_id, "home_team", "away_team")
    offer = ReplacementOffer.objects.select_for_update(of=("self",)).get(pk=offer_id)
    if offer.status != Status.OPEN:
        return None
    if fixture.status != S.REPLACEMENT_OFFERED or fixture.kick_off != offer.kick_off:
        offer.status = Status.WITHDRAWN
        offer.ended_at = now
        offer.save(update_fields=["status", "ended_at"])
        _close_offer_notifications(offer)
        return Status.WITHDRAWN
    if now < offer.closes_at:
        return None
    _lapse(fixture, offer, now)
    return Status.LAPSED


def due_offers(now: datetime) -> list[int]:
    """Open offers past their close time, or whose match moved on."""
    moved_on = ~Q(fixture__status=S.REPLACEMENT_OFFERED) | ~Q(fixture__kick_off=F("kick_off"))
    return list(
        ReplacementOffer.objects.filter(status=Status.OPEN)
        .filter(Q(closes_at__lte=now) | moved_on)
        .order_by("closes_at", "pk")
        .values_list("pk", flat=True)
    )


def lapse_due(now: datetime | None = None) -> dict[str, int]:
    """Ends every offer that is due. One failing is logged and tried again next pass."""
    now = now or timezone.now()
    ended = {Status.LAPSED.value: 0, Status.WITHDRAWN.value: 0}
    for offer_id in due_offers(now):
        try:
            result = end_offer(offer_id, now)
        except Exception:
            logger.exception("Ending replacement offer %s failed", offer_id)
            continue
        if result:
            ended[result] += 1
    return ended
