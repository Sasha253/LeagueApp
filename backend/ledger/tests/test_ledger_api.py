"""The read-only ledger API: my credit, Team credit (its Captain) and Team balance."""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from ledger import services
from ledger.models import LedgerEntry

MY_CREDIT = reverse("api-v1:my-credit")


def team_url(name, team):
    return reverse(f"api-v1:team-{name}", kwargs={"team_id": team.pk})


def signed_in(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def money(lions, people, cashier, club_a):
    """Red Lions owe R 350; Sipho paid R 100 by card, then it came back as his credit."""
    services.charge_league_fee(lions)
    payment = services.record_payment(
        team=lions, amount=Decimal("100"), method="card", recorded_by=None, player=people["sipho"]
    )
    services.return_as_credit(payment, reason="Match cancelled", recorded_by=cashier)
    services.issue_credit(
        club=club_a, amount=Decimal("40"), reason="Goodwill", recorded_by=cashier, team=lions
    )
    return payment


# My credit


@pytest.mark.django_db
def test_a_player_sees_their_credit_per_club(money, people, club_a):
    answer = signed_in(people["sipho"]).get(MY_CREDIT)

    assert answer.status_code == 200
    [club] = answer.json()
    assert club["club"] == {"id": club_a.pk, "name": club_a.name}
    assert club["balance"] == "100.00"
    assert [e["kind"] for e in club["entries"]] == ["credit"]
    assert club["entries"][0]["reason"] == "Match cancelled"
    assert club["entries"][0]["recorded_by_name"] == "Cash Admin"


@pytest.mark.django_db
def test_a_player_without_credit_sees_none(money, people):
    assert signed_in(people["lerato"]).get(MY_CREDIT).json() == []


@pytest.mark.django_db
def test_my_credit_is_for_players(money, api, cashier):
    assert api.get(MY_CREDIT).status_code == 401
    assert signed_in(cashier).get(MY_CREDIT).status_code == 403


# Team credit


@pytest.mark.django_db
def test_the_captain_sees_team_credit(money, people, lions):
    answer = signed_in(people["thandi"]).get(team_url("credit", lions))

    assert answer.status_code == 200
    body = answer.json()
    assert body["team"] == {"id": lions.pk, "name": "Red Lions"}
    assert body["balance"] == "40.00"
    assert [e["amount"] for e in body["entries"]] == ["40.00"]


@pytest.mark.django_db
def test_only_the_captain_sees_team_credit(money, people, lions, cashier):
    url = team_url("credit", lions)

    assert signed_in(people["sipho"]).get(url).status_code == 404
    assert signed_in(people["lerato"]).get(url).status_code == 404
    assert signed_in(cashier).get(url).status_code == 403


# Team balance


@pytest.mark.django_db
def test_the_captain_sees_the_team_balance(money, people, lions):
    answer = signed_in(people["thandi"]).get(team_url("balance", lions))

    assert answer.status_code == 200
    body = answer.json()
    assert (body["due"], body["paid"], body["outstanding"]) == ("350.00", "100.00", "250.00")
    assert body["paid_by_method"] == {"card": "100.00", "cash": "0.00", "credit": "0.00"}
    assert [e["kind"] for e in body["entries"]] == ["charge", "payment"]
    assert body["entries"][1]["player"] == {"id": people["sipho"].pk, "name": "Sipho"}


@pytest.mark.django_db
def test_the_clubs_admin_sees_the_team_balance(money, lions, admin_of, club_a):
    assert admin_of(club_a).get(team_url("balance", lions)).status_code == 200


@pytest.mark.django_db
def test_nobody_else_sees_the_team_balance(
    money, lions, people, admin_of, club_b, api, give_role, make_user, club_a
):
    from accounts.models import ClubRole

    referee = make_user("ref@example.com", name="Rita")
    give_role(referee, club_a, ClubRole.Role.REFEREE)
    url = team_url("balance", lions)

    assert api.get(url).status_code == 401
    assert signed_in(people["sipho"]).get(url).status_code == 404
    assert signed_in(people["lerato"]).get(url).status_code == 404
    assert signed_in(referee).get(url).status_code == 404
    assert admin_of(club_b).get(url).status_code == 404


@pytest.mark.django_db
def test_an_unknown_team_is_404(money, people):
    url = reverse("api-v1:team-balance", kwargs={"team_id": 999999})

    assert signed_in(people["thandi"]).get(url).status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_the_ledger_api_only_reads(money, people, lions, method):
    count = LedgerEntry.objects.count()
    client = signed_in(people["thandi"])

    for url in (MY_CREDIT, team_url("credit", lions), team_url("balance", lions)):
        assert getattr(client, method)(url).status_code == 405
    assert LedgerEntry.objects.count() == count
