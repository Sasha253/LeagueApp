"""Answering Confirmations (FR-3) and who has answered (FR-38).

A Player in either Team of a Fixture answers "confirm" (playing) or "decline", from the
Confirmation Notification or from the match screen. Both end in `answer()`, which decides
everything here, never the app:

- Replies are open while the Fixture is `confirming` (the T-36h Confirmations went out,
  FR-1) and until the cutoff, `readiness_hours_before` kick-off (T-6h) from the Club's own
  settings. The Player can change their answer as often as they like until then.
- Only a Player in one of the Fixture's Teams now can answer, for that Team.
- A replacement opponent that took the slot after the cutoff (chunk 14, fixtures/
  replacements.py) gets its Confirmations then: its Players answer while the match is
  `ready`, until kick-off. Their answers decide nothing; the T-6h check has run.
- One answer per Player, Fixture and kick-off (ConfirmationAnswer). The Player's
  Confirmation Notification for the match shows the same answer, whichever way it was
  given, so the inbox and the resend (FR-2) agree with the match screen.

`squad()` is what a Team's Players see: each Player in the Team now and their answer, and
whether the Team is below its Division's minimum (FR-5). The T-6h readiness check (chunk
13) counts with `confirmed_count()`.

Locks: the Fixture first, then Notifications, in every path (here, the Notification answer
in notifications/services.py, and the checkpoints), so two of them never deadlock.
"""

from dataclasses import dataclass, field
from datetime import datetime

from django.db import transaction
from django.db.models import Q
from django.dispatch import receiver
from django.utils import timezone

from core.exceptions import Conflict
from notifications.models import Kind, Notification
from notifications.services import match_day, match_time, notification_answered
from teams.models import Team, TeamMembership

from . import lifecycle
from .checkpoints import confirmation_cutoff
from .models import ConfirmationAnswer, Fixture, ReplacementCandidate, ReplacementOffer

S = Fixture.Status
Value = ConfirmationAnswer.Value
Via = ConfirmationAnswer.Via

NOT_OPEN_YET = "Replies open when the Confirmations go out, {hours} hours before kick-off."
CLOSED = "Replies for this match closed at {day}, {time}."
NOT_CONFIRMING = "This match isn't taking replies."
NOT_IN_TEAM = "You're not in either Team of this match."


def cutoff(fixture: Fixture) -> datetime:
    """T-6h: answers are taken until then (FR-3)."""
    return confirmation_cutoff(fixture, fixture.club.settings)


def late_replacement(fixture: Fixture, team: Team | None) -> bool:
    """`team` took this match's slot after the cutoff (chunk 14)."""
    if team is None:
        return False
    return ReplacementOffer.objects.filter(
        fixture=fixture,
        kick_off=fixture.kick_off,
        status=ReplacementOffer.Status.ACCEPTED,
        accepted_team=team,
        accepted_at__gte=cutoff(fixture),
    ).exists()


def answer_by(fixture: Fixture, team: Team | None = None) -> datetime:
    """Until when `team`'s Players can answer: the cutoff, or kick-off for a late replacement."""
    return fixture.kick_off if late_replacement(fixture, team) else cutoff(fixture)


def replies_open(fixture: Fixture, now: datetime, team: Team | None = None) -> bool:
    if late_replacement(fixture, team):
        return fixture.status == S.READY and now < fixture.kick_off
    return fixture.status == S.CONFIRMING and now < cutoff(fixture)


def team_of(fixture: Fixture, player) -> Team | None:
    """The Fixture's Team the Player is in now (a Player is in one Team per Division)."""
    membership = (
        TeamMembership.objects.filter(
            player=player,
            left_at__isnull=True,
            team_id__in=[fixture.home_team_id, fixture.away_team_id],
            team__status=Team.Status.ACTIVE,
        )
        .select_related("team")
        .first()
    )
    return membership.team if membership else None


def _refuse_if_closed(fixture: Fixture, now: datetime, team: Team | None) -> None:
    if late_replacement(fixture, team):
        if fixture.status != S.READY:
            raise Conflict(NOT_CONFIRMING)
        if now >= fixture.kick_off:
            kick_off = fixture.kick_off
            raise Conflict(CLOSED.format(day=match_day(kick_off), time=match_time(kick_off)))
        return
    if fixture.status == S.SCHEDULED:
        hours = fixture.club.settings.confirmation_hours_before
        raise Conflict(NOT_OPEN_YET.format(hours=hours))
    if fixture.status != S.CONFIRMING:
        raise Conflict(NOT_CONFIRMING)
    closes = cutoff(fixture)
    if now >= closes:
        raise Conflict(CLOSED.format(day=match_day(closes), time=match_time(closes)))


@transaction.atomic
def answer(fixture: Fixture, player, value: str, *, via: str) -> ConfirmationAnswer:
    """Records (or changes) the Player's answer. 409 when replies are closed for them."""
    if value not in Value.values:
        raise Conflict(f"Answer with one of: {', '.join(Value.values)}.")
    fixture = lifecycle.lock(fixture.pk, "club__settings")
    now = timezone.now()
    team = team_of(fixture, player)
    _refuse_if_closed(fixture, now, team)
    if team is None:
        raise Conflict(NOT_IN_TEAM)
    saved, _created = ConfirmationAnswer.objects.update_or_create(
        fixture=fixture,
        player=player,
        kick_off=fixture.kick_off,
        defaults={"team": team, "answer": value, "answered_at": now, "via": via},
    )
    _copy_to_notifications(fixture, player, value, now)
    return saved


def _copy_to_notifications(fixture: Fixture, player, value: str, now: datetime) -> None:
    """The Player's open Confirmation for this match shows the same answer (inbox, FR-2)."""
    open_confirmations = Notification.objects.filter(
        fixture=fixture,
        recipient=player,
        kind=Kind.CONFIRMATION,
        closed_at__isnull=True,
    ).filter(Q(answer_by__isnull=True) | Q(answer_by__gt=now))
    open_confirmations.exclude(answer=value).update(answer=value, answered_at=now)
    open_confirmations.filter(read_at__isnull=True).update(read_at=now)


@receiver(notification_answered, dispatch_uid="fixtures.confirmation_answered")
def confirmation_answered(sender, notification: Notification, previous: str, **kwargs) -> None:
    """Answering the Confirmation Notification answers for the match (same transaction)."""
    if notification.kind != Kind.CONFIRMATION or notification.fixture_id is None:
        return
    if ReplacementCandidate.objects.filter(notification_id=notification.pk).exists():
        return  # A Captain's replacement offer: fixtures/replacements.py answers it.
    answer(notification.fixture, notification.recipient, notification.answer, via=Via.NOTIFICATION)


def confirmed_count(fixture: Fixture, team: Team) -> int:
    """Players in `team` now who confirmed for it, for the Fixture's current kick-off (FR-5).

    An answer given for the other Team of the match (a Player who moved between them) does
    not count: they answer again for their new Team.
    """
    return ConfirmationAnswer.objects.filter(
        fixture=fixture,
        team=team,
        kick_off=fixture.kick_off,
        answer=Value.CONFIRM,
        player__team_memberships__team=team,
        player__team_memberships__left_at__isnull=True,
    ).count()


@dataclass
class SquadPlayer:
    id: int
    name: str
    position: str
    is_captain: bool
    answer: str
    answered_at: datetime | None


@dataclass
class Squad:
    fixture: Fixture
    team: Team
    min_players: int
    answer_by: datetime
    replies_open: bool
    players: list[SquadPlayer] = field(default_factory=list)

    def count(self, value: str) -> int:
        return sum(1 for p in self.players if p.answer == value)

    @property
    def confirmed(self) -> int:
        return self.count(Value.CONFIRM)

    @property
    def declined(self) -> int:
        return self.count(Value.DECLINE)

    @property
    def waiting(self) -> int:
        return self.count("")

    @property
    def below_minimum(self) -> bool:
        return self.confirmed < self.min_players

    @property
    def short_by(self) -> int:
        return max(0, self.min_players - self.confirmed)


def squad(fixture: Fixture, team: Team, now: datetime | None = None) -> Squad:
    """Every Player in `team` now and their answer for the Fixture's kick-off (FR-38)."""
    now = now or timezone.now()
    memberships = (
        TeamMembership.objects.filter(team=team, left_at__isnull=True)
        .select_related("player__player_profile")
        .order_by("player__name", "player_id")
    )
    answers = {
        a.player_id: a
        for a in ConfirmationAnswer.objects.filter(
            fixture=fixture, team=team, kick_off=fixture.kick_off
        )
    }
    players = []
    for membership in memberships:
        player = membership.player
        given = answers.get(player.pk)
        profile = getattr(player, "player_profile", None)
        players.append(
            SquadPlayer(
                id=player.pk,
                name=player.name,
                position=profile.position if profile else "",
                is_captain=player.pk == team.captain_id,
                answer=given.answer if given else "",
                answered_at=given.answered_at if given else None,
            )
        )
    players.sort(key=lambda p: not p.is_captain)  # The Captain first, then by name.
    return Squad(
        fixture=fixture,
        team=team,
        min_players=fixture.division.min_players,
        answer_by=answer_by(fixture, team),
        replies_open=replies_open(fixture, now, team),
        players=players,
    )
