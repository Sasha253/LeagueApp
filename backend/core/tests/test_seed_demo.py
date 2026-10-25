from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from barcodes.models import Barcode
from bookings.models import Booking
from clubs.models import Club
from fixtures.models import Fixture
from ledger import services as ledger
from teams.models import Team

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded(settings):
    settings.DEBUG = True
    Club.objects.create(name="Club A")
    call_command("seed_demo", "Club A", "Club B", stdout=StringIO())
    return Club.objects.get(name="Club A"), Club.objects.get(name="Club B")


def test_seeds_existing_and_new_clubs(seeded):
    for club in seeded:
        assert club.teams.filter(status=Team.Status.ACTIVE).count() == 16
        assert club.teams.filter(status=Team.Status.REQUESTED).count() == 1
        assert club.fixtures.filter(status=Fixture.Status.PLAYED).exists()
        assert club.fixtures.filter(kick_off__gt=club.created_at).exists()
        assert Booking.objects.filter(club=club, status=Booking.Status.ACCEPTED).count() == 2
        assert Barcode.objects.filter(club=club, booking__isnull=False).count() == 2


def test_some_teams_are_paid_and_have_barcodes(seeded):
    club = seeded[0]
    teams = club.teams.filter(status=Team.Status.ACTIVE)
    paid = [team for team in teams if ledger.team_balance(team).is_paid]
    assert len(paid) == 8
    assert Barcode.objects.filter(team__in=paid).count() == 8


def test_runs_once_per_club(seeded):
    call_command("seed_demo", "Club A", stdout=StringIO())

    assert seeded[0].teams.count() == 18


def test_refuses_without_debug(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError):
        call_command("seed_demo", "Club A")
