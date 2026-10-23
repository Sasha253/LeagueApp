"""Player and Goalkeeper Requests: borrowing Players for one match (FR-35 to FR-37).

- A Captain who expects to be short raises a request for their Team's match: a Player
  Request (outfield) or a Goalkeeper Request, for one or more places (Screens.md Captain 4).
  Only while the match is scheduled, confirming or ready and before kick-off.
- It goes to the Players opted into the match's Night who are in neither Team and play
  that position (FR-36, the visibility rule; notifications/targeting.py
  `request_recipients`), less anyone already borrowed for the match. Each gets their own
  Notification with Accept / Decline, answerable until kick-off.
- The first Players to accept join, one per place (FR-37); then the request is filled,
  every other invite stops taking answers and the Captain gets an Update. A late Accept is
  refused (409) and not saved. Joining happens in the Notification's own transaction: the
  Fixture is locked first (notifications/services.py `answer`), then the request, so two
  Players accepting at once are taken one after the other; a database constraint keeps a
  Player to one borrowed place per match.
- A borrowed Player counts as confirmed for the Team at that kick-off (FR-5, FR-38).
- The Captain may withdraw an open request; whoever joined keeps their place.
- A request stops applying when the match moves to a new kick-off, its Team leaves the
  match, the match is no longer scheduled, confirming or ready, or kick-off passes. Its
  Notifications close with the match's (reschedules, fallbacks); the row is marked closed
  the next time the Team's requests change.

No fee is charged to a borrowed Player in this chunk (docs/OPEN_QUESTIONS.md "Chunk 17").

Locks: the Fixture first, then the PlayerRequest, in every path.
"""

from dataclasses import dataclass
from datetime import datetime

from django.db import IntegrityError, transaction
from django.dispatch import receiver
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from core.exceptions import Conflict
from notifications import services as notifications
from notifications import targeting
from notifications.models import Answer, Kind, Notification
from notifications.services import match_day, match_time, notification_answered
from teams.models import Team, TeamMembership

from . import lifecycle
from .models import BorrowedPlayer, Fixture, PlayerRequest, PlayerRequestInvite
from .reschedules import captain_team

S = Fixture.Status
RKind = PlayerRequest.Kind
RStatus = PlayerRequest.Status

# A match still on its way to being played as a league match.
OPEN_STATUSES = (S.SCHEDULED, S.CONFIRMING, S.READY)

NOTIFICATION_KIND = {RKind.PLAYER: Kind.PLAYER_REQUEST, RKind.GOALKEEPER: Kind.GOALKEEPER_REQUEST}
WANTED = {RKind.PLAYER: ("a player", "players"), RKind.GOALKEEPER: ("a goalkeeper", "goalkeepers")}

RELATED = ("club__settings", "division__night", "pitch", "home_team", "away_team")

NOT_CAPTAIN = "Only the Captain of a Team in this match can request players."
CLOSED_NOW = "Players can't be requested for this match now."
ALREADY_OPEN = "{team} already has an open request for {what}. Withdraw it to send a new one."
NO_ONE = "No one can be asked: no {who} opted into {night} outside both Teams."
TOO_MANY = "Ask for 1 to {most}."
NOT_OPEN = "This request has already been {status}."
NO_LONGER = "This request no longer applies."
FILLED = "Too late: this request has been filled."
IN_A_TEAM = "You're in one of this match's Teams."
ALREADY_JOINED = "You've already joined this match."
NOT_FOR_YOU = "This request isn't open to you any more."
NOT_YOURS = "Only {team}'s Captain can withdraw this request."


def _match(fixture: Fixture) -> str:
    return f"{fixture.home_team.name} vs {fixture.away_team.name}"


def _when(fixture: Fixture) -> str:
    return f"{match_day(fixture.kick_off)}, {match_time(fixture.kick_off)}, {fixture.pitch.name}"


def can_raise(fixture: Fixture, now: datetime | None = None) -> bool:
    now = now or timezone.now()
    return fixture.status in OPEN_STATUSES and now < fixture.kick_off


def max_places(fixture: Fixture) -> int:
    """At most the Division's minimum: a Team can't need more borrowed Players than that."""
    return max(1, fixture.division.min_players)


def applies(player_request: PlayerRequest, fixture: Fixture, now: datetime) -> bool:
    """The request is still for this match as it stands now."""
    return (
        fixture.kick_off == player_request.kick_off
        and player_request.team_id in (fixture.home_team_id, fixture.away_team_id)
        and can_raise(fixture, now)
    )


def still_playing(place: BorrowedPlayer, fixture: Fixture) -> bool:
    """The borrowed place still counts: same kick-off, and its Team is still in the match
    (the same rule as confirmations.borrowed)."""
    return place.kick_off == fixture.kick_off and place.team_id in (
        fixture.home_team_id,
        fixture.away_team_id,
    )


def status_of(player_request: PlayerRequest, fixture: Fixture, now: datetime) -> str:
    """What the request is now: an open one that no longer applies shows as closed."""
    if player_request.status == RStatus.OPEN and not applies(player_request, fixture, now):
        return RStatus.CLOSED
    return player_request.status


def _end(player_request: PlayerRequest, status: str, now: datetime, note: str = "") -> None:
    player_request.status = status
    player_request.ended_at = now
    player_request.note = note[:300]
    player_request.save(update_fields=["status", "ended_at", "note"])
    notifications.close(Notification.objects.filter(player_request_invite__request=player_request))


def _close_stale(fixture: Fixture, now: datetime) -> None:
    for stale in PlayerRequest.objects.select_for_update().filter(
        fixture=fixture, status=RStatus.OPEN
    ):
        if not applies(stale, fixture, now):
            _end(stale, RStatus.CLOSED, now, "The match changed, so the request no longer applies.")


def recipients(fixture: Fixture, kind: str):
    """FR-36: who a request of `kind` goes to, less anyone already borrowed for the match."""
    taken = BorrowedPlayer.objects.filter(fixture=fixture, kick_off=fixture.kick_off)
    return targeting.request_recipients(fixture, NOTIFICATION_KIND[kind]).exclude(
        pk__in=taken.values("player_id")
    )


@dataclass
class Preview:
    kind: str
    recipients: int
    night: str
    max_places: int


def preview(fixture: Fixture, captain, kind: str) -> Preview:
    """How many would be asked (Screens.md Captain 4). 403 for anyone but a Captain."""
    if captain_team(fixture, captain) is None:
        raise PermissionDenied(NOT_CAPTAIN)
    return Preview(
        kind=kind,
        recipients=recipients(fixture, kind).count(),
        night=fixture.night.get_weekday_display(),
        max_places=max_places(fixture),
    )


def _content(fixture: Fixture, team: Team, kind: str, places: int) -> tuple[str, str]:
    """Confirmation format: both team names, date and time."""
    one, many = WANTED[kind]
    what = one if places == 1 else f"{places} {many}"
    title = f"{team.name} need {what}: {_match(fixture)}"
    return title[:120], f"{_when(fixture)}. Can you play for {team.name}?"[:500]


@transaction.atomic
def raise_request(fixture: Fixture, captain, kind: str, places: int) -> PlayerRequest:
    """The Captain asks for borrowed Players (FR-35). See the module doc."""
    now = timezone.now()
    fixture = lifecycle.lock(fixture.pk, *RELATED)
    team = captain_team(fixture, captain)
    if team is None:
        raise PermissionDenied(NOT_CAPTAIN)
    if not can_raise(fixture, now):
        raise Conflict(CLOSED_NOW)
    most = max_places(fixture)
    if not 1 <= places <= most:
        raise ValidationError({"places": [TOO_MANY.format(most=most)]})
    _close_stale(fixture, now)
    if PlayerRequest.objects.filter(
        fixture=fixture, team=team, kind=kind, status=RStatus.OPEN
    ).exists():
        raise Conflict(ALREADY_OPEN.format(team=team.name, what=WANTED[kind][1]))
    asked = list(recipients(fixture, kind))
    if not asked:
        night = fixture.night.get_weekday_display()
        raise Conflict(NO_ONE.format(who=WANTED[kind][1], night=night))

    created = PlayerRequest.objects.create(
        fixture=fixture,
        team=team,
        kind=kind,
        places=places,
        kick_off=fixture.kick_off,
        raised_by=captain,
        raised_at=now,
        status=RStatus.OPEN,
        notified=len(asked),
    )
    title, body = _content(fixture, team, kind, places)
    sent = notifications.notify(
        NOTIFICATION_KIND[kind],
        asked,
        club=fixture.club,
        title=title,
        body=body,
        fixture=fixture,
        answer_by=fixture.kick_off,
    )
    PlayerRequestInvite.objects.bulk_create(
        PlayerRequestInvite(request=created, player_id=n.recipient_id, notification=n) for n in sent
    )
    return created


def _in_either_team(fixture: Fixture, player) -> bool:
    return TeamMembership.objects.filter(
        player=player,
        left_at__isnull=True,
        team_id__in=[fixture.home_team_id, fixture.away_team_id],
    ).exists()


def join(invite: PlayerRequestInvite, now: datetime | None = None) -> BorrowedPlayer:
    """The invited Player takes a place (FR-37). The Fixture is already locked by the
    caller (the Notification answer); 409 when they can't, which rolls the answer back."""
    now = now or timezone.now()
    player_request = PlayerRequest.objects.select_for_update().get(pk=invite.request_id)
    fixture = Fixture.objects.select_related(*RELATED).get(pk=player_request.fixture_id)
    if player_request.status == RStatus.FILLED:
        raise Conflict(FILLED)
    if player_request.status != RStatus.OPEN:
        raise Conflict(NOT_OPEN.format(status=player_request.get_status_display().lower()))
    if not applies(player_request, fixture, now):
        raise Conflict(NO_LONGER)
    player = invite.player
    if _in_either_team(fixture, player):
        raise Conflict(IN_A_TEAM)
    if BorrowedPlayer.objects.filter(
        fixture=fixture, kick_off=fixture.kick_off, player=player
    ).exists():
        raise Conflict(ALREADY_JOINED)
    still_for_them = targeting.request_recipients(fixture, NOTIFICATION_KIND[player_request.kind])
    if not still_for_them.filter(pk=player.pk).exists():
        raise Conflict(NOT_FOR_YOU)
    taken = BorrowedPlayer.objects.filter(request=player_request).count()
    if taken >= player_request.places:
        raise Conflict(FILLED)
    try:
        with transaction.atomic():
            joined = BorrowedPlayer.objects.create(
                request=player_request,
                fixture=fixture,
                team=player_request.team,
                kick_off=fixture.kick_off,
                player=player,
                joined_at=now,
            )
    except IntegrityError as error:
        raise Conflict(ALREADY_JOINED) from error
    # Their answer stands: no leaving once joined (docs/OPEN_QUESTIONS.md "Chunk 17").
    notifications.close(Notification.objects.filter(pk=invite.notification_id))
    if taken + 1 >= player_request.places:
        _end(player_request, RStatus.FILLED, now)
        _tell_captain_filled(fixture, player_request)
    return joined


def _tell_captain_filled(fixture: Fixture, player_request: PlayerRequest) -> None:
    """An Update to the Captain when the request fills (open question 2, provisional)."""
    names = list(
        BorrowedPlayer.objects.filter(request=player_request)
        .order_by("joined_at", "pk")
        .values_list("player__name", flat=True)
    )
    team = player_request.team
    one, many = WANTED[player_request.kind]
    what = one if player_request.places == 1 else many
    notifications.notify(
        Kind.UPDATE,
        targeting.opted_in_captains([team], fixture.night),
        club=fixture.club,
        title=f"Request filled: {_match(fixture)}"[:120],
        body=f"{', '.join(names)} will play for {team.name} as {what}. {_when(fixture)}."[:500],
        fixture=fixture,
    )


@receiver(notification_answered, dispatch_uid="fixtures.player_request_answered")
def request_answered(sender, notification: Notification, previous: str, **kwargs) -> None:
    """Accept on a Player or Goalkeeper Request joins the match; Decline is only recorded."""
    if notification.kind not in (Kind.PLAYER_REQUEST, Kind.GOALKEEPER_REQUEST):
        return
    invite = (
        PlayerRequestInvite.objects.filter(notification_id=notification.pk)
        .select_related("player")
        .first()
    )
    if invite is None or notification.answer != Answer.ACCEPT:
        return
    join(invite)


@transaction.atomic
def withdraw(player_request: PlayerRequest, captain) -> PlayerRequest:
    """The Captain takes back an open request. Who already joined keeps their place."""
    now = timezone.now()
    fixture = lifecycle.lock(player_request.fixture_id, *RELATED)
    player_request = PlayerRequest.objects.select_for_update().get(pk=player_request.pk)
    team = Team.objects.get(pk=player_request.team_id)
    if team.captain_id != captain.pk:
        raise PermissionDenied(NOT_YOURS.format(team=team.name))
    current = status_of(player_request, fixture, now)
    if current != RStatus.OPEN:
        raise Conflict(NOT_OPEN.format(status=PlayerRequest.Status(current).label.lower()))
    _end(player_request, RStatus.WITHDRAWN, now, "Withdrawn by the Captain.")
    return player_request
