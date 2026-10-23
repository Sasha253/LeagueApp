"""Who has paid towards a Team (FR-21) and where "Pay my share" starts (Screens.md Player 3)."""

from decimal import Decimal as D

import pytest
from django.urls import reverse
from django.utils import timezone

from ledger import services as ledger
from payments import services


def summary_url(team):
    return reverse("api-v1:team-payment-summary", kwargs={"team_id": team.pk})


def cash(team, admin, amount, player=None):
    return services.record_cash(team=team, admin=admin, amount=D(amount), player=player)


@pytest.mark.django_db
def test_the_captain_sees_who_has_paid(owing, people, signed_in, cashier, club_a):
    cash(owing, cashier, "100", people["sipho"])
    cash(owing, cashier, "50")
    ledger.issue_credit(
        club=club_a, amount=D("20"), reason="Goodwill", recorded_by=cashier, team=owing
    )

    answer = signed_in(people["thandi"]).get(summary_url(owing))

    assert answer.status_code == 200
    assert answer.json() == {
        "team": {"id": owing.pk, "name": "Red Lions"},
        "due": "350.00",
        "paid": "150.00",
        "outstanding": "200.00",
        "is_paid": False,
        "players": [
            {
                "player_id": people["sipho"].pk,
                "name": "Sipho",
                "is_captain": False,
                "in_team": True,
                "paid": "100.00",
                "has_paid": True,
            },
            {
                "player_id": people["thandi"].pk,
                "name": "Thandi",
                "is_captain": True,
                "in_team": True,
                "paid": "0.00",
                "has_paid": False,
            },
        ],
        "paid_for_team": "50.00",
        "team_credit": "20.00",
    }


@pytest.mark.django_db
def test_reversed_payments_and_leavers(owing, people, signed_in, cashier):
    wrong = cash(owing, cashier, "70", people["thandi"])
    ledger.reverse(wrong, reason="Typed for the wrong Player", recorded_by=cashier)
    cash(owing, cashier, "70", people["sipho"])
    membership = owing.current_memberships().get(player=people["sipho"])
    membership.left_at = timezone.now()
    membership.save(update_fields=["left_at"])

    body = signed_in(people["thandi"]).get(summary_url(owing)).json()

    rows = {row["name"]: row for row in body["players"]}
    assert rows["Thandi"]["paid"] == "0.00"
    assert rows["Thandi"]["has_paid"] is False
    assert rows["Sipho"] == {
        "player_id": people["sipho"].pk,
        "name": "Sipho",
        "is_captain": False,
        "in_team": False,
        "paid": "70.00",
        "has_paid": True,
    }
    assert body["paid"] == "70.00"


@pytest.mark.django_db
def test_an_admin_of_the_club_sees_it_without_team_credit(owing, people, admin_of, club_a):
    cash(owing, admin_of(club_a).user, "350")

    answer = admin_of(club_a, "other-admin@example.com").get(summary_url(owing))

    assert answer.status_code == 200
    assert answer.json()["is_paid"] is True
    assert answer.json()["team_credit"] is None


@pytest.mark.django_db
def test_no_one_else_sees_who_has_paid(owing, people, signed_in, admin_of, club_b):
    assert signed_in(people["sipho"]).get(summary_url(owing)).status_code == 404
    assert signed_in(people["lerato"]).get(summary_url(owing)).status_code == 404
    assert admin_of(club_b).get(summary_url(owing)).status_code == 404


@pytest.mark.django_db
def test_signed_out_gets_401(api, owing):
    assert api.get(summary_url(owing)).status_code == 401


# Suggested amount


@pytest.mark.django_db
def test_the_suggested_amount_is_the_share_less_what_was_paid(owing, people, cashier):
    assert services.suggested_amount(owing, people["sipho"]) == D("175.00")

    cash(owing, cashier, "100", people["sipho"])

    assert services.suggested_amount(owing, people["sipho"]) == D("75.00")


@pytest.mark.django_db
def test_the_share_is_rounded_up_to_the_cent_and_capped(make_team, people, make_user, cashier):
    third = make_user("third@example.com", position="outfield", name="Third")
    team = make_team("Old Boys", people["lerato"], third, people["sipho"])
    ledger.charge_league_fee(team)

    assert services.suggested_amount(team, third) == D("116.67")

    cash(team, cashier, "300")

    assert services.suggested_amount(team, third) == D("50.00")


@pytest.mark.django_db
def test_once_the_share_is_paid_the_share_is_suggested_again(owing, people, cashier):
    cash(owing, cashier, "175", people["sipho"])

    assert services.suggested_amount(owing, people["sipho"]) == D("175.00")


@pytest.mark.django_db
def test_nothing_is_suggested_when_nothing_is_owed(lions, people):
    assert services.suggested_amount(lions, people["sipho"]) is None
