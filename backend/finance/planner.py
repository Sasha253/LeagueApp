"""The income planner (FR-47): expected league income week by week for a Season, built from
the fixture list, with what has come in overlaid so shortfalls show early.

Nothing here writes. Definitions (docs/DECISIONS.md, chunk 27):

- **Weeks** are the Season's own: week 1 starts on the Season's first day (South African
  date), each week is seven days, and the last ends on the Season's last day.
- **expected**: each Team's league fees charged (as on the Finances summary) are spread
  evenly over its Fixtures in the Season, to the cent (the last Fixture takes the odd
  cents), and fall in the week each Fixture kicks off. Cancelled Fixtures are left out.
  A Team charged but with no Fixtures yet is **unscheduled**: in the Season's expected,
  in no week.
- **covered**: what a Team has paid (card, cash and credit, as on its Team ledger), never
  more than it was charged, covers its own Fixtures in date order, then its unscheduled
  part. One Team paying ahead never hides another Team's shortfall.
- **short**: expected less covered, for weeks that have started (they are **due**); a week
  still to come is never short.
- **received**: card and cash taken that week for the Teams in scope (less refunds and
  reversals, on the day each entry was made). Money taken before the Season started counts
  in week 1, after it ended in the last week.
"""

import datetime as dt
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal

from django.db.models import Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from clubs.models import Club, Division, Night, Season
from fixtures.models import Fixture
from ledger.models import LedgerEntry
from teams.models import Team

from .services import CENT, ZERO, Category, Method, Sums, _divisions, _grouped, league_by_team

WEEK = dt.timedelta(days=7)


@dataclass
class Week:
    week: int
    starts_on: dt.date
    ends_on: dt.date
    is_due: bool
    is_current: bool
    matches: int = 0
    expected: Decimal = ZERO
    covered: Decimal = ZERO
    received: Decimal = ZERO

    @property
    def short(self) -> Decimal:
        return self.expected - self.covered if self.is_due else ZERO


@dataclass
class TeamPlan:
    """One Team's fees spread over its Fixtures: (week, expected, covered) in date order;
    week None is the unscheduled part."""

    team: Team
    charged: Decimal
    paid: Decimal
    parts: list[tuple[int | None, Decimal, Decimal]] = field(default_factory=list)

    def short_since(self, due_weeks: int) -> int | None:
        """The first week that has started and isn't fully covered."""
        for week, expected, covered in self.parts:
            if week is not None and week <= due_weeks and covered < expected:
                return week
        return None


@dataclass
class Plan:
    season: Season
    night: Night | None
    division: Division | None
    weeks: list[Week]
    unscheduled: Decimal
    teams: list[TeamPlan]

    @property
    def current_week(self) -> int | None:
        return next((w.week for w in self.weeks if w.is_current), None)

    @property
    def season_expected(self) -> Decimal:
        return sum((w.expected for w in self.weeks), ZERO) + self.unscheduled

    @property
    def due_to_date(self) -> Decimal:
        return sum((w.expected for w in self.weeks if w.is_due), ZERO)

    @property
    def covered_to_date(self) -> Decimal:
        return sum((w.covered for w in self.weeks if w.is_due), ZERO)

    @property
    def behind(self) -> Decimal:
        return self.due_to_date - self.covered_to_date

    @property
    def received(self) -> Decimal:
        return sum((w.received for w in self.weeks), ZERO)


def local_today() -> dt.date:
    return timezone.localdate()


def season_weeks(season: Season, today: dt.date) -> list[Week]:
    weeks = []
    start = season.starts_on
    while start <= season.ends_on:
        end = min(start + WEEK - dt.timedelta(days=1), season.ends_on)
        weeks.append(
            Week(
                week=len(weeks) + 1,
                starts_on=start,
                ends_on=end,
                is_due=start <= today,
                is_current=start <= today <= end,
            )
        )
        start += WEEK
    return weeks


def week_of(season: Season, day: dt.date, count: int) -> int:
    """The Season week a date falls in; dates outside the Season go to the first or last."""
    return min(max((day - season.starts_on).days // 7 + 1, 1), count)


def _split(total: Decimal, parts: int) -> list[Decimal]:
    base = (total / parts).quantize(CENT, rounding=ROUND_DOWN)
    shares = [base] * parts
    shares[-1] += total - base * parts
    return shares


def _local_day(moment: dt.datetime) -> dt.date:
    return timezone.localtime(moment).date()


def team_plans(club: Club, season: Season, teams: list[Team], count: int) -> list[TeamPlan]:
    """Each Team's league fees spread over its Fixtures and covered by what it paid."""
    if count == 0:
        return []
    ids = [t.pk for t in teams]
    sums = league_by_team(club, ids)
    days: dict[int, list[dt.date]] = {pk: [] for pk in ids}
    fixtures = (
        Fixture.objects.filter(club=club, season=season)
        .exclude(status=Fixture.Status.CANCELLED)
        .filter(Q(home_team_id__in=ids) | Q(away_team_id__in=ids))
        .order_by("kick_off", "pk")
        .values_list("home_team_id", "away_team_id", "kick_off")
    )
    for home, away, kick_off in fixtures:
        for team_id in {home, away}:
            if team_id in days:
                days[team_id].append(_local_day(kick_off))

    plans = []
    for team in teams:
        team_sums = sums.get(team.pk, Sums())
        charged = team_sums.net("charge")
        if charged <= 0:
            continue
        paid = sum((team_sums.method(m) for m in Method.values), ZERO)
        weeks: list[int | None] = [week_of(season, d, count) for d in days[team.pk]] or [None]
        left = min(max(paid, ZERO), charged)
        plan = TeamPlan(team=team, charged=charged, paid=paid)
        for week, expected in zip(weeks, _split(charged, len(weeks)), strict=True):
            covered = min(expected, left)
            left -= covered
            plan.parts.append((week, expected, covered))
        plans.append(plan)
    return plans


def planner(
    club: Club,
    season: Season,
    *,
    night: Night | None = None,
    division: Division | None = None,
    today: dt.date | None = None,
) -> Plan:
    today = today or local_today()
    weeks = season_weeks(season, today)
    count = len(weeks)
    division_ids = [d.pk for d in _divisions(club, night, division)]
    teams = list(
        Team.objects.filter(club=club, season=season, division_id__in=division_ids).order_by("pk")
    )
    plans = team_plans(club, season, teams, count)

    unscheduled = ZERO
    for plan in plans:
        for week, expected, covered in plan.parts:
            if week is None:
                unscheduled += expected
            else:
                weeks[week - 1].expected += expected
                weeks[week - 1].covered += covered

    if count:
        kick_offs = (
            Fixture.objects.filter(club=club, season=season, division_id__in=division_ids)
            .exclude(status=Fixture.Status.CANCELLED)
            .values_list("kick_off", flat=True)
        )
        for kick_off in kick_offs:
            weeks[week_of(season, _local_day(kick_off), count) - 1].matches += 1

        entries = LedgerEntry.objects.filter(
            club=club, category=Category.LEAGUE, team_id__in=[t.pk for t in teams]
        )
        by_day = _grouped(entries, TruncDate("created_at", tzinfo=timezone.get_default_timezone()))
        for day, sums in by_day.items():
            weeks[week_of(season, day, count) - 1].received += sums.method(
                Method.CARD
            ) + sums.method(Method.CASH)

    return Plan(
        season=season,
        night=night,
        division=division,
        weeks=weeks,
        unscheduled=unscheduled,
        teams=plans,
    )
