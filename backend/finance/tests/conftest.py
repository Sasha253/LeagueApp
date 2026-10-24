from decimal import Decimal

import pytest
from django.utils import timezone

from bookings.tests import conftest as booking_fixtures
from clubs.models import Division, Night, Season
from fixtures.models import Fixture
from fixtures.tests import conftest as fixture_fixtures
from ledger import services as ledger
from teams.models import Team

# Other apps' pytest fixtures, used here too.
season = fixture_fixtures.season
division = fixture_fixtures.division
friday_division = fixture_fixtures.friday_division
make_team = fixture_fixtures.make_team
make_fixture = fixture_fixtures.make_fixture
pitch = fixture_fixtures.pitch
next_tuesday = fixture_fixtures.next_tuesday
takes_bookings = booking_fixtures.takes_bookings
day = booking_fixtures.day
book = booking_fixtures.book


@pytest.fixture
def people(make_user):
    names = ["thandi", "sipho", "pieter", "zola", "lerato"]
    return {
        name: make_user(f"{name}@example.com", position="outfield", name=name.title())
        for name in names
    }


@pytest.fixture
def cashier(make_user, give_role, club_a):
    from accounts.models import ClubRole

    user = make_user("cashier@example.com", name="Cash Admin")
    give_role(user, club_a, ClubRole.Role.ADMIN)
    return user


@pytest.fixture
def books(
    club_a, club_b, season, division, friday_division, make_team, make_fixture, people,
    cashier, book, make_user,
):  # fmt: skip
    """Club A's Spring Season, R 350 a Team:

    Tuesday Division 2:
    - Red Lions (Thandi, Sipho): Sipho paid R 100 by card, which came back to him as credit;
      Thandi paid R 250 cash for the Team. R 40 goodwill Team credit.
    - Old Boys (Pieter): R 50 cash, reversed; R 120 card; R 30 Team credit, spent.
    - A friendly in Division 2: Lerato paid R 80 cash.
    Friday Division 1: Night Owls (Zola) owe R 350; Late Starters are waiting (no charge).
    A booking: R 600 card, R 300 of it returned as credit.
    Club B has its own money, which never shows.
    """
    p = people
    lions = make_team("Red Lions", p["thandi"], p["sipho"])
    boys = make_team("Old Boys", p["pieter"])
    owls = make_team("Night Owls", p["zola"], division=friday_division)
    make_team("Late Starters", p["lerato"], division=friday_division, status="requested")
    for team in (lions, boys, owls):
        ledger.charge_league_fee(team)

    card = ledger.record_payment(
        team=lions, amount=Decimal("100"), method="card", recorded_by=None, player=p["sipho"]
    )
    ledger.return_as_credit(card, reason="Match cancelled", recorded_by=cashier)
    ledger.record_payment(team=lions, amount=Decimal("250"), method="cash", recorded_by=cashier)
    ledger.issue_credit(
        club=club_a, amount=Decimal("40"), reason="Goodwill", recorded_by=cashier, team=lions
    )

    wrong = ledger.record_payment(
        team=boys, amount=Decimal("50"), method="cash", recorded_by=cashier
    )
    ledger.reverse(wrong, reason="Wrong Team", recorded_by=cashier)
    ledger.record_payment(team=boys, amount=Decimal("120"), method="card", recorded_by=None)
    ledger.issue_credit(
        club=club_a, amount=Decimal("30"), reason="Goodwill", recorded_by=cashier, team=boys
    )
    ledger.spend_credit(team=boys, amount=Decimal("30"), spent_by=p["pieter"])

    friendly = make_fixture(lions, boys, status=Fixture.Status.FRIENDLY)
    ledger.record_friendly_payment(
        fixture=friendly, player=p["lerato"], amount=Decimal("80"), method="cash",
        recorded_by=cashier,
    )  # fmt: skip

    hirer = make_user("hirer@example.com", booking=True, name="Hannah Hirer")
    booking = book(hirer)
    ledger.record_booking_payment(
        booking=booking, amount=Decimal("600"), method="card", recorded_by=None
    )
    ledger.return_booking_payments(
        booking, Decimal("300"), reason="Cancelled late", recorded_by=None
    )

    _other_club(club_b, make_user)
    return {"lions": lions, "boys": boys, "owls": owls, "friendly": friendly}


def _other_club(club_b, make_user):
    from teams.models import TeamMembership

    today = timezone.localdate()
    other_season = Season.objects.create(club=club_b, name="Spring", starts_on=today, ends_on=today)
    night = Night.objects.create(club=club_b, weekday=Night.Weekday.TUESDAY)
    other_division = Division.objects.create(
        night=night, name="Division 2", min_players=5, league_fee=Decimal("900")
    )
    captain = make_user("b-captain@example.com", position="outfield", name="B Captain")
    team = Team.objects.create(
        club=club_b, season=other_season, division=other_division, name="B Team",
        captain=captain, status="active",
    )  # fmt: skip
    TeamMembership.objects.create(team=team, player=captain, joined_at=timezone.now())
    ledger.charge_league_fee(team)
    ledger.record_payment(team=team, amount=Decimal("900"), method="card", recorded_by=None)
