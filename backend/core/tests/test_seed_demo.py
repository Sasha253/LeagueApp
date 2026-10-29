import datetime as dt
from io import StringIO
from zoneinfo import ZoneInfo

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from accounts.models import User
from barcodes.models import Barcode, BarcodeScan
from bookings.models import Booking
from clubs.models import Club, Season
from fixtures.models import (
    BorrowedPlayer,
    CaptainRequest,
    ConfirmationAnswer,
    Fixture,
    FixtureReschedule,
    FriendlyFee,
    PlayerRequest,
    ReplacementOffer,
    TeamReadiness,
)
from ledger import services as ledger
from ledger.models import LedgerEntry
from teams.models import Team

pytestmark = pytest.mark.django_db

S = Fixture.Status
# A Thursday morning in the demo Season.
DEMO_MORNING = dt.datetime(2026, 10, 29, 10, 0, tzinfo=ZoneInfo("Africa/Johannesburg"))


@pytest.fixture
def morning(time_machine):
    time_machine.move_to(DEMO_MORNING, tick=False)


def test_seeds_a_full_demo(settings, morning):
    """One test, as seeding two clubs takes a while."""
    settings.DEBUG = True
    Club.objects.create(name="Club A")
    call_command("seed_demo", "Club A", "Club B", stdout=StringIO())
    seeded = Club.objects.get(name="Club A"), Club.objects.get(name="Club B")

    check_seeds_existing_and_new_clubs(seeded)
    check_tonight_has_each_part_of_the_demo(seeded)
    check_gate_scans_tonight(seeded)
    check_tomorrow_and_next_week(seeded)
    check_logins_to_demo_with(seeded)
    check_money(seeded)
    check_runs_once_per_club(seeded)


def tonight(club) -> list[Fixture]:
    return list(
        club.fixtures.filter(kick_off__date=timezone.localdate()).order_by("kick_off", "pitch")
    )


def check_seeds_existing_and_new_clubs(seeded):
    for club in seeded:
        summer = club.seasons.get(name="Summer 2026")
        assert summer.teams.filter(status=Team.Status.ACTIVE).count() == 20
        assert summer.teams.filter(status=Team.Status.REQUESTED).count() == 1
        assert club.fixtures.filter(status=S.PLAYED).exists()
        assert Booking.objects.filter(club=club, status=Booking.Status.ACCEPTED).count() == 4
        assert Barcode.objects.filter(club=club, booking__isnull=False).count() == 4


def check_tonight_has_each_part_of_the_demo(seeded):
    club = seeded[0]
    ready, friendly, offered, waiting = tonight(club)

    assert [f.status for f in tonight(club)] == [
        S.READY,
        S.FRIENDLY,
        S.REPLACEMENT_OFFERED,
        S.CONFIRMING,
    ]
    assert BorrowedPlayer.objects.filter(fixture=ready, team=ready.home_team).count() == 1
    friendly_fee = FriendlyFee.objects.get(fixture=friendly)
    assert 0 < ledger.friendly_paid(friendly) < friendly_fee.fee
    offer = ReplacementOffer.objects.get(fixture=offered)
    assert offer.status == ReplacementOffer.Status.OPEN
    assert offer.candidates.count() == 2
    assert offer.closes_at > timezone.now()
    pending = TeamReadiness.objects.get(fixture=waiting, outcome=TeamReadiness.Outcome.PENDING)
    assert pending.team == waiting.home_team
    assert pending.reason == TeamReadiness.Reason.UNPAID


def check_gate_scans_tonight(seeded):
    scans = BarcodeScan.objects.filter(club=seeded[0], barcode__booking__isnull=True)

    assert scans.filter(result=BarcodeScan.Result.PAID).count() == 1
    assert scans.filter(result=BarcodeScan.Result.NOT_PAID).count() == 3


def check_tomorrow_and_next_week(seeded):
    club = seeded[0]
    tomorrow = timezone.localdate() + dt.timedelta(days=1)
    matches = club.fixtures.filter(kick_off__date=tomorrow)

    assert {f.status for f in matches} == {S.CONFIRMING}
    assert ConfirmationAnswer.objects.filter(fixture__in=matches).exists()
    assert PlayerRequest.objects.get(fixture__in=matches).kind == PlayerRequest.Kind.GOALKEEPER
    pending = CaptainRequest.objects.filter(
        fixture__in=matches, status=CaptainRequest.Status.PENDING
    )
    assert {r.kind for r in pending} == {CaptainRequest.Kind.CANCEL, CaptainRequest.Kind.POSTPONE}
    assert FixtureReschedule.objects.filter(fixture__club=club).count() == 1


def check_logins_to_demo_with(seeded):
    club = seeded[0]
    roles = ["admin", "referee", "captain", "standby", "owing", "player", "keeper", "booker"]
    for role in roles:
        assert User.objects.filter(email=f"{role}.club{club.pk}@example.com").exists()
    player = User.objects.get(email=f"player.club{club.pk}@example.com")
    assert not ConfirmationAnswer.objects.filter(player=player).exists()
    assert User.objects.get(email="super@example.com").is_superuser
    testers = User.objects.filter(email__endswith=f".club{club.pk}@test.invalid")
    assert testers.filter(is_test_account=True).count() == 5


def check_money(seeded):
    club = seeded[0]
    summer = club.seasons.get(name="Summer 2026")
    teams = summer.teams.filter(status=Team.Status.ACTIVE)
    paid = [team for team in teams if ledger.team_balance(team).is_paid]
    assert 0 < len(paid) < len(teams)
    assert LedgerEntry.objects.filter(club=club, kind=LedgerEntry.Kind.REVERSAL).count() == 1
    winter = Season.objects.get(club=club, name="Winter 2026")
    owing = [team for team in winter.teams.all() if not ledger.team_balance(team).is_paid]
    assert winter.teams.count() == 12
    assert len(owing) == 1


def check_runs_once_per_club(seeded):
    teams = seeded[0].teams.count()

    call_command("seed_demo", "Club A", stdout=StringIO())

    assert seeded[0].teams.count() == teams


def test_refuses_without_debug(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError):
        call_command("seed_demo", "Club A")


def test_refuses_outside_the_season(settings, time_machine):
    settings.DEBUG = True
    time_machine.move_to(dt.datetime(2027, 6, 1, 10, tzinfo=ZoneInfo("Africa/Johannesburg")))

    with pytest.raises(CommandError):
        call_command("seed_demo", "Club A")


def test_refuses_too_late_in_the_day(settings, time_machine):
    settings.DEBUG = True
    time_machine.move_to(DEMO_MORNING.replace(hour=21), tick=False)

    with pytest.raises(CommandError):
        call_command("seed_demo", "Club A", stdout=StringIO())
