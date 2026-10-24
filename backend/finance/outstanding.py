"""The Outstanding list (FR-48): Teams and Players who owe, largest first, with Remind and
Mark cash paid on each row.

Definitions (docs/DECISIONS.md, chunk 27):

- A **Team owes** what its Team ledger says is outstanding (league fees charged less card,
  cash and credit paid). Only active Teams are listed: cash can't be recorded for a Team
  that has withdrawn.
- A **Player owes** their share less what they have paid towards the Team, never more than
  the Team still owes. The share is what is due over the Team's current Players, rounded
  up to the cent (as "Pay my share", payments.services.suggested_amount). Only current
  Players of a Team that owes are listed.
- **Remind** sends an Update notification (message only) to the Team's Captain and its
  Players who owe, or to the one Player, and only to those who opted into the Team's Night
  (PRD targeting rules).
- **Mark cash paid** records exactly what the row owes as cash (FR-22): for the Team, or
  for the one Player. The amount the Admin saw must still be what is owed, so nobody
  records cash against a figure that has since changed.
"""

from dataclasses import dataclass, field
from decimal import ROUND_UP, Decimal

from django.db import transaction
from django.db.models import Q

from accounts.models import PlayerProfile, User
from clubs.models import Club, Division, Night, Season
from core.exceptions import Conflict
from ledger import services as ledger
from ledger.models import LedgerEntry
from notifications import services as notifications
from notifications import targeting
from notifications.models import Kind as NotificationKind
from payments import services as payments
from teams.models import Team, TeamMembership

from .planner import local_today, season_weeks, team_plans
from .services import CENT, ZERO, Method, Sums, _aggregates, _divisions

NOTHING_OWED = "Nothing is owed here any more."
PLAYER_OWES_NOTHING = "This Player owes nothing towards the Team."
NOT_ACTIVE = "This Team isn't active."
CASH_REASON = "Cash paid, marked on the Outstanding list"


def _rand(amount: Decimal) -> str:
    return payments._rand(amount)


@dataclass
class PlayerOwed:
    player: User
    team: Team
    share: Decimal
    paid: Decimal
    owes: Decimal
    gets_notifications: bool


@dataclass
class TeamOwed:
    team: Team
    due: Decimal
    paid: Decimal
    outstanding: Decimal
    short_since_week: int | None = None
    players: list[PlayerOwed] = field(default_factory=list)

    @property
    def unpaid_players(self) -> list[str]:
        return [p.player.name for p in self.players]


@dataclass
class Outstanding:
    season: Season
    night: Night | None
    division: Division | None
    teams: list[TeamOwed]

    @property
    def players(self) -> list[PlayerOwed]:
        rows = [p for t in self.teams for p in t.players]
        return sorted(rows, key=lambda p: (-p.owes, p.player.name.lower(), p.team.name.lower()))

    @property
    def total(self) -> Decimal:
        return sum((t.outstanding for t in self.teams), ZERO)


def share_of(due: Decimal, players: int) -> Decimal:
    return (due / players).quantize(CENT, rounding=ROUND_UP) if players else due


def _paid_by_player(teams: list[Team]) -> dict[tuple[int, int], Decimal]:
    """What each Player paid towards each Team: card, cash and credit, net."""
    rows = (
        LedgerEntry.objects.filter(team__in=teams, user__isnull=False)
        .values("team_id", "user_id")
        .annotate(**_aggregates())
    )
    paid = {}
    for row in rows:
        sums = Sums(row)
        paid[(row["team_id"], row["user_id"])] = sum((sums.method(m) for m in Method.values), ZERO)
    return paid


def _opted_in(user_ids, night_ids) -> set[tuple[int, int]]:
    through = PlayerProfile.nights.through
    rows = through.objects.filter(
        playerprofile__user_id__in=user_ids, night_id__in=night_ids
    ).values_list("playerprofile__user_id", "night_id")
    return set(rows)


def _player_rows(owed: list[TeamOwed]) -> None:
    teams = [row.team for row in owed]
    members = (
        TeamMembership.objects.filter(team__in=teams, left_at__isnull=True)
        .select_related("player")
        .order_by("pk")
    )
    by_team: dict[int, list[User]] = {}
    for membership in members:
        by_team.setdefault(membership.team_id, []).append(membership.player)
    paid = _paid_by_player(teams)
    opted = _opted_in([m.player_id for m in members], {t.division.night_id for t in teams})
    for row in owed:
        players = by_team.get(row.team.pk, [])
        share = share_of(row.due, len(players))
        for player in players:
            already = paid.get((row.team.pk, player.pk), ZERO)
            owes = min(max(share - already, ZERO), row.outstanding)
            if owes > 0:
                row.players.append(
                    PlayerOwed(
                        player=player,
                        team=row.team,
                        share=share,
                        paid=already,
                        owes=owes,
                        gets_notifications=(player.pk, row.team.division.night_id) in opted,
                    )
                )
        row.players.sort(key=lambda p: (-p.owes, p.player.name.lower()))


def outstanding(
    club: Club,
    season: Season,
    *,
    night: Night | None = None,
    division: Division | None = None,
) -> Outstanding:
    division_ids = [d.pk for d in _divisions(club, night, division)]
    teams = Team.objects.filter(
        club=club, season=season, division_id__in=division_ids, status=Team.Status.ACTIVE
    ).select_related("division__night", "captain")
    balances = ledger.team_balances(teams)
    owed = [
        TeamOwed(
            team=team,
            due=balances[team.pk].due,
            paid=balances[team.pk].paid,
            outstanding=balances[team.pk].outstanding,
        )
        for team in teams
        if balances[team.pk].outstanding > 0
    ]
    if owed:
        _player_rows(owed)
        weeks = season_weeks(season, local_today())
        due_weeks = sum(1 for w in weeks if w.is_due)
        plans = team_plans(club, season, [row.team for row in owed], len(weeks))
        short = {plan.team.pk: plan.short_since(due_weeks) for plan in plans}
        for row in owed:
            row.short_since_week = short.get(row.team.pk)
    owed.sort(key=lambda row: (-row.outstanding, row.team.name.lower()))
    return Outstanding(season=season, night=night, division=division, teams=owed)


# One row's figures, for the actions


def _team_owes(team: Team) -> Decimal:
    return ledger.team_balance(team).outstanding


def player_owes(team: Team, player: User) -> Decimal:
    balance = ledger.team_balance(team)
    if balance.outstanding <= 0:
        return ZERO
    share = share_of(balance.due, team.current_memberships().count())
    already = ledger.paid_by_payer(team).get(player.pk, ZERO)
    return min(max(share - already, ZERO), balance.outstanding)


def _check_row(team: Team, player: User | None) -> Decimal:
    """What the row owes now; Conflict if nothing."""
    if team.status != Team.Status.ACTIVE:
        raise Conflict(NOT_ACTIVE)
    if _team_owes(team) <= 0:
        raise Conflict(NOTHING_OWED)
    if player is None:
        return _team_owes(team)
    owes = player_owes(team, player)
    if owes <= 0:
        raise Conflict(PLAYER_OWES_NOTHING)
    return owes


# Remind


@dataclass
class Reminded:
    sent_to: list[User]
    not_reached: list[User]


def _pay_how(club: Club) -> str:
    takes_card, _ = payments.club_card_options(club)
    return "Pay in the app, or in cash at the club." if takes_card else "Pay in cash at the club."


@transaction.atomic
def remind(*, team: Team, player: User | None = None) -> Reminded:
    """FR-48 Remind: an Update to the Team's Captain and Players who owe (or to `player`),
    only those opted into the Team's Night."""
    owes = _check_row(team, player)
    club = team.club
    if player is not None:
        wanted = [player]
        title = f"Payment due: {team.name}"
        body = f"Your share for {team.name} is {_rand(owes)} ({team.season.name}). {_pay_how(club)}"
    else:
        members = [m.player for m in team.current_memberships().select_related("player")]
        share = share_of(ledger.team_balance(team).due, len(members))
        paid = ledger.paid_by_payer(team)
        wanted = [
            member
            for member in members
            if member.pk == team.captain_id or share - paid.get(member.pk, ZERO) > 0
        ]
        title = f"Payment due: {team.name}"
        body = f"{team.name} still owes {_rand(owes)} for {team.season.name}. {_pay_how(club)}"
    recipients = list(targeting.payment_reminder_recipients(team, wanted))
    notifications.notify(NotificationKind.UPDATE, recipients, club=club, title=title, body=body)
    reached = {user.pk for user in recipients}
    return Reminded(
        sent_to=recipients,
        not_reached=sorted(
            (user for user in wanted if user.pk not in reached), key=lambda u: u.name.lower()
        ),
    )


# Mark cash paid


@transaction.atomic
def mark_cash_paid(
    *, team: Team, admin: User, amount: Decimal, player: User | None = None
) -> LedgerEntry:
    """FR-48 Mark cash paid: what the row owes, recorded as cash (FR-22). `amount` is what
    the Admin was shown; if what is owed has changed since, nothing is recorded."""
    team = Team.objects.select_for_update(of=("self",)).select_related("club").get(pk=team.pk)
    owes = _check_row(team, player)
    if amount != owes:
        raise Conflict(f"What is owed is now {_rand(owes)}. Check it and try again.")
    return payments.record_cash(
        team=team, admin=admin, amount=owes, player=player, reason=CASH_REASON
    )


def is_current_player(team: Team, user_id: int) -> User | None:
    membership = (
        team.current_memberships().filter(Q(player_id=user_id)).select_related("player").first()
    )
    return membership.player if membership else None
