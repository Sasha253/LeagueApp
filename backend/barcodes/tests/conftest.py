from decimal import Decimal

import pytest
from django.utils import timezone

from clubs.models import PaymentMode
from fixtures.tests import conftest as fixture_fixtures
from ledger import services as ledger
from payments import services as payments
from payments.tests import conftest as payment_fixtures

season = payment_fixtures.season
division = payment_fixtures.division
player = payment_fixtures.player
make_team = payment_fixtures.make_team
people = payment_fixtures.people
lions = payment_fixtures.lions
cashier = payment_fixtures.cashier
signed_in = payment_fixtures.signed_in
pitch = fixture_fixtures.pitch
next_tuesday = fixture_fixtures.next_tuesday
make_fixture = fixture_fixtures.make_fixture


@pytest.fixture
def boys(make_team, make_user):
    pieter = make_user("pieter@example.com", position="goalkeeper", name="Pieter")
    return make_team("Old Boys", pieter)


@pytest.fixture
def match(make_fixture, lions, boys):
    """Red Lions vs Old Boys, next Tuesday at 19:40."""
    return make_fixture(lions, boys)


@pytest.fixture
def tonight(make_fixture, lions, boys):
    """Red Lions vs Old Boys today (South African date): the match at the gate now."""
    return make_fixture(lions, boys, date=timezone.localdate(), time="00:01")


@pytest.fixture
def owing(lions):
    """Red Lions owe their R 350 league fee."""
    ledger.charge_league_fee(lions)
    return lions


@pytest.fixture
def pay():
    """Records cash for `team` (R 350 by default) by `admin`: makes it paid."""

    def run(team, admin, amount="350"):
        return payments.record_cash(team=team, admin=admin, amount=Decimal(amount))

    return run


@pytest.fixture
def cash_only(club_a):
    club_settings = club_a.settings
    club_settings.payment_mode = PaymentMode.CASH_ONLY
    club_settings.save()
    return club_settings
