"""Who receives each notification (PRD "Notifications" and "Targeting rules").

Every later chunk picks recipients here, so the rules live in one place:

- Players only receive notifications for the Nights they opted into. That covers anyone
  addressed as a Player, Captains too (a Captain is a Player). Admins and Referees are
  addressed through their Club role and are not filtered by Night.
- Player Requests go only to outfield Players, Goalkeeper Requests only to Goalkeepers
  (a Player who plays both gets both), and never to Players of either opposing Team.
- A payment Remind from the Outstanding list (FR-48) goes only to the named Players of the
  Team who opted into its Night.
- On a reschedule, only that Night's Admins and the affected pitch's Referee are told,
  besides the Players of both Teams (FR-7, FR-8).

A Night has no Admin of its own, so "the Admin of the registered Night" is every Admin of
the Night's Club (provisional, docs/OPEN_QUESTIONS.md "Chunk 9"). A pitch's Referee is
told only while they still hold the Referee role at the pitch's Club.

Every function returns a queryset of active users, each at most once.
"""

from collections.abc import Iterable

from django.db.models import Q, QuerySet

from accounts.models import ClubRole, PlayerProfile, User
from clubs.models import Club, Field, Night

from .models import Kind


def _users(condition: Q) -> QuerySet[User]:
    return User.objects.filter(condition, is_active=True).distinct().order_by("pk")


def _in_team(teams: Iterable) -> Q:
    return Q(
        team_memberships__team__in=list(teams),
        team_memberships__left_at__isnull=True,
    )


def opted_in(night: Night) -> Q:
    """Players who opted into this Night's notifications."""
    return Q(player_profile__nights=night)


def team_players(team, night: Night | None = None) -> QuerySet[User]:
    """The Players in `team` now (its Captain too) who opted into its Night."""
    night = night or team.division.night
    return _users(_in_team([team]) & opted_in(night))


def fixture_players(fixture, teams: Iterable | None = None) -> QuerySet[User]:
    """The Players of the Fixture's Teams (or of `teams`) who opted into its Night."""
    teams = teams if teams is not None else (fixture.home_team, fixture.away_team)
    return _users(_in_team(teams) & opted_in(fixture.night))


def opted_in_captains(teams: Iterable, night: Night) -> QuerySet[User]:
    """The Captains of `teams` who opted into this Night (a replacement offer, FR-15)."""
    captain_ids = [team.captain_id for team in teams if team.captain_id]
    return _users(Q(pk__in=captain_ids) & opted_in(night))


def players_outside(fixture, position: str | None = None) -> QuerySet[User]:
    """Players opted into the Fixture's Night who are in neither of its Teams (FR-11, FR-36).

    `position` "outfield" keeps outfield Players, "goalkeeper" keeps Goalkeepers; a Player
    who plays both counts as either.
    """
    condition = opted_in(fixture.night)
    Position = PlayerProfile.Position
    if position == Position.OUTFIELD:
        condition &= Q(player_profile__position__in=[Position.OUTFIELD, Position.BOTH])
    elif position == Position.GOALKEEPER:
        condition &= Q(player_profile__position__in=[Position.GOALKEEPER, Position.BOTH])
    elif position is not None:
        raise ValueError(f"Unknown position {position!r}.")
    in_either = User.objects.filter(_in_team([fixture.home_team, fixture.away_team]))
    return _users(condition).exclude(pk__in=in_either.values("pk"))


def request_recipients(fixture, kind: str) -> QuerySet[User]:
    """A Player Request or Goalkeeper Request for the Fixture (FR-35, FR-36)."""
    positions = {
        Kind.PLAYER_REQUEST: PlayerProfile.Position.OUTFIELD,
        Kind.GOALKEEPER_REQUEST: PlayerProfile.Position.GOALKEEPER,
    }
    if kind not in positions:
        raise ValueError(f"{kind!r} is not a Player or Goalkeeper Request.")
    return players_outside(fixture, positions[kind])


def club_admins(club: Club) -> QuerySet[User]:
    return _users(Q(club_roles__club=club, club_roles__role=ClubRole.Role.ADMIN))


def night_admins(night: Night) -> QuerySet[User]:
    """The Admins of a Night: every Admin of its Club (a Night has no Admin of its own)."""
    return club_admins(night.club)


def pitch_referees(*pitches: Field) -> QuerySet[User]:
    """The Referees of these pitches, while they hold the Referee role at the pitch's Club."""
    condition = Q(pk__in=[])
    for pitch in pitches:
        if pitch.referee_id:
            condition |= Q(
                pk=pitch.referee_id,
                club_roles__club_id=pitch.club_id,
                club_roles__role=ClubRole.Role.REFEREE,
            )
    return _users(condition)


def officials(fixture) -> QuerySet[User]:
    """The Fixture's Night's Admins and its pitch's Referee (FR-12, FR-16, FR-17)."""
    return _users(
        Q(pk__in=night_admins(fixture.night).values("pk"))
        | Q(pk__in=pitch_referees(fixture.pitch).values("pk"))
    )


def confirmation_recipients(fixture) -> QuerySet[User]:
    """FR-1, FR-2: every Player of both Teams."""
    return fixture_players(fixture)


def reminder_recipients(fixture) -> QuerySet[User]:
    """FR-4: Players and Captains of both Teams, the Night's Admins and the pitch's Referee."""
    return _users(
        Q(pk__in=fixture_players(fixture).values("pk")) | Q(pk__in=officials(fixture).values("pk"))
    )


def reschedule_officials(fixture, old_pitch: Field | None = None) -> QuerySet[User]:
    """FR-8: only the Night's Admins and the affected pitch's Referee.

    When the pitch changes, both the old and the new pitch are affected.
    """
    pitches = [fixture.pitch] + ([old_pitch] if old_pitch and old_pitch != fixture.pitch else [])
    return _users(
        Q(pk__in=night_admins(fixture.night).values("pk"))
        | Q(pk__in=pitch_referees(*pitches).values("pk"))
    )


def reschedule_players(fixture) -> QuerySet[User]:
    """FR-7: the Players of both rescheduled Teams."""
    return fixture_players(fixture)


def booking_recipients(club: Club) -> QuerySet[User]:
    """FR-29: the Club's Admins."""
    return club_admins(club)


def payment_reminder_recipients(team, players: Iterable) -> QuerySet[User]:
    """FR-48: these Players, while in `team` now and opted into its Night."""
    return _users(
        Q(pk__in=[player.pk for player in players])
        & _in_team([team])
        & opted_in(team.division.night)
    )
