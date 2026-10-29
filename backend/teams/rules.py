"""What may happen to a Team, its Players and its join requests, and in what order.

Every change runs in a transaction and locks what it checks: the Player, so they can't end
up in two Teams of one Division and Season, and the Division, so it can't take more Teams
than its `max_teams`. Views call these; nothing else changes Teams.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import normalize_email
from clubs.models import Division, Season
from core.exceptions import Conflict
from ledger import services as ledger
from notifications import services as notifications
from notifications import targeting
from notifications.models import Kind

from .models import JoinRequest, Team, TeamInvite, TeamMembership

logger = logging.getLogger(__name__)

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
NO_SUCH_PLAYER = (
    "No Player in League App has this email. Ask them to sign up as a Player first, or add "
    "the Team with another Captain and invite them to it."
)
ALREADY_PLAYS_HERE = "This Player is already in this Team."
ALREADY_INVITED = "This email is already invited to this Team."


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
    ledger.charge_league_fee(team, recorded_by=admin)
    return team


@transaction.atomic
def add_team(season: Season, division: Division, name: str, admin) -> Team:
    """The Admin adds a confirmed Team with no Captain and no Players, as the league import
    does for a Team its Fixtures name (docs/DECISIONS.md). The first Player to ask to join it
    is its Captain. Like confirming a request, it counts against the Division's `max_teams`
    and charges the league fee."""
    if division.get_club_id() != season.club_id:
        raise ValidationError({"division": [OTHER_CLUB]})
    if division.effective_league_fee is None:
        raise ValidationError({"division": [NO_LEAGUE_FEE]})
    division = Division.objects.select_for_update().get(pk=division.pk)
    if _is_full(division, season.pk):
        raise Conflict(DIVISION_FULL)
    now = timezone.now()
    team = Team.objects.create(
        club_id=season.club_id,
        season=season,
        division=division,
        name=name,
        status=Team.Status.ACTIVE,
        decided_by=admin,
        decided_at=now,
    )
    ledger.charge_league_fee(team, recorded_by=admin)
    return team


@transaction.atomic
def add_team_with_captain(
    season: Season, division: Division, name: str, captain_email: str, admin
) -> Team:
    """The Admin adds a confirmed Team with its Captain, a Player found by email, in it
    (docs/DECISIONS.md). As add_team: it counts against `max_teams` and charges the league fee."""
    if season.ends_on < timezone.localdate():
        raise ValidationError({"season": [SEASON_ENDED]})
    captain = _player_by_email(captain_email)
    if captain is None:
        raise ValidationError({"captain_email": [NO_SUCH_PLAYER]})
    _lock_player(captain)
    if _in_another_team(captain, season.pk, division.pk):
        raise ValidationError({"captain_email": [PLAYER_IN_DIVISION]})
    taken = Team.objects.exclude(status=Team.Status.DECLINED).filter(
        season=season, division=division, name__iexact=name
    )
    if taken.exists():
        raise ValidationError({"name": [NAME_TAKEN]})
    try:
        with transaction.atomic():
            team = add_team(season, division, name, admin)
    except IntegrityError as error:
        raise ValidationError({"name": [NAME_TAKEN]}) from error
    team.captain = captain
    team.save(update_fields=["captain"])
    _join(team, captain, team.decided_at)
    _withdraw_other_requests(captain, team, team.decided_at)
    _tell_added(team, captain)
    return team


def _player_by_email(email: str):
    return User.objects.filter(
        email=normalize_email(email), is_active=True, player_profile__isnull=False
    ).first()


def _withdraw_other_requests(player, team: Team, when) -> None:
    JoinRequest.objects.filter(
        player=player,
        status=JoinRequest.Status.PENDING,
        team__season_id=team.season_id,
        team__division_id=team.division_id,
    ).update(status=JoinRequest.Status.WITHDRAWN, decided_at=when)


def _tell_added(team: Team, player) -> None:
    """An Update to the Player, only if they opted into the Team's Night (targeting)."""
    role = "Captain of" if team.captain_id == player.pk else "a Player in"
    notifications.notify(
        Kind.UPDATE,
        targeting.added_to_team_recipients(team, player),
        club=team.club,
        title=f"You're {role} {team.name}",
        body=(
            f"{team.club.name} added you to {team.name}, {team.division.name}, {team.season.name}."
        ),
    )


@transaction.atomic
def invite_player(team: Team, email: str, admin) -> TeamInvite:
    """The Admin invites an email to play in the Team. A Player with that email joins at
    once (the invite comes back accepted). Anyone else gets an email, and joins when they
    sign up or start playing with that email (accept_team_invites)."""
    team = _lock_team(team)
    if team.status != Team.Status.ACTIVE:
        raise Conflict(NOT_ACTIVE)
    if _season_ended(team):
        raise Conflict(SEASON_ENDED)
    email = normalize_email(email)
    if team.current_memberships().filter(player__email=email).exists():
        raise ValidationError({"email": [ALREADY_PLAYS_HERE]})
    if team.invites.filter(email=email, accepted_at__isnull=True).exists():
        raise ValidationError({"email": [ALREADY_INVITED]})
    player = _player_by_email(email)
    if player is not None:
        _lock_player(player)
        if _in_another_team(player, team.season_id, team.division_id):
            raise ValidationError({"email": [PLAYER_IN_DIVISION]})
    invite = TeamInvite.objects.create(team=team, email=email, invited_by=admin)
    if player is not None:
        _accept(invite, team, player)
    else:
        transaction.on_commit(lambda: _email_invite(invite), robust=True)
    return invite


def _accept(invite: TeamInvite, team: Team, player) -> None:
    now = timezone.now()
    first = team.captain_id is None and not team.current_memberships().exists()
    _join(team, player, now)
    _withdraw_other_requests(player, team, now)
    if first:  # As ask_to_join: a Team with no one in it takes its first Player as Captain.
        team.captain = player
        team.save(update_fields=["captain"])
    invite.accepted_at = now
    invite.save(update_fields=["accepted_at"])
    _tell_added(team, player)


def _email_invite(invite: TeamInvite) -> None:
    team = invite.team
    lines = [
        f"{team.club.name} has added you to {team.name} ({team.division.name}, "
        f"{team.season.name}) in League App.",
        "",
        "Sign up as a Player with this email address and you'll be in the Team.",
    ]
    if settings.APP_SIGNUP_URL:
        lines += ["", settings.APP_SIGNUP_URL]
    send_mail(
        f"Join {team.name} in League App",
        "\n".join(lines),
        None,  # DEFAULT_FROM_EMAIL
        [invite.email],
    )


def accept_team_invites(user) -> None:
    """Puts a new Player in the Teams they were invited to. Call it when an account is made,
    or starts playing. An invite that can no longer be met (the Team isn't active, its
    Season ended, or the Player is in another Team of that Division) stays open, so the
    Admin sees it and can cancel it."""
    if not user.is_player:
        return
    invites = TeamInvite.objects.filter(email=user.email, accepted_at__isnull=True)
    for invite_id in invites.order_by("created_at").values_list("pk", flat=True):
        with transaction.atomic():
            _lock_player(user)
            invite = TeamInvite.objects.select_for_update().get(pk=invite_id)
            team = _lock_team(invite.team)
            if invite.accepted_at is not None or team.status != Team.Status.ACTIVE:
                continue
            if _season_ended(team) or _in_another_team(user, team.season_id, team.division_id):
                logger.info("Team invite %s left open: it can't be met now.", invite.pk)
                continue
            _accept(invite, team, user)


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
    """A Player asks to join a Team. A Team with no Captain and no Players (one the Admin
    added) takes the first Player at once, as its Captain: the request comes back accepted."""
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
    join_request = JoinRequest.objects.create(team=team, player=player)
    if team.captain_id is None and not team.current_memberships().exists():
        _take_in(join_request, team, by=player)
        team.captain = player
        team.save(update_fields=["captain"])
    return join_request


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
    return _take_in(join_request, team, by=captain)


def _take_in(join_request: JoinRequest, team: Team, by) -> TeamMembership:
    """Accepts the request and withdraws the Player's other ones in this Division."""
    player = join_request.player
    _answer(join_request, JoinRequest.Status.ACCEPTED, by)
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
