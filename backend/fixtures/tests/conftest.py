import datetime as dt

import pytest
from django.utils import timezone

from accounts.models import ClubRole
from clubs.models import Field
from fixtures import lifecycle
from fixtures.imports import local_kick_off
from fixtures.models import Fixture, FixtureTransition
from teams.tests import conftest as team_fixtures

# The Teams tests' pytest fixtures, used here too.
season = team_fixtures.season
division = team_fixtures.division
friday_division = team_fixtures.friday_division
make_team = team_fixtures.make_team


def next_weekday(weekday: int, after_days: int = 2) -> dt.date:
    """The first date on `weekday` (0 is Monday) at least `after_days` from today."""
    day = timezone.localdate() + dt.timedelta(days=after_days)
    return day + dt.timedelta(days=(weekday - day.weekday()) % 7)


@pytest.fixture
def next_tuesday():
    return next_weekday(1)


@pytest.fixture
def pitch(club_a, make_user, give_role):
    referee = make_user("ref@example.com", name="Rita Referee")
    give_role(referee, club_a, ClubRole.Role.REFEREE)
    return Field.objects.create(club=club_a, name="Pitch 3", referee=referee)


@pytest.fixture
def make_fixture(season, division, pitch, next_tuesday):
    """A scheduled Fixture between `home` and `away`, next Tuesday at `time` by default."""

    def make(home, away, *, time="19:40", date=None, **fields):
        hour, minute = map(int, time.split(":"))
        fields.setdefault("season", season)
        fields.setdefault("division", division)
        fields.setdefault("pitch", pitch)
        fixture = Fixture.objects.create(
            club=fields["season"].club,
            home_team=home,
            away_team=away,
            kick_off=local_kick_off(date or next_tuesday, dt.time(hour, minute)),
            status=fields.pop("status", Fixture.Status.SCHEDULED),
            **fields,
        )
        lifecycle.log_creation(fixture, cause=FixtureTransition.Cause.ADMIN)
        return fixture

    return make


@pytest.fixture
def lions_and_boys(make_team, make_user):
    """Two active Teams of Division 2: Red Lions (Captain Thandi) and Old Boys."""
    thandi = make_user("thandi@example.com", position="outfield", name="Thandi")
    pieter = make_user("pieter@example.com", position="goalkeeper", name="Pieter")
    return make_team("Red Lions", thandi), make_team("Old Boys", pieter)
