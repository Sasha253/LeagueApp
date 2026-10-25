"""Fills clubs with demo data for local development: `manage.py seed_demo "Club name" ...`.

Club names come from the command line, never from code (CLAUDE.md). A club that doesn't
exist yet is created. For each club it adds a Season, two Nights with two Divisions each,
three Fields with Referees, an Admin, Teams of Players, a round-robin of Fixtures (past
ones played), league fees with a mix of paid, part-paid and unpaid Teams, join requests and
field Bookings. It goes through the app's services, so the ledger, Barcodes, Fixture
transitions and Booking events are what the app itself would have written. Then it runs
the due timed checkpoints and answers some Confirmations.

A club that already has the demo Season is skipped. Every demo user's email ends in
@example.com and shares one password. Only runs with DEBUG on.
"""

import datetime as dt
import random
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import ClubRole, PlayerProfile, User
from bookings import services as bookings
from clubs.models import Club, Division, Field, Night, Season
from core.exceptions import Conflict
from fixtures import checkpoints, confirmations, lifecycle
from fixtures.imports import local_kick_off
from fixtures.models import ConfirmationAnswer, Fixture, FixtureTransition
from ledger import services as ledger
from ledger.models import LedgerEntry
from payments import services as payments
from teams.models import JoinRequest, Team, TeamMembership

SEASON_NAME = "Summer 2026"
SEASON_STARTS = dt.date(2026, 10, 1)
SEASON_ENDS = dt.date(2027, 3, 31)
WEEKS_AHEAD = 4
TEAM_SIZE = 8
TEAMS_PER_DIVISION = 4
FREE_PLAYERS = 10
BOOKING_USERS = 4
DEFAULT_PASSWORD = "league-demo-2026"  # noqa: S105 Demo users on a local database only.

# Settings the demo needs, set only where the club hasn't set them.
SETTINGS = {
    "league_fee": Decimal("3500.00"),
    "friendly_fee": Decimal("400.00"),
    "booking_hourly_fee": Decimal("600.00"),
    "match_length_minutes": 50,
}
# Each club gets the next pair of weekdays, so clubs play on different Nights.
NIGHT_PAIRS = [
    (Night.Weekday.MONDAY, Night.Weekday.WEDNESDAY),
    (Night.Weekday.TUESDAY, Night.Weekday.THURSDAY),
]
DIVISIONS = [
    ("Division 1", dt.time(19, 0), Decimal("4000.00")),
    ("Division 2", dt.time(20, 0), None),
]
LEAGUE_PITCHES = ["Pitch 1", "Pitch 2"]
BOOKING_PITCH = "Pitch 3"
DECLINE_REASON = "Division is full this Season."


def words(text: str, sep: str | None = None) -> list[str]:
    return [word.strip() for word in text.split(sep)]


FIRST_NAMES = words("""
    Sipho Thabo Lungile Kagiso Pieter Johan Ruan Ayanda Bongani Mandla Tshepo Liam Ethan Kyle
    Jaco Dumisani Siyabonga Andile Neo Lerato Themba Wian Riaan Musa Kabelo Zaid Yusuf Craig
    Brandon Ntokozo Lwazi Tiaan Dylan Keegan Mpho Vusi
""")
LAST_NAMES = words("""
    Dlamini Nkosi Botha Mokoena Naidoo Pillay Khumalo Smith Ndlovu Mahlangu Pretorius Jacobs
    Adams Zulu Steyn Molefe Govender Petersen Mthembu Sithole Fourie Coetzee Kruger Mabaso
""")
TEAM_NAMES = words(
    """
    Red Lions, Blue Bulls FC, Dynamos, Kasi Kings, Atletico Braai, Real Madrink,
    Sporting Lisbon't, Inter Mi Lekker, Old Boys, Fynbos United, Mountain Goats,
    Saturday Legends, Nomads, Wanderers, Spartans, Hooligans XI, Rovers, Thunder, Phoenix,
    Vikings
""",
    ",",
)


class Command(BaseCommand):
    help = "Fills the named clubs with demo data (local development only)."

    def add_arguments(self, parser):
        parser.add_argument("clubs", nargs="+", help="Club names; missing clubs are created.")
        parser.add_argument("--password", default=DEFAULT_PASSWORD)

    def handle(self, *args, clubs, password, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo only runs with DEBUG on.")
        for position, name in enumerate(clubs):
            club, created = Club.objects.get_or_create(name=name)
            if Season.objects.filter(club=club, name=SEASON_NAME).exists():
                self.stdout.write(f"{club}: already has {SEASON_NAME}, skipped.")
                continue
            with transaction.atomic():
                Seeder(club, position, password, self.stdout).run()
            self.stdout.write(
                self.style.SUCCESS(f"{club}: seeded{' (new club)' if created else ''}.")
            )
        ran = checkpoints.run_due()
        self.stdout.write(f"Checkpoints run: {ran}")
        answered = answer_confirmations([Club.objects.get(name=name) for name in clubs])
        self.stdout.write(f"Confirmations answered: {answered}")
        self.stdout.write(f"Every demo user's password: {password}")


class Seeder:
    def __init__(self, club: Club, position: int, password: str, out):
        self.club = club
        self.password = make_password(password)  # Hashed once: hashing is slow on purpose.
        self.out = out
        self.rng = random.Random(club.pk)  # noqa: S311 Repeatable demo data, not security.
        self.weekdays = NIGHT_PAIRS[position % len(NIGHT_PAIRS)]
        self.count = 0
        self.today = timezone.localdate()

    # Users

    def user(self, kind: str, *, name: str | None = None, **fields) -> User:
        self.count += 1
        name = name or f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_NAMES)}"
        email = f"{kind}{self.count:03d}.club{self.club.pk}@example.com"
        phone = f"08{self.rng.randint(10000000, 99999999)}"
        user = User(email=email, password=self.password, name=name, phone=phone, **fields)
        user.save()
        return user

    def player(self, position: str, nights: list[Night]) -> User:
        user = self.user("player")
        PlayerProfile.objects.create(user=user, position=position).nights.set(nights)
        return user

    # Setup

    def run(self) -> None:
        self.settings()
        self.admin = self.user("admin", name=f"{self.rng.choice(FIRST_NAMES)} Admin")
        ClubRole.objects.create(user=self.admin, club=self.club, role=ClubRole.Role.ADMIN)
        self.season = Season.objects.create(
            club=self.club, name=SEASON_NAME, starts_on=SEASON_STARTS, ends_on=SEASON_ENDS
        )
        self.fields()
        self.nights = [
            Night.objects.get_or_create(club=self.club, weekday=weekday)[0]
            for weekday in self.weekdays
        ]
        names = iter(self.rng.sample(TEAM_NAMES, len(TEAM_NAMES)))
        teams = []
        for night in self.nights:
            for division_name, kick_off, fee in DIVISIONS:
                division = Division.objects.create(
                    night=night,
                    name=division_name,
                    min_players=self.club.settings.division_min_players,
                    league_fee=fee,
                )
                division_teams = [
                    self.team(division, next(names)) for _ in range(TEAMS_PER_DIVISION)
                ]
                self.fixtures(division, division_teams, kick_off)
                teams += division_teams
        self.waiting_teams(names)
        self.money(teams)
        self.free_players(teams)
        self.bookings()

    def settings(self) -> None:
        club_settings = self.club.settings
        changed = [name for name, value in SETTINGS.items() if getattr(club_settings, name) is None]
        for name in changed:
            setattr(club_settings, name, SETTINGS[name])
        if changed:
            club_settings.save(update_fields=[*changed, "updated_at"])

    def fields(self) -> None:
        self.pitches = []
        for name in [*LEAGUE_PITCHES, BOOKING_PITCH]:
            referee = None
            if name in LEAGUE_PITCHES:
                referee = self.user("referee")
                ClubRole.objects.create(user=referee, club=self.club, role=ClubRole.Role.REFEREE)
            field, _ = Field.objects.get_or_create(club=self.club, name=name)
            field.referee = referee or field.referee
            field.save(update_fields=["referee"])
            self.pitches.append(field)

    # Teams

    def team(self, division: Division, name: str, status=Team.Status.ACTIVE) -> Team:
        captain = self.player(PlayerProfile.Position.OUTFIELD, [division.night])
        decided = status != Team.Status.REQUESTED
        team = Team.objects.create(
            club=self.club,
            season=self.season,
            division=division,
            name=name,
            captain=captain,
            status=status,
            requested_by=captain,
            decided_by=self.admin if decided else None,
            decided_at=timezone.now() - dt.timedelta(days=30) if decided else None,
            decline_reason=DECLINE_REASON if status == Team.Status.DECLINED else "",
        )
        if status != Team.Status.ACTIVE:
            return team
        positions = [PlayerProfile.Position.GOALKEEPER, PlayerProfile.Position.BOTH]
        positions += [PlayerProfile.Position.OUTFIELD] * (TEAM_SIZE - 3)
        joined = team.decided_at
        TeamMembership.objects.create(team=team, player=captain, joined_at=joined)
        for position in positions:
            player = self.player(position, [division.night])
            TeamMembership.objects.create(team=team, player=player, joined_at=joined)
        return team

    def waiting_teams(self, names) -> None:
        division = Division.objects.filter(night=self.nights[-1], name=DIVISIONS[-1][0]).get()
        self.team(division, next(names), Team.Status.REQUESTED)
        self.team(division, next(names), Team.Status.DECLINED)

    def free_players(self, teams: list[Team]) -> None:
        """Players in no Team: for Player Requests and join requests."""
        positions = [PlayerProfile.Position.GOALKEEPER] * 3 + [PlayerProfile.Position.OUTFIELD] * (
            FREE_PLAYERS - 3
        )
        free = [self.player(position, self.nights) for position in positions]
        for player, team in zip(free[:3], self.rng.sample(teams, 3), strict=True):
            JoinRequest.objects.create(team=team, player=player)

    # Fixtures

    def fixtures(self, division: Division, teams: list[Team], kick_off_time: dt.time) -> None:
        """A weekly round-robin from the Season's start to WEEKS_AHEAD weeks from now."""
        rounds = round_robin(teams)
        day = SEASON_STARTS + dt.timedelta(
            days=(division.night.weekday - SEASON_STARTS.weekday()) % 7
        )
        last = self.today + dt.timedelta(weeks=WEEKS_AHEAD)
        week = 0
        while day <= last:
            for (home, away), pitch in zip(rounds[week % len(rounds)], self.pitches, strict=False):
                self.fixture(division, pitch, local_kick_off(day, kick_off_time), home, away, week)
            day += dt.timedelta(weeks=1)
            week += 1

    def fixture(self, division, pitch, kick_off, home, away, week) -> None:
        fixture = Fixture.objects.create(
            club=self.club,
            season=self.season,
            division=division,
            pitch=pitch,
            kick_off=kick_off,
            home_team=home,
            away_team=away,
            friendly_eligible=week % 3 == 0,
            status=Fixture.Status.SCHEDULED,
        )
        lifecycle.log_creation(fixture, cause=FixtureTransition.Cause.IMPORT, actor=self.admin)
        if timezone.localdate(kick_off) >= self.today:
            return
        if self.rng.random() < 0.08:
            lifecycle.transition(
                fixture,
                Fixture.Status.CANCELLED,
                cause=FixtureTransition.Cause.ADMIN,
                actor=self.admin,
                note="Pitch waterlogged.",
            )
            return
        for status in (Fixture.Status.READY, Fixture.Status.PLAYED):
            lifecycle.transition(fixture, status, cause=FixtureTransition.Cause.SYSTEM)

    # Money

    def money(self, teams: list[Team]) -> None:
        """League fees charged, then by turns: paid in cash, paid by card by every Player,
        part-paid by card, unpaid. Paying in full issues the Team's Barcode."""
        for index, team in enumerate(teams):
            ledger.charge_league_fee(team, recorded_by=self.admin)
            owed = ledger.team_balance(team).outstanding
            players = [m.player for m in team.current_memberships()]
            share = (owed / len(players)).quantize(Decimal("0.01"))
            match index % 4:
                case 0:
                    payments.record_cash(team=team, admin=self.admin, amount=owed)
                case 1:
                    paid = Decimal("0")
                    for i, player in enumerate(players):
                        amount = owed - paid if i == len(players) - 1 else share
                        self.card(team, player, amount)
                        paid += amount
                case 2:
                    for player in players[:3]:
                        self.card(team, player, share)
                case _:
                    pass
        ledger.issue_credit(
            club=self.club,
            amount=Decimal("250.00"),
            reason="Goodwill credit for a match the club cancelled.",
            recorded_by=self.admin,
            team=teams[-1],
        )

    def card(self, team: Team, player: User, amount: Decimal) -> None:
        payments.paying(
            team,
            lambda: ledger.record_payment(
                team=team,
                amount=amount,
                method=LedgerEntry.Method.CARD,
                recorded_by=None,
                player=player,
                reason="Card payment (demo data)",
                money_taken=True,
            ),
        )

    # Bookings

    def bookings(self) -> None:
        """On the booking pitch, over the next two Saturdays: accepted, waiting, declined
        and cancelled Bookings."""
        users = [self.user("booker", is_booking_user=True) for _ in range(BOOKING_USERS)]
        saturday = self.today + dt.timedelta(days=(5 - self.today.weekday()) % 7 or 7)
        pitch = self.pitches[-1]
        slots = [
            (saturday, 9, 2, "accept"),
            (saturday, 12, 1, "pending"),
            (saturday, 15, 2, "decline"),
            (saturday + dt.timedelta(weeks=1), 10, 1, "accept"),
            (saturday + dt.timedelta(weeks=1), 13, 3, "pending"),
            (saturday + dt.timedelta(weeks=1), 17, 1, "cancel"),
        ]
        for i, (day, hour, hours, outcome) in enumerate(slots):
            user = users[i % len(users)]
            booking = bookings.request(
                user=user,
                club=self.club,
                field=pitch,
                starts_at=local_kick_off(day, dt.time(hour)),
                hours=hours,
            )
            if outcome == "accept":
                bookings.accept(booking, by=self.admin)
            elif outcome == "decline":
                bookings.decline(booking, by=self.admin, reason="Pitch maintenance that morning.")
            elif outcome == "cancel":
                bookings.cancel(booking, by=user)


def round_robin(teams: list) -> list[list[tuple]]:
    """Every pairing once, in rounds where each Team plays once (the circle method)."""
    teams = list(teams)
    rounds = []
    for _ in range(len(teams) - 1):
        half = len(teams) // 2
        rounds.append(list(zip(teams[:half], reversed(teams[half:]), strict=True)))
        teams = [teams[0], teams[-1], *teams[1:-1]]
    return rounds


def answer_confirmations(clubs: list[Club]) -> int:
    """Most Players of matches taking replies say they're playing; a few say not, and some
    don't answer."""
    rng = random.Random(0)  # noqa: S311 Repeatable demo data, not security.
    answered = 0
    taking_replies = Fixture.objects.filter(club__in=clubs, status=Fixture.Status.CONFIRMING)
    for fixture in taking_replies:
        for team in (fixture.home_team, fixture.away_team):
            for membership in team.current_memberships():
                roll = rng.random()
                if roll < 0.2:
                    continue
                value = (
                    ConfirmationAnswer.Value.DECLINE
                    if roll < 0.3
                    else ConfirmationAnswer.Value.CONFIRM
                )
                try:
                    confirmations.answer(
                        fixture, membership.player, value, via=ConfirmationAnswer.Via.FIXTURE
                    )
                    answered += 1
                except Conflict:
                    pass
    return answered
