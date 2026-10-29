"""Fills clubs with demo data for local development: `manage.py seed_demo "Club name" ...`.

Club names come from the command line, never from code (CLAUDE.md). A club that doesn't
exist yet is created. For each club it adds this Summer's Season and last Winter's (for the
finance comparison), two Nights with two Divisions each, three Fields with Referees, an
Admin, Teams of Players, a weekly round-robin of Fixtures (past ones played), league fees
with paid, part-paid and unpaid Teams, join requests and field Bookings.

The first Night is the day it runs, so every screen has something on it:

- Tonight, kicking off four to five hours after seeding (with the default T-6h check): a
  match ready to play, with a borrowed Player and its home Team scanned in at the gate; a
  friendly both Teams dropped out of, with Players joined and part of its fee paid; a slot
  offered to the Teams resting tonight, still open; and an unpaid Team waiting for the
  Admin's ruling.
- Tomorrow: Confirmations out and mostly answered, an open Goalkeeper Request, and a
  Captain's postponement and cancellation waiting for the Admin.
- Next week: a match moved to a later kick-off.
- Bookings: one played and paid, one today paid in cash, and coming ones in every state.

It gets there through the app's own services, replaying each match with the clock moved
(time-machine): the T-36h Confirmations, the answers, the resend and the T-6h check happen
at their own times. So the ledger, Barcodes, Fixture transitions, Notifications and Booking
events are what the app itself would have written.

A club that already has the demo Season is skipped. Every demo user's email ends in
@example.com and shares one password; the logins to demo with are printed at the end.
Only runs with DEBUG on.
"""

import datetime as dt
import random
from contextlib import contextmanager
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import ClubInvite, ClubRole, PlayerProfile, User
from accounts.testers import make_test_users
from barcodes import services as barcodes
from barcodes.models import BarcodeScan
from bookings import policy
from bookings import services as bookings
from clubs.models import Club, Division, Field, Night, Season
from core.exceptions import Conflict
from fixtures import borrowing, checkpoints, confirmations, friendlies, lifecycle, reschedules
from fixtures.imports import local_kick_off
from fixtures.models import (
    CaptainRequest,
    ConfirmationAnswer,
    Fixture,
    FixtureTransition,
    FriendlyFee,
    FriendlyInvite,
    PlayerRequest,
    PlayerRequestInvite,
    ReplacementCandidate,
)
from ledger import services as ledger
from ledger.models import LedgerEntry
from notifications import services as notifications
from notifications.models import Answer
from payments import services as payments
from teams.models import JoinRequest, Team, TeamMembership

SEASON_NAME = "Summer 2026"
SEASON_STARTS = dt.date(2026, 10, 1)
SEASON_ENDS = dt.date(2027, 3, 31)
LAST_SEASON = ("Winter 2026", dt.date(2026, 4, 1), dt.date(2026, 9, 30))
LAST_SEASON_TEAMS = 3  # Per Division.
WEEKS_AHEAD = 4
TEAM_SIZE = 8
FREE_GOALKEEPERS = 3
FREE_PLAYERS = 10
BOOKING_USERS = 4
DEFAULT_PASSWORD = "league-demo-2026"  # noqa: S105 Demo users on a local database only.
SUPERUSER_EMAIL = "super@example.com"
CENT = Decimal("0.01")
Value = ConfirmationAnswer.Value
Via = ConfirmationAnswer.Via

# Settings the demo needs, set only where the club hasn't set them.
SETTINGS = {
    "league_fee": Decimal("3500.00"),
    "friendly_fee": Decimal("400.00"),
    "booking_hourly_fee": Decimal("600.00"),
    "match_length_minutes": 50,
}
# (name, usual kick-off, league fee override, Teams). Division 2 has more Teams than fit on
# the league pitches: two rest each week, and can take a slot another Team drops out of.
DIVISIONS = [
    ("Division 1", dt.time(19, 0), Decimal("4000.00"), 4),
    ("Division 2", dt.time(20, 0), None, 6),
]
LEAGUE_PITCHES = ["Pitch 1", "Pitch 2"]
BOOKING_PITCH = "Pitch 3"
DECLINE_REASON = "Division is full this Season."
# How Teams pay their league fee, in turn; a part of the demo can need a Team paid or not.
PAYS = ("cash", "card", "part", "none")
PAID = ("cash", "card")

# The logins to demo with: the start of each one's email, and what it shows.
LOGINS = {
    "admin": "Admin: Tonight, requests, payments, finances, bookings, gate",
    "referee": "Referee of Pitch 1: scan Barcodes at the gate",
    "captain": "Captain of a Team ready tonight: Barcode, Player Request, a join request",
    "standby": "Captain of a Team resting tonight: take the open slot from the inbox",
    "owing": "Captain of an unpaid Team waiting for the Admin's ruling: pay what's owed",
    "player": "Player in tomorrow's match: answer the Confirmation",
    "keeper": "Goalkeeper in no Team: join tonight's friendly, take the Goalkeeper Request",
    "booker": "Booking User: a paid booking today, a played one and coming ones",
}


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
    Vikings, Galacticos, Hotshots, Highveld Hawks, Dune Runners, Lekker Ballers, Shosholoza FC
""",
    ",",
)


@contextmanager
def travel(moment: dt.datetime):
    """Runs the block with the clock stopped at `moment` (always one already past)."""
    import time_machine  # A dev requirement, like this command.

    with time_machine.travel(moment, tick=False):
        yield


def hours(value: float) -> dt.timedelta:
    return dt.timedelta(hours=value)


def minutes(value: float) -> dt.timedelta:
    return dt.timedelta(minutes=value)


class Command(BaseCommand):
    help = "Fills the named clubs with demo data (local development only)."

    def add_arguments(self, parser):
        parser.add_argument("clubs", nargs="+", help="Club names; missing clubs are created.")
        parser.add_argument("--password", default=DEFAULT_PASSWORD)

    def handle(self, *args, clubs, password, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo only runs with DEBUG on.")
        today = timezone.localdate()
        if not SEASON_STARTS <= today < SEASON_ENDS:
            raise CommandError(
                f"The demo's {SEASON_NAME} Season runs {SEASON_STARTS:%d %b %Y} to "
                f"{SEASON_ENDS:%d %b %Y}, so it can't be seeded today. Move SEASON_STARTS and "
                "SEASON_ENDS in this command."
            )
        seeded = []
        for name in clubs:
            club, created = Club.objects.get_or_create(name=name)
            if Season.objects.filter(club=club, name=SEASON_NAME).exists():
                self.stdout.write(f"{club}: already has {SEASON_NAME}, skipped.")
                continue
            seeder = Seeder(club, password, self.stdout)
            with transaction.atomic():
                seeder.run()
            seeded.append(seeder)
            self.stdout.write(
                self.style.SUCCESS(f"{club}: seeded{' (new club)' if created else ''}.")
            )
        if not User.objects.filter(email=SUPERUSER_EMAIL).exists():
            User.objects.create_superuser(SUPERUSER_EMAIL, password, name="Demo Superuser")
        ran = checkpoints.run_due()
        self.stdout.write(f"Checkpoints run: {ran}")
        unanswered = {user.pk for seeder in seeded for user in seeder.logins.values()}
        answered = answer_confirmations(
            [Club.objects.get(name=name) for name in clubs], skip=unanswered
        )
        self.stdout.write(f"Confirmations answered: {answered}")
        # After the replay, so no Request or Confirmation went to them.
        for seeder in seeded:
            make_test_users(seeder.club)
        self.logins(seeded, password)

    def logins(self, seeded: list["Seeder"], password: str) -> None:
        self.stdout.write("")
        self.stdout.write(f"Every demo user's password: {password}")
        self.stdout.write(f"  {SUPERUSER_EMAIL:<28} Superuser: every club (All clubs, imports)")
        self.stdout.write("  The superuser can also sign in as each club's test users (Log in as).")
        for seeder in seeded:
            kick_off = timezone.localtime(seeder.first_kick_off)
            self.stdout.write(f"{seeder.club}, tonight's first kick-off {kick_off:%H:%M}:")
            for role, user in seeder.logins.items():
                self.stdout.write(f"  {user.email:<28} {LOGINS[role]}")


class Seeder:
    def __init__(self, club: Club, password: str, out):
        self.club = club
        self.password = make_password(password)  # Hashed once: hashing is slow on purpose.
        self.out = out
        self.rng = random.Random(club.pk)  # noqa: S311 Repeatable demo data, not security.
        self.count = 0
        self.now = timezone.now()
        self.today = timezone.localdate(self.now)
        self.set_up_at = local_kick_off(SEASON_STARTS - dt.timedelta(days=10), dt.time(10))
        self.first_kick_off = self.tonight_kick_off()
        self.weekdays = (self.today.weekday(), (self.today + dt.timedelta(days=1)).weekday())
        self.matches: dict[tuple[dt.date, int], list[Fixture]] = {}
        self.division_teams: dict[int, list[Team]] = {}
        self.logins: dict[str, User] = {}
        self.standby = self.player_in_demo = self.booker = None

    def tonight_kick_off(self) -> dt.datetime:
        """Tonight's first kick-off (Division 1; Division 2 an hour later). Late enough that
        each slot offered to other Teams is still open, and early enough that the club's
        T-6h check has run, an hour ago or more, for every match tonight."""
        readiness = self.club.settings.readiness_hours_before
        on_the_hour = timezone.localtime(self.now).replace(minute=0, second=0, microsecond=0)
        kick_off = on_the_hour + hours(readiness - 2)
        last = kick_off + hours(len(DIVISIONS) - 1)
        if readiness < 3 or timezone.localdate(last) != self.today:
            raise CommandError(
                f"Tonight's demo matches would kick off at {timezone.localtime(kick_off):%H:%M} "
                f"(the club checks readiness {readiness} hours before). Seed earlier in the "
                "day, so they kick off today."
            )
        return kick_off

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
        with travel(self.set_up_at):
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
            self.names = iter(self.rng.sample(TEAM_NAMES, len(TEAM_NAMES)))
            teams = self.divisions()
            plan = self.cast(teams)
            self.free = self.free_players()
        self.waiting_teams()
        self.join_requests(teams)
        self.money(teams, plan)
        self.last_season()
        self.tonight()
        self.tomorrow()
        self.next_week()
        self.bookings()
        ClubInvite.objects.create(
            club=self.club,
            email=f"new.referee.club{self.club.pk}@example.com",
            role=ClubRole.Role.REFEREE,
            invited_by=self.admin,
        )
        self.name_logins()

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

    def divisions(self) -> list[Team]:
        teams = []
        for night in self.nights:
            for index, (name, kick_off, fee, count) in enumerate(DIVISIONS):
                division, _ = Division.objects.get_or_create(
                    night=night,
                    name=name,
                    defaults={
                        "min_players": self.club.settings.division_min_players,
                        "league_fee": fee,
                    },
                )
                division_teams = [self.team(division, next(self.names)) for _ in range(count)]
                self.division_teams[division.pk] = division_teams
                self.fixtures(division, division_teams, kick_off, index)
                teams += division_teams
        return teams

    def on(self, day: dt.date, night: int, division: int) -> list[Fixture]:
        """The matches of a Night's Division on `day`, by pitch."""
        division_id = Division.objects.get(night=self.nights[night], name=DIVISIONS[division][0]).pk
        return self.matches.get((day, division_id), [])

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
            decided_at=timezone.now() if decided else None,
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

    def waiting_teams(self) -> None:
        division = Division.objects.get(night=self.nights[-1], name=DIVISIONS[-1][0])
        self.team(division, next(self.names), Team.Status.REQUESTED)
        self.team(division, next(self.names), Team.Status.DECLINED)

    def free_players(self) -> list[User]:
        """Players in no Team, opted into both Nights: for Player and Goalkeeper Requests,
        friendlies and join requests. Goalkeepers first."""
        positions = [PlayerProfile.Position.GOALKEEPER] * FREE_GOALKEEPERS
        positions += [PlayerProfile.Position.OUTFIELD] * (FREE_PLAYERS - FREE_GOALKEEPERS)
        return [self.player(position, self.nights) for position in positions]

    def join_requests(self, teams: list[Team]) -> None:
        """One to the Team of the Captain demo login, two to others."""
        others = [team for team in teams if team != self.ready.home_team]
        asked = [self.ready.home_team, *self.rng.sample(others, 2)]
        for player, team in zip(self.free[-3:], asked, strict=True):
            JoinRequest.objects.create(team=team, player=player)

    # Fixtures

    def fixtures(self, division: Division, teams: list[Team], kick_off_time, index) -> None:
        """A weekly round-robin from the Season's start to WEEKS_AHEAD weeks from now, on the
        league pitches. Tonight's matches kick off at the demo's times."""
        rounds = round_robin(teams)
        pitches = self.pitches[: len(LEAGUE_PITCHES)]
        day = SEASON_STARTS + dt.timedelta(
            days=(division.night.weekday - SEASON_STARTS.weekday()) % 7
        )
        last = self.today + dt.timedelta(weeks=WEEKS_AHEAD)
        week = 0
        while day <= last:
            if day == self.today:
                kick_off = self.first_kick_off + hours(index)
            else:
                kick_off = local_kick_off(day, kick_off_time)
            pairs = rounds[week % len(rounds)]
            self.matches[(day, division.pk)] = [
                self.fixture(division, pitch, kick_off, home, away, week)
                for (home, away), pitch in zip(pairs, pitches, strict=False)
            ]
            day += dt.timedelta(weeks=1)
            week += 1

    def fixture(self, division, pitch, kick_off, home, away, week) -> Fixture:
        fixture = Fixture.objects.create(
            club=self.club,
            season=self.season,
            division=division,
            pitch=pitch,
            kick_off=kick_off,
            home_team=home,
            away_team=away,
            friendly_eligible=week % 3 == 0 or timezone.localdate(kick_off) == self.today,
            status=Fixture.Status.SCHEDULED,
        )
        lifecycle.log_creation(fixture, cause=FixtureTransition.Cause.IMPORT, actor=self.admin)
        if timezone.localdate(kick_off) >= self.today:
            return fixture
        if self.rng.random() < 0.08:
            with travel(kick_off - hours(3)):
                lifecycle.transition(
                    fixture,
                    Fixture.Status.CANCELLED,
                    cause=FixtureTransition.Cause.ADMIN,
                    actor=self.admin,
                    note="Pitch waterlogged.",
                )
            return fixture
        with travel(kick_off - hours(self.club.settings.readiness_hours_before)):
            lifecycle.transition(
                fixture, Fixture.Status.READY, cause=FixtureTransition.Cause.SYSTEM
            )
        with travel(kick_off + hours(2)):
            lifecycle.transition(
                fixture, Fixture.Status.PLAYED, cause=FixtureTransition.Cause.SYSTEM
            )
        return fixture

    def cast(self, teams: list[Team]) -> dict[int, str]:
        """Picks tonight's match for each part of the demo, and how each Team pays: every
        Team that must be paid for its part is."""
        self.ready, self.friendly = self.on(self.today, 0, 0)
        self.offered, self.waiting = self.on(self.today, 0, 1)
        playing = {team.pk for f in (self.offered, self.waiting) for team in teams_of(f)}
        division_teams = self.division_teams[self.offered.division_id]
        self.resting = [team for team in division_teams if team.pk not in playing]
        plan = {team.pk: PAYS[index % len(PAYS)] for index, team in enumerate(teams)}
        must_pay = [*teams_of(self.ready), *teams_of(self.offered), self.waiting.away_team]
        for team in [*must_pay, *self.resting]:
            if plan[team.pk] not in PAID:
                plan[team.pk] = "cash"
        plan[self.ready.home_team.pk] = "card"
        plan[self.waiting.home_team.pk] = "none"
        return plan

    # Money

    def money(self, teams: list[Team], plan: dict[int, str]) -> None:
        """League fees charged before the Season starts, then each Team pays as `plan` says:
        in cash, by card by every Player, part by card, or not yet. Paying in full issues the
        Team's Barcode. One cash payment, recorded against the wrong Team, is reversed."""
        wrong = None
        for index, team in enumerate(teams):
            paid_at = self.set_up_at + dt.timedelta(days=3, hours=5 * index)
            with travel(paid_at):
                ledger.charge_league_fee(team, recorded_by=self.admin)
                owed = ledger.team_balance(team).outstanding
                players = [m.player for m in team.current_memberships().order_by("player_id")]
                share = (owed / len(players)).quantize(CENT)
                match plan[team.pk]:
                    case "cash":
                        payments.record_cash(team=team, admin=self.admin, amount=owed)
                    case "card":
                        paid = Decimal("0")
                        for i, player in enumerate(players):
                            amount = owed - paid if i == len(players) - 1 else share
                            self.card(team, player, amount)
                            paid += amount
                    case "part":
                        for player in players[:3]:
                            self.card(team, player, share)
                        if wrong is None:
                            wrong = payments.record_cash(
                                team=team, admin=self.admin, amount=Decimal("500.00")
                            )
                            with travel(paid_at + hours(20)):
                                ledger.reverse(
                                    wrong,
                                    reason="Recorded against the wrong Team.",
                                    recorded_by=self.admin,
                                )
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

    def last_season(self) -> None:
        """Last Winter, for the finance comparison: some of this Season's Teams played it
        too, with the same Captains. All paid in cash but the last, which still owes half."""
        name, starts_on, ends_on = LAST_SEASON
        if Season.objects.filter(club=self.club, name=name).exists():
            return
        signed_up = local_kick_off(starts_on - dt.timedelta(days=14), dt.time(10))
        left_at = local_kick_off(ends_on, dt.time(22))
        with travel(signed_up):
            season = Season.objects.create(
                club=self.club, name=name, starts_on=starts_on, ends_on=ends_on
            )
        returning = [
            team for teams in self.division_teams.values() for team in teams[:LAST_SEASON_TEAMS]
        ]
        for index, current in enumerate(returning):
            with travel(signed_up + hours(index)):
                team = Team.objects.create(
                    club=self.club,
                    season=season,
                    division=current.division,
                    name=current.name,
                    captain=current.captain,
                    status=Team.Status.ACTIVE,
                    requested_by=current.captain,
                    decided_by=self.admin,
                    decided_at=timezone.now(),
                )
                for membership in current.current_memberships().order_by("player_id")[:6]:
                    TeamMembership.objects.create(
                        team=team, player=membership.player, joined_at=signed_up, left_at=left_at
                    )
                ledger.charge_league_fee(team, recorded_by=self.admin)
            with travel(signed_up + dt.timedelta(days=7 + index)):
                owed = ledger.team_balance(team).outstanding
                last = index == len(returning) - 1
                amount = (owed / 2).quantize(CENT) if last else owed
                payments.record_cash(team=team, admin=self.admin, amount=amount)

    # Tonight

    def tonight(self) -> None:
        """Replays tonight's matches from their T-36h Confirmations to now. How many of each
        Team say they're playing decides where each match lands (fewer than the Division's
        minimum is out); its payments, which Teams wait for the Admin."""
        club_settings = self.club.settings
        tonight = [self.ready, self.friendly, self.offered, self.waiting]
        playing = {
            self.ready.home_team.pk: 5,
            self.ready.away_team.pk: 6,
            self.friendly.home_team.pk: 2,
            self.friendly.away_team.pk: 3,
            self.offered.home_team.pk: 3,
            self.offered.away_team.pk: 7,
            self.waiting.home_team.pk: 6,
            self.waiting.away_team.pk: 7,
        }
        for fixture in tonight:
            opens = fixture.kick_off - hours(club_settings.confirmation_hours_before)
            with travel(opens):
                checkpoints.send_confirmations(fixture.pk, opens)
        answered_at = self.first_kick_off - hours(club_settings.confirmation_hours_before - 1)
        for fixture in tonight:
            for team in teams_of(fixture):
                for i, player in enumerate(squad(team)):
                    yes = playing[team.pk]
                    if i >= yes + 2:
                        break
                    value = Value.CONFIRM if i < yes else Value.DECLINE
                    via = Via.FIXTURE if i % 3 == 0 else Via.NOTIFICATION
                    answered_at += minutes(2)
                    with travel(answered_at):
                        confirmations.answer(fixture, player, value, via=via)
        for fixture in tonight:
            opens = fixture.kick_off - hours(club_settings.confirmation_hours_before)
            resend = opens + hours(club_settings.confirmation_resend_after_hours)
            with travel(resend):
                checkpoints.resend_confirmations(fixture.pk, resend)

        # The ready match's home Team is one short of a full squad: it borrows a Player.
        division_1_cutoff = checkpoints.confirmation_cutoff(self.ready, club_settings)
        with travel(division_1_cutoff - hours(3)):
            asked = borrowing.raise_request(
                self.ready, self.ready.home_team.captain, PlayerRequest.Kind.PLAYER, 1
            )
        invite = (
            PlayerRequestInvite.objects.filter(request=asked, player__in=self.free)
            .select_related("notification", "player")
            .order_by("pk")
            .first()
        )
        self.borrowed = invite.player
        with travel(division_1_cutoff - hours(2.5)):
            notifications.answer(invite.notification, Answer.ACCEPT)

        for fixture in (self.ready, self.friendly):
            self.check(fixture, division_1_cutoff)
        self.join_friendly(division_1_cutoff + minutes(5))
        division_2_cutoff = checkpoints.confirmation_cutoff(self.offered, club_settings)
        for fixture in (self.offered, self.waiting):
            self.check(fixture, division_2_cutoff)
        candidates = list(
            ReplacementCandidate.objects.filter(offer__fixture=self.offered)
            .select_related("team__captain", "notification")
            .order_by("team__name")
        )
        if candidates:
            self.standby = candidates[0].team.captain
        for candidate in candidates[1:2]:
            with travel(division_2_cutoff + minutes(30)):
                notifications.answer(candidate.notification, Answer.DECLINE)
        self.gate()

    def check(self, fixture: Fixture, cutoff: dt.datetime) -> None:
        """The T-6h checkpoints, at T-6h."""
        with travel(cutoff):
            checkpoints.check_readiness(fixture.pk, cutoff)
            checkpoints.send_reminders(fixture.pk, cutoff)

    def join_friendly(self, start: dt.datetime) -> None:
        """Players in no Team join the friendly; the Admin sets its fee, paid by those who
        joined, and makes the first its Captain; two pay their share in cash. The Goalkeeper
        demo login and the Player borrowed for the other match leave their invite open."""
        invites = {
            invite.player_id: invite
            for invite in FriendlyInvite.objects.filter(
                fallback__fixture=self.friendly
            ).select_related("notification")
        }
        keeper = self.free[0]
        answering = [p for p in self.free if p not in (keeper, self.borrowed) and p.pk in invites]
        joined = answering[:6]
        for i, player in enumerate(answering):
            value = Answer.CONFIRM if player in joined else Answer.DECLINE
            with travel(start + minutes(4 * i)):
                notifications.answer(invites[player.pk].notification, value)
        if not joined:
            return
        fee = self.club.settings.friendly_fee
        with travel(start + minutes(40)):
            friendlies.set_terms(
                self.friendly,
                fee=fee,
                payer=FriendlyFee.Payer.BORROWED_PLAYERS,
                captain=joined[0],
                by=self.admin,
            )
        share = (fee / len(joined)).quantize(CENT)
        for i, player in enumerate(joined[:2]):
            with travel(start + minutes(45 + i)):
                friendlies.record_cash(self.friendly, player=player, amount=share, by=self.admin)

    def gate(self) -> None:
        """At Pitch 1's gate: the ready match's home Team let in, its Barcode scanned again,
        a mistyped code, and a Team that is out of its match."""
        referee = self.ready.pitch.referee
        home = barcodes.current_for(self.ready.home_team).barcode
        out = barcodes.current_for(self.offered.home_team).barcode
        if home is None:
            return
        mistyped = home.code[:-1] + ("1" if home.code[-1] != "1" else "2")
        scans = [
            (home.code, BarcodeScan.Method.CAMERA),
            (home.code, BarcodeScan.Method.CAMERA),
            (mistyped, BarcodeScan.Method.MANUAL),
        ]
        if out is not None:
            scans.append((out.code, BarcodeScan.Method.CAMERA))
        for code, method in scans:
            barcodes.scan(code, club=self.club, by=referee, method=method)

    # Tomorrow and next week

    def tomorrow(self) -> None:
        """A Goalkeeper Request still open, and a postponement and a cancellation waiting
        for the Admin. The Confirmations go out with the checkpoints."""
        day = self.today + dt.timedelta(days=1)
        first, _second = self.on(day, 1, 0)
        borrowing.raise_request(first, first.away_team.captain, PlayerRequest.Kind.GOALKEEPER, 1)
        self.player_in_demo = squad(first.home_team)[1]
        third, fourth = self.on(day, 1, 1)
        reschedules.request(
            third,
            third.home_team.captain,
            CaptainRequest.Kind.POSTPONE,
            "Half our squad is away at a wedding.",
        )
        reschedules.request(
            fourth,
            fourth.away_team.captain,
            CaptainRequest.Kind.CANCEL,
            "We can't get five Players together this week.",
        )

    def next_week(self) -> None:
        """The Admin moves a match on next week's second Night to a later kick-off."""
        day = self.today + dt.timedelta(days=8)
        matches = self.on(day, 1, 0)
        if not matches or day > SEASON_ENDS:
            return
        reschedules.reschedule(
            matches[-1],
            local_kick_off(day, dt.time(21, 0)),
            admin=self.admin,
            note="The pitch is taken by a school match until 21:00.",
        )

    # Bookings

    def bookings(self) -> None:
        """On the booking pitch: one played and paid, one later today paid in cash, and over
        the next two Saturdays accepted, waiting, declined and cancelled Bookings."""
        users = [self.user("booker", is_booking_user=True) for _ in range(BOOKING_USERS)]
        self.booker = users[0]
        pitch = self.pitches[-1]
        self.played_booking(users[0], pitch)
        self.booking_today(users[0], pitch)
        saturday = self.today + dt.timedelta(days=(5 - self.today.weekday()) % 7 or 7)
        slots = [
            (saturday, 9, 2, "accept"),
            (saturday, 12, 1, "pending"),
            (saturday, 15, 2, "decline"),
            (saturday + dt.timedelta(weeks=1), 10, 1, "accept"),
            (saturday + dt.timedelta(weeks=1), 13, 3, "pending"),
            (saturday + dt.timedelta(weeks=1), 17, 1, "cancel"),
        ]
        for i, (day, hour, length, outcome) in enumerate(slots):
            user = users[i % len(users)]
            booking = bookings.request(
                user=user,
                club=self.club,
                field=pitch,
                starts_at=local_kick_off(day, dt.time(hour)),
                hours=length,
            )
            if outcome == "accept":
                bookings.accept(booking, by=self.admin)
            elif outcome == "decline":
                bookings.decline(booking, by=self.admin, reason="Pitch maintenance that morning.")
            elif outcome == "cancel":
                bookings.cancel(booking, by=user)

    def played_booking(self, user: User, pitch: Field) -> None:
        starts_at = local_kick_off(self.today - dt.timedelta(days=5), dt.time(10))
        with travel(starts_at - dt.timedelta(days=7)):
            booking = bookings.request(
                user=user, club=self.club, field=pitch, starts_at=starts_at, hours=2
            )
        with travel(starts_at - dt.timedelta(days=6)):
            bookings.accept(booking, by=self.admin)
        due = policy.payment_due_at(booking)
        with travel(due + minutes(1)):
            bookings.take_payment(booking)
        with travel(due + hours(3)):
            owed = ledger.booking_outstanding(booking)
            bookings.record_cash(booking, by=self.admin, amount=owed)
        with travel(starts_at - minutes(10)):
            barcode, _status = barcodes.current_for_booking(booking)
            barcodes.scan(
                barcode.code, club=self.club, by=self.admin, method=BarcodeScan.Method.CAMERA
            )
        with travel(booking.ends_at + hours(1)):
            bookings.settle(booking)

    def booking_today(self, user: User, pitch: Field) -> None:
        on_the_hour = timezone.localtime(self.now).replace(minute=0, second=0, microsecond=0)
        starts_at = on_the_hour + hours(2)
        if timezone.localdate(starts_at) != self.today or starts_at.hour > 22:
            return
        booking = bookings.request(
            user=user, club=self.club, field=pitch, starts_at=starts_at, hours=1
        )
        bookings.accept(booking, by=self.admin)
        bookings.take_payment(booking)
        owed = ledger.booking_outstanding(booking)
        bookings.record_cash(booking, by=self.admin, amount=owed)

    # Logins

    def name_logins(self) -> None:
        """Gives each user to demo with an email that says who they are (LOGINS)."""
        people = {
            "admin": self.admin,
            "referee": self.ready.pitch.referee,
            "captain": self.ready.home_team.captain,
            "standby": self.standby,
            "owing": self.waiting.home_team.captain,
            "player": self.player_in_demo,
            "keeper": self.free[0],
            "booker": self.booker,
        }
        for role, user in people.items():
            if user is None:
                continue
            user.email = f"{role}.club{self.club.pk}@example.com"
            user.save(update_fields=["email"])
            self.logins[role] = user


def teams_of(fixture: Fixture) -> tuple[Team, Team]:
    return fixture.home_team, fixture.away_team


def squad(team: Team) -> list[User]:
    """The Team's Players, its Captain first."""
    players = [m.player for m in team.current_memberships().select_related("player")]
    return sorted(players, key=lambda player: (player.pk != team.captain_id, player.pk))


def round_robin(teams: list) -> list[list[tuple]]:
    """Every pairing once, in rounds where each Team plays once (the circle method)."""
    teams = list(teams)
    rounds = []
    for _ in range(len(teams) - 1):
        half = len(teams) // 2
        rounds.append(list(zip(teams[:half], reversed(teams[half:]), strict=True)))
        teams = [teams[0], teams[-1], *teams[1:-1]]
    return rounds


def answer_confirmations(clubs: list[Club], skip: set[int]) -> int:
    """Most Players of matches taking replies say they're playing; a few say not, and some
    don't answer. The demo logins in `skip` are left to answer in the demo."""
    rng = random.Random(0)  # noqa: S311 Repeatable demo data, not security.
    answered = 0
    taking_replies = Fixture.objects.filter(club__in=clubs, status=Fixture.Status.CONFIRMING)
    for fixture in taking_replies:
        for team in (fixture.home_team, fixture.away_team):
            for membership in team.current_memberships():
                roll = rng.random()
                if roll < 0.2 or membership.player_id in skip:
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
