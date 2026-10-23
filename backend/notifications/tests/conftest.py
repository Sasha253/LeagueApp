import pytest

from fixtures.tests import conftest as fixture_fixtures
from teams.tests import conftest as team_fixtures

# The Teams and Fixtures tests' pytest fixtures, used here too.
season = team_fixtures.season
division = team_fixtures.division
make_team = team_fixtures.make_team
friday_division = team_fixtures.friday_division
next_tuesday = fixture_fixtures.next_tuesday
pitch = fixture_fixtures.pitch
make_fixture = fixture_fixtures.make_fixture


@pytest.fixture
def player(make_user, tuesday):
    """A Player opted into Club A's Tuesday unless `nights` says otherwise."""

    def make(name, position="outfield", nights=None):
        user = make_user(f"{name}@example.com", position=position, name=name.title())
        user.player_profile.nights.set([tuesday] if nights is None else nights)
        return user

    return make


@pytest.fixture
def match(make_team, make_fixture, player):
    """Red Lions (Captain Thandi, Sipho) vs Old Boys (Captain Pieter, a goalkeeper, Ayanda)."""
    people = {
        "thandi": player("thandi"),
        "sipho": player("sipho"),
        "pieter": player("pieter", "goalkeeper"),
        "ayanda": player("ayanda", "both"),
    }
    lions = make_team("Red Lions", people["thandi"], people["sipho"])
    boys = make_team("Old Boys", people["pieter"], people["ayanda"])
    fixture = make_fixture(lions, boys)
    return fixture, people
