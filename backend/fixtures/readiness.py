"""The T-6h readiness check (FR-5, FR-6) and the Admin's rulings on the Teams it queues.

The T-6h checkpoint (fixtures/checkpoints.py `check_readiness`) calls `assess()` once per
Fixture and kick-off, at the cutoff, before the Reminder. For each Team of the match:

- Fewer Players confirmed than the Division's minimum (ConfirmationAnswer, chunk 12): the
  Team is out (FR-5). Decided by the check; no one rules on it.
- Otherwise, if the Team still owes anything on the ledger (chunk 8): it waits for the
  Admin, who rules it in (for example cash at the gate) or out (FR-6). Nothing decides
  this automatically, however long it waits.
- Otherwise it plays.

A Fixture still `scheduled` at T-6h never had its Confirmations go out, so no one could
answer: both Teams wait for the Admin instead of being ruled out by a count no one could
change.

Once no Team is waiting, the Fixture settles: both Teams playing to `ready`, one out to
`one_team_out`, both out to `both_teams_out`. `readiness_settled` is then sent, in the same
transaction, with the Fixture and the Teams that are out; what happens next (a replacement
opponent, a friendly or a cancellation) belongs to its receivers (chunks 14 and 15).

Locks: the Fixture first, then its TeamReadiness rows, in every path.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import models, transaction
from django.db.models import Exists, OuterRef, Q
from django.dispatch import Signal
from django.utils import timezone

from core.exceptions import Conflict
from ledger.services import team_balance
from teams.models import Team

from . import lifecycle
from .confirmations import confirmed_count
from .models import Fixture, FixtureTransition, TeamReadiness

S = Fixture.Status
Outcome = TeamReadiness.Outcome
Reason = TeamReadiness.Reason

# Statuses the check runs on: a match still on its way to being played as a league match.
CHECKED_STATUSES = (S.SCHEDULED, S.CONFIRMING)

ALREADY_DECIDED = "{team} has already been ruled {outcome}."
MOVED_ON = "This match has moved on, so {team} can't be ruled on now."


class Decision(models.TextChoices):
    PLAY = "play", "Let them play"
    OUT = "out", "Rule out"


DECISIONS = {Decision.PLAY: Outcome.PLAYING, Decision.OUT: Outcome.OUT}

readiness_settled = Signal()
"""Sent when every Team of a Fixture is decided at T-6h. Arguments: `fixture` (its new
status set), `out` (the Teams that are out, home first) and `actor` (the Admin whose ruling
settled it, or None when the check did)."""


def _assess_team(fixture: Fixture, team: Team, now: datetime) -> TeamReadiness:
    confirmed = confirmed_count(fixture, team)
    minimum = fixture.division.min_players
    outstanding = team_balance(team).outstanding
    if fixture.status == S.SCHEDULED:
        outcome, reason = Outcome.PENDING, Reason.NO_REPLIES
    elif confirmed < minimum:
        outcome, reason = Outcome.OUT, Reason.SHORT
    elif outstanding > 0:
        outcome, reason = Outcome.PENDING, Reason.UNPAID
    else:
        outcome, reason = Outcome.PLAYING, Reason.NONE
    readiness, _created = TeamReadiness.objects.get_or_create(
        fixture=fixture,
        team=team,
        kick_off=fixture.kick_off,
        defaults={
            "checked_at": now,
            "confirmed": confirmed,
            "min_players": minimum,
            "outstanding": outstanding,
            "outcome": outcome,
            "reason": reason,
        },
    )
    return readiness


def assess(fixture: Fixture, now: datetime) -> list[TeamReadiness]:
    """Runs the check for a locked Fixture (called by the T-6h checkpoint, once)."""
    teams = [_assess_team(fixture, team, now) for team in (fixture.home_team, fixture.away_team)]
    _settle_if_decided(fixture, teams, actor=None)
    return teams


def current(fixture: Fixture) -> list[TeamReadiness]:
    """The Fixture's readiness for its current kick-off, home Team first."""
    rows = {
        r.team_id: r
        for r in TeamReadiness.objects.filter(fixture=fixture, kick_off=fixture.kick_off)
    }
    return [rows[t] for t in (fixture.home_team_id, fixture.away_team_id) if t in rows]


def _note(fixture: Fixture, teams: list[TeamReadiness], to_status: str) -> str:
    if to_status == S.READY:
        return "T-6h: both Teams are ready."
    parts = []
    for r in teams:
        if r.outcome != Outcome.OUT:
            continue
        name = r.team.name
        if r.reason == Reason.SHORT:
            parts.append(f"{name} below the minimum ({r.confirmed} of {r.min_players})")
        else:
            parts.append(f"{name} ruled out")
    return f"T-6h: {'; '.join(parts)}."[:300]


def _settle_if_decided(fixture: Fixture, teams: list[TeamReadiness], *, actor) -> None:
    if len(teams) != 2 or any(r.outcome == Outcome.PENDING for r in teams):
        return
    out = [r.team for r in teams if r.outcome == Outcome.OUT]
    to_status = {0: S.READY, 1: S.ONE_TEAM_OUT, 2: S.BOTH_TEAMS_OUT}[len(out)]
    moved = lifecycle.transition(
        fixture,
        to_status,
        cause=FixtureTransition.Cause.ADMIN if actor else FixtureTransition.Cause.CHECKPOINT,
        actor=actor,
        note=_note(fixture, teams, to_status),
    )
    fixture.status = moved.status
    readiness_settled.send(sender=Fixture, fixture=fixture, out=out, actor=actor)


@transaction.atomic
def decide(readiness: TeamReadiness, admin, decision: str, note: str = "") -> TeamReadiness:
    """The Admin rules a waiting Team in ("play") or out ("out"). Once; 409 otherwise."""
    if decision not in DECISIONS:
        raise Conflict(f"Decide with one of: {', '.join(DECISIONS)}.")
    fixture = (
        Fixture.objects.select_for_update(of=("self",))
        .select_related("home_team", "away_team", "division", "club")
        .get(pk=readiness.fixture_id)
    )
    readiness = (
        TeamReadiness.objects.select_for_update(of=("self",))
        .select_related("team")
        .get(pk=readiness.pk)
    )
    team = readiness.team.name
    if readiness.outcome != Outcome.PENDING:
        raise Conflict(
            ALREADY_DECIDED.format(team=team, outcome=readiness.get_outcome_display().lower())
        )
    if fixture.status not in CHECKED_STATUSES or fixture.kick_off != readiness.kick_off:
        raise Conflict(MOVED_ON.format(team=team))
    readiness.outcome = DECISIONS[decision]
    readiness.decided_by = admin
    readiness.decided_at = timezone.now()
    readiness.note = note.strip()[:300]
    readiness.save(update_fields=["outcome", "decided_by", "decided_at", "note"])
    teams = list(
        TeamReadiness.objects.select_for_update(of=("self",))
        .select_related("team")
        .filter(fixture=fixture, kick_off=fixture.kick_off)
    )
    teams.sort(key=lambda r: r.team_id != fixture.home_team_id)
    _settle_if_decided(fixture, teams, actor=admin)
    return readiness


# The Admin's Tonight queue


@dataclass
class TonightTeam:
    team: Team
    confirmed: int
    min_players: int
    due: Decimal
    paid: Decimal
    outstanding: Decimal
    readiness: TeamReadiness | None

    @property
    def below_minimum(self) -> bool:
        return self.confirmed < self.min_players

    @property
    def unpaid(self) -> bool:
        return self.outstanding > 0


@dataclass
class TonightFixture:
    fixture: Fixture
    teams: list[TonightTeam] = field(default_factory=list)

    @property
    def checked(self) -> bool:
        """The T-6h check has run for this kick-off."""
        return any(t.readiness is not None for t in self.teams)

    @property
    def waiting(self) -> bool:
        """A Team waits for the Admin's ruling, and the match can still be ruled on (once it
        has moved on, for example cancelled, `decide()` refuses, so nothing waits)."""
        return self.fixture.status in CHECKED_STATUSES and any(
            t.readiness and t.readiness.outcome == Outcome.PENDING for t in self.teams
        )

    @property
    def at_risk(self) -> bool:
        """Needs the Admin: a Team waits for a ruling, or the check is still to come and a
        Team is below the minimum or owes money."""
        if self.waiting:
            return True
        return (
            self.fixture.status in CHECKED_STATUSES
            and not self.checked
            and any(t.below_minimum or t.unpaid for t in self.teams)
        )


def tonight_fixture(fixture: Fixture) -> TonightFixture:
    rows = {r.team_id: r for r in current(fixture)}
    teams = []
    for team in (fixture.home_team, fixture.away_team):
        balance = team_balance(team)
        teams.append(
            TonightTeam(
                team=team,
                confirmed=confirmed_count(fixture, team),
                min_players=fixture.division.min_players,
                due=balance.due,
                paid=balance.paid,
                outstanding=balance.outstanding,
                readiness=rows.get(team.pk),
            )
        )
    return TonightFixture(fixture=fixture, teams=teams)


def tonight(club, now: datetime | None = None) -> list[TonightFixture]:
    """The Club's Fixtures kicking off today (South African date), and any Fixture with a
    Team still waiting for the Admin's ruling (while it can still be ruled on), by kick-off."""
    now = now or timezone.now()
    start = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)  # South Africa has no daylight saving.
    waiting = TeamReadiness.objects.filter(
        fixture=OuterRef("pk"), kick_off=OuterRef("kick_off"), outcome=Outcome.PENDING
    )
    fixtures = (
        Fixture.objects.filter(club=club)
        .filter(
            Q(kick_off__gte=start, kick_off__lt=end)
            | Q(Exists(waiting), status__in=CHECKED_STATUSES)
        )
        .select_related("club", "season", "division__night", "pitch__referee")
        .select_related("home_team", "away_team", "friendly_eligible_changed_by")
        .order_by("kick_off", "pitch__name", "pk")
    )
    return [tonight_fixture(f) for f in fixtures]
