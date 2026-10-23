import pytest

from teams.tests import conftest as team_fixtures

# The Teams tests' pytest fixtures, used here too.
season = team_fixtures.season
division = team_fixtures.division
player = team_fixtures.player
make_team = team_fixtures.make_team
friday_division = team_fixtures.friday_division


@pytest.fixture
def people(make_user):
    """Thandi (Captain of Red Lions), Sipho (a Player in it) and Lerato (not in it)."""
    return {
        "thandi": make_user("thandi@example.com", position="outfield", name="Thandi"),
        "sipho": make_user("sipho@example.com", position="outfield", name="Sipho"),
        "lerato": make_user("lerato@example.com", position="goalkeeper", name="Lerato"),
    }


@pytest.fixture
def lions(make_team, people):
    return make_team("Red Lions", people["thandi"], people["sipho"])


@pytest.fixture
def cashier(make_user, give_role, club_a):
    """An Admin of Club A who records cash."""
    from accounts.models import ClubRole

    user = make_user("cashier@example.com", name="Cash Admin")
    give_role(user, club_a, ClubRole.Role.ADMIN)
    return user
