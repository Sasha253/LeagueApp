"""What may happen to a Team, its Players and its join requests, and in what order.

Every change runs in a transaction and locks what it checks: the Player, so they can't end
up in two Teams of one Division and Season, and the Division, so it can't take more Teams
than its `max_teams`. Views call these; nothing else changes Teams.
"""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from clubs.models import Division, Season
from core.exceptions import Conflict

from .models import JoinRequest, Team, TeamMembership

User = get_user_model()

SEASON_ENDED = "This Season has ended."
OTHER_CLUB = "This Division belongs to another club."
NO_LEAGUE_FEE = "The club hasn't set the league fee for this Division yet, so Teams can't sign up."
DIVISION_FULL = "This Division has all the Teams it takes for this Season."
NAME_TAKEN = "This Division already has a Team with this name this Season."
ALREADY_IN_DIVISION = "You're already in a Team in this Division this Season."
PLAYER_IN_DIVISION = "This Player is already in another Team in this Division this Season."
NOT_REQUESTED = "This Team is no longer waiting for a decision."
NOT_ACTIVE = "This Team isn't active."
DECLINED_TEAM = "This Team was declined."
ALREADY_MEMBER = "You're already in this Team."
ALREADY_ASKED = "You've already asked to join this Team."
NOT_PENDING = "This request has already been answered."
NOT_A_MEMBER = "Only a Player in this Team can be its Captain."
NOT_IN_TEAM = "You're not in this Team."
CAPTAIN_CANT_LEAVE = "A Captain can't leave their Team. Ask the Admin to assign another Captain."
ALREADY_CAPTAIN = "This Player is already the Captain."


def _lock_player(player) -> None:
    User.objects.select_for_update().filter(pk=player.pk).first()


def _in_another_team(player, season_id: int, division_id: int, team: Team | None = None) -> bool:
    memberships = TeamMembership.objects.filter(
        player=player,
        left_at__isnull=True,
        team__season_id=season_id,
        team__division_id=division_id,
        team__status__in=[Team.Status.REQUESTED, Team.Status.ACTIVE],
    )
    if team is not None:
        memberships = memberships.exclude(team=team)
    return memberships.exists()


def _is_full(division: Division, season_id: int) -> bool:
    if division.max_teams is None:
        return False
    active = Team.objects.filter(division=division, season_id=season_id, status=Team.Status.ACTIVE)
    return active.count() >= division.max_teams


def _season_ended(team: Team) -> bool:
    return team.season.ends_on < timezone.localdate()


def _join(team: Team, player, when) -> TeamMembership:
    return TeamMembership.objects.create(team=team, player=player, joined_at=when)


@transaction.atomic
def request_team(player, season: Season, division: Division, name: str) -> Team:
    """A Player asks the Admin for a new Team, with themself as its Captain."""
    errors = {}
    if division.get_club_id() != season.club_id:
        errors["division"] = [OTHER_CLUB]
    elif division.effective_league_fee is None:
        errors["division"] = [NO_LEAGUE_FEE]
    if season.ends_on < timezone.localdate():
        errors["season"] = [SEASON_ENDED]
    if errors:
        raise ValidationError(errors)

    _lock_player(player)
    division = Division.objects.select_for_update().get(pk=division.pk)
    if _in_another_team(player, season.pk, division.pk):
        raise Conflict(ALREADY_IN_DIVISION)
    if _is_full(division, season.pk):
        raise Conflict(DIVISION_FULL)
    taken = Team.objects.exclude(status=Team.Status.DECLINED).filter(
        season=season, division=division, name__iexact=name
    )
    if taken.exists():
        raise ValidationError({"name": [NAME_TAKEN]})
    try:
        with transaction.atomic():
            team = Team.objects.create(
                club_id=season.club_id,
                season=season,
                division=division,
                name=name,
                captain=player,
                status=Team.Status.REQUESTED,
                requested_by=player,
            )
    except IntegrityError as error:
        raise ValidationError({"name": [NAME_TAKEN]}) from error
    _join(team, player, team.requested_at)
    return team


def _lock_team(team: Team) -> Team:
    return Team.objects.select_for_update().get(pk=team.pk)


@transaction.atomic
def confirm_team(team: Team, admin) -> Team:
    team = _lock_team(team)
    if team.status != Team.Status.REQUESTED:
        raise Conflict(NOT_REQUESTED)
    division = Division.objects.select_for_update().get(pk=team.division_id)
    if _is_full(division, team.season_id):
        raise Conflict(DIVISION_FULL)
    team.status = Team.Status.ACTIVE
    team.decided_by = admin
    team.decided_at = timezone.now()
    team.save(update_fields=["status", "decided_by", "decided_at"])
    return team


@transaction.atomic
def decline_team(team: Team, admin, reason: str = "") -> Team:
    """Declines a Team request. Its Players leave it, so they can join or request another."""
    team = _lock_team(team)
    if team.status != Team.Status.REQUESTED:
        raise Conflict(NOT_REQUESTED)
    now = timezone.now()
    team.status = Team.Status.DECLINED
    team.decided_by = admin
    team.decided_at = now
    team.decline_reason = reason
    team.save(update_fields=["status", "decided_by", "decided_at", "decline_reason"])
    team.current_memberships().update(left_at=now)
    return team


@transaction.atomic
def assign_captain(team: Team, player) -> Team:
    """The Admin makes a Player of the Team its Captain. The old Captain stays a Player."""
    team = _lock_team(team)
    if team.status == Team.Status.DECLINED:
        raise Conflict(DECLINED_TEAM)
    if team.captain_id == player.pk:
        raise Conflict(ALREADY_CAPTAIN)
    if not team.current_memberships().filter(player=player).exists():
        raise ValidationError({"player": [NOT_A_MEMBER]})
    team.captain = player
    team.save(update_fields=["captain"])
    return team


@transaction.atomic
def ask_to_join(team: Team, player) -> JoinRequest:
    _lock_player(player)
    team = _lock_team(team)
    if team.status != Team.Status.ACTIVE:
        raise Conflict(NOT_ACTIVE)
    if _season_ended(team):
        raise Conflict(SEASON_ENDED)
    if team.current_memberships().filter(player=player).exists():
        raise Conflict(ALREADY_MEMBER)
    if team.join_requests.filter(player=player, status=JoinRequest.Status.PENDING).exists():
        raise Conflict(ALREADY_ASKED)
    if _in_another_team(player, team.season_id, team.division_id):
        raise Conflict(ALREADY_IN_DIVISION)
    return JoinRequest.objects.create(team=team, player=player)


def _lock_pending(join_request: JoinRequest) -> JoinRequest:
    join_request = JoinRequest.objects.select_for_update().get(pk=join_request.pk)
    if join_request.status != JoinRequest.Status.PENDING:
        raise Conflict(NOT_PENDING)
    return join_request


def _answer(join_request: JoinRequest, status: str, by) -> None:
    join_request.status = status
    join_request.decided_by = by
    join_request.decided_at = timezone.now()
    join_request.save(update_fields=["status", "decided_by", "decided_at"])


@transaction.atomic
def accept_join(join_request: JoinRequest, captain) -> TeamMembership:
    """The Captain takes the Player in. Their other requests in this Division are withdrawn."""
    _lock_player(join_request.player)
    join_request = _lock_pending(join_request)
    team = _lock_team(join_request.team)
    player = join_request.player
    if team.status != Team.Status.ACTIVE:
        raise Conflict(NOT_ACTIVE)
    if _season_ended(team):
        raise Conflict(SEASON_ENDED)
    if _in_another_team(player, team.season_id, team.division_id, team):
        raise Conflict(PLAYER_IN_DIVISION)
    _answer(join_request, JoinRequest.Status.ACCEPTED, captain)
    JoinRequest.objects.filter(
        player=player,
        status=JoinRequest.Status.PENDING,
        team__season_id=team.season_id,
        team__division_id=team.division_id,
    ).update(status=JoinRequest.Status.WITHDRAWN, decided_at=join_request.decided_at)
    return _join(team, player, join_request.decided_at)


@transaction.atomic
def decline_join(join_request: JoinRequest, captain) -> JoinRequest:
    join_request = _lock_pending(join_request)
    _answer(join_request, JoinRequest.Status.DECLINED, captain)
    return join_request


@transaction.atomic
def withdraw_join(join_request: JoinRequest) -> JoinRequest:
    join_request = _lock_pending(join_request)
    _answer(join_request, JoinRequest.Status.WITHDRAWN, join_request.player)
    return join_request


@transaction.atomic
def leave_team(team: Team, player) -> TeamMembership:
    team = _lock_team(team)
    membership = team.current_memberships().filter(player=player).first()
    if membership is None:
        raise Conflict(NOT_IN_TEAM)
    if team.captain_id == player.pk:
        raise Conflict(CAPTAIN_CANT_LEAVE)
    membership.left_at = timezone.now()
    membership.save(update_fields=["left_at"])
    return membership
