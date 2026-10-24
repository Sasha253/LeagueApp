"""The finance tracker's figures (FR-25 to FR-27, FR-49), all computed from the ledger.

Nothing here writes: every figure is a sum of LedgerEntry rows, and a reversal entry takes
back the entry it undoes (FR-50). Definitions (docs/DECISIONS.md, chunk 25):

- **expected**: the league fees charged to the Teams in scope (Teams x fee, as charged when
  each Team was confirmed), less reversed charges.
- **card**, **cash**: money taken in by that method, less refunds and reversals.
  **received** is card plus cash: money the club actually took.
- **credit_spent**: what was paid from credit. It is not new money, so it is not received,
  but it does count towards what a Team has paid.
- **returned_as_credit**: what was given back as credit from this category's payments
  (a cancelled match or booking), less reversals.
- **outstanding**: what Teams still owe, Team by Team (charges less card, cash and credit
  paid, as on the Team ledger); a Team that paid more counts as owing nothing.
- **credit held**: credit not yet spent. Team credit belongs to a Team, so it is shown per
  Division; Player and Booking User credit is held per Club, so it is shown club-wide only.

League income is the `league` category on Team accounts, by the Team's Season, Night and
Division. Friendly income is the `friendly` category, by the Fixture's Season and Division.
Booking income is the `booking` category, for Bookings starting within the Season's dates
(South African time); bookings have no Night or Division.
"""

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import DecimalField, F, Q, QuerySet, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from clubs.models import Club, Division, Night, Season
from ledger.models import LedgerEntry
from teams.models import Team

Kind = LedgerEntry.Kind
Method = LedgerEntry.Method
Subject = LedgerEntry.Subject
Category = LedgerEntry.Category

CENT = Decimal("0.01")
ZERO = Decimal("0.00")

# Each sum: the kind of entry and the other fields it must match. Reversal entries copy
# every one of those fields, so "less reversals" is the same filter on reversals of `kind`.
SUMS: dict[str, tuple[str, Q]] = {
    "charge": (Kind.CHARGE, Q()),
    "returned": (Kind.CREDIT, Q(source__isnull=False)),
    "team_credit": (Kind.CREDIT, Q(subject=Subject.TEAM)),
    "team_credit_spent": (Kind.PAYMENT, Q(subject=Subject.TEAM, method=Method.CREDIT)),
    "user_credit": (Kind.CREDIT, Q(subject__in=[Subject.PLAYER, Subject.BOOKING_USER])),
    "user_credit_spent": (
        Kind.PAYMENT,
        Q(subject__in=[Subject.PLAYER, Subject.BOOKING_USER], method=Method.CREDIT),
    ),
}
for _method in Method.values:
    SUMS[f"payment_{_method}"] = (Kind.PAYMENT, Q(method=_method))
    SUMS[f"refund_{_method}"] = (Kind.REFUND, Q(method=_method))


def _aggregates() -> dict:
    money = {"output_field": DecimalField(max_digits=12, decimal_places=2)}
    result = {}
    for name, (kind, where) in SUMS.items():
        result[name] = Coalesce(Sum("amount", filter=where & Q(kind=kind)), Value(ZERO), **money)
        result[f"{name}_reversed"] = Coalesce(
            Sum("amount", filter=where & Q(kind=Kind.REVERSAL, reverses__kind=kind)),
            Value(ZERO),
            **money,
        )
    return result


class Sums:
    """Net sums of one group of entries: each sum less its reversals."""

    def __init__(self, row: dict | None = None):
        self.row = row or {}

    def net(self, name: str) -> Decimal:
        added = Decimal(self.row.get(name, ZERO))
        reversed_ = Decimal(self.row.get(f"{name}_reversed", ZERO))
        return (added - reversed_).quantize(CENT)

    def method(self, method: str) -> Decimal:
        return self.net(f"payment_{method}") - self.net(f"refund_{method}")


def _grouped(entries: QuerySet, key) -> dict:
    """Sums of `entries` grouped by `key` (an expression), as {key value: Sums}."""
    rows = entries.annotate(group=key).values("group").annotate(**_aggregates())
    return {row["group"]: Sums(row) for row in rows}


def _total(entries: QuerySet) -> Sums:
    return Sums(entries.aggregate(**_aggregates()))


# Lines


@dataclass
class IncomeLine:
    card: Decimal = ZERO
    cash: Decimal = ZERO
    credit_spent: Decimal = ZERO
    returned_as_credit: Decimal = ZERO

    @property
    def received(self) -> Decimal:
        return self.card + self.cash

    @classmethod
    def of(cls, sums: Sums) -> "IncomeLine":
        return cls(
            card=sums.method(Method.CARD),
            cash=sums.method(Method.CASH),
            credit_spent=sums.method(Method.CREDIT),
            returned_as_credit=sums.net("returned"),
        )

    def __add__(self, other: "IncomeLine") -> "IncomeLine":
        return IncomeLine(
            card=self.card + other.card,
            cash=self.cash + other.cash,
            credit_spent=self.credit_spent + other.credit_spent,
            returned_as_credit=self.returned_as_credit + other.returned_as_credit,
        )


@dataclass
class LeagueFigures:
    """League figures for a group of Teams, with friendly income beside them."""

    teams: int = 0
    expected: Decimal = ZERO
    outstanding: Decimal = ZERO
    team_credit_held: Decimal = ZERO
    league: IncomeLine = field(default_factory=IncomeLine)
    friendly: IncomeLine = field(default_factory=IncomeLine)

    def add(self, other: "LeagueFigures") -> None:
        self.teams += other.teams
        self.expected += other.expected
        self.outstanding += other.outstanding
        self.team_credit_held += other.team_credit_held
        self.league = self.league + other.league
        self.friendly = self.friendly + other.friendly


@dataclass
class DivisionFigures(LeagueFigures):
    division: Division | None = None


@dataclass
class NightFigures(LeagueFigures):
    night: Night | None = None
    divisions: list[DivisionFigures] = field(default_factory=list)


@dataclass
class CreditHeld:
    team: Decimal = ZERO
    player: Decimal | None = None
    booking_user: Decimal | None = None


@dataclass
class SeasonSummary:
    season: Season
    night: Night | None
    division: Division | None
    totals: LeagueFigures
    booking: IncomeLine | None
    credit_held: CreditHeld
    nights: list[NightFigures]

    @property
    def received(self) -> Decimal:
        total = self.totals.league.received + self.totals.friendly.received
        return total + (self.booking.received if self.booking else ZERO)


# Scope


def season_window(season: Season) -> tuple[dt.datetime, dt.datetime]:
    """The Season's first and last days in South African time, as a [start, end) range."""
    tz = timezone.get_default_timezone()
    start = dt.datetime.combine(season.starts_on, dt.time.min, tzinfo=tz)
    end = dt.datetime.combine(season.ends_on + dt.timedelta(days=1), dt.time.min, tzinfo=tz)
    return start, end


def _divisions(club: Club, night: Night | None, division: Division | None) -> QuerySet:
    divisions = Division.objects.filter(night__club=club).select_related("night")
    if night is not None:
        divisions = divisions.filter(night=night)
    if division is not None:
        divisions = divisions.filter(pk=division.pk)
    return divisions.order_by("night__weekday", "name", "pk")


def league_by_team(club: Club, team_ids) -> dict[int, Sums]:
    """League sums per Team: its account, Team credit, and credit returned from its
    payments (a Player's own payment comes back as that Player's credit, naming the
    payment, so it is found through the payment's Team)."""
    entries = LedgerEntry.objects.filter(club=club, category=Category.LEAGUE).filter(
        Q(team_id__in=team_ids) | Q(source__team_id__in=team_ids)
    )
    return _grouped(entries, Coalesce(F("team_id"), F("source__team_id")))


def friendly_by_division(club: Club, season: Season, division_ids) -> dict[int, Sums]:
    entries = LedgerEntry.objects.filter(
        club=club,
        category=Category.FRIENDLY,
        fixture__season=season,
        fixture__division_id__in=division_ids,
    )
    return _grouped(entries, F("fixture__division_id"))


def booking_line(club: Club, season: Season) -> IncomeLine:
    start, end = season_window(season)
    entries = LedgerEntry.objects.filter(
        club=club,
        category=Category.BOOKING,
        booking__starts_at__gte=start,
        booking__starts_at__lt=end,
    )
    return IncomeLine.of(_total(entries))


def user_credit_held(club: Club, subject: str) -> Decimal:
    """Credit held now by all of the Club's Players (or Booking Users), together."""
    sums = _total(LedgerEntry.objects.filter(club=club, subject=subject))
    return sums.net("user_credit") - sums.net("user_credit_spent")


def _team_figures(team: Team, sums: Sums) -> LeagueFigures:
    expected = sums.net("charge")
    paid = sum((sums.method(m) for m in Method.values), ZERO)
    return LeagueFigures(
        teams=1 if team.status == Team.Status.ACTIVE else 0,
        expected=expected,
        outstanding=max(expected - paid, ZERO),
        team_credit_held=sums.net("team_credit") - sums.net("team_credit_spent"),
        league=IncomeLine.of(sums),
    )


def season_summary(
    club: Club,
    season: Season,
    *,
    night: Night | None = None,
    division: Division | None = None,
) -> SeasonSummary:
    """FR-25 and FR-49: the Season's totals per Night and Division, with friendly and
    booking income as their own lines. With a Night or Division filter, club-wide figures
    (bookings, Player and Booking User credit) are left out (None)."""
    divisions = list(_divisions(club, night, division))
    division_ids = [d.pk for d in divisions]
    teams = list(Team.objects.filter(club=club, season=season, division_id__in=division_ids))
    by_team = league_by_team(club, [t.pk for t in teams])
    friendly = friendly_by_division(club, season, division_ids)

    per_division = {d.pk: DivisionFigures(division=d) for d in divisions}
    for team in teams:
        per_division[team.division_id].add(_team_figures(team, by_team.get(team.pk, Sums())))
    for division_id, sums in friendly.items():
        per_division[division_id].friendly = IncomeLine.of(sums)

    nights: list[NightFigures] = []
    totals = LeagueFigures()
    for figures in per_division.values():
        if not nights or nights[-1].night.pk != figures.division.night_id:
            nights.append(NightFigures(night=figures.division.night))
        nights[-1].divisions.append(figures)
        nights[-1].add(figures)
        totals.add(figures)

    club_wide = night is None and division is None
    return SeasonSummary(
        season=season,
        night=night,
        division=division,
        totals=totals,
        booking=booking_line(club, season) if club_wide else None,
        credit_held=CreditHeld(
            team=totals.team_credit_held,
            player=user_credit_held(club, Subject.PLAYER) if club_wide else None,
            booking_user=user_credit_held(club, Subject.BOOKING_USER) if club_wide else None,
        ),
        nights=nights,
    )


def comparison(club: Club, seasons: list[Season]) -> list[SeasonSummary]:
    """FR-27: each Season's income, Night by Night, to compare them side by side."""
    return [season_summary(club, season) for season in seasons]
