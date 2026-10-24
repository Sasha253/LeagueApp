"""The finance tracker API: Season totals, income comparison and the Team ledger, all
computed from the ledger, for the Club's Admins only."""

import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import ClubRole
from clubs.models import Season
from finance import services
from ledger import services as ledger
from ledger.models import LedgerEntry


def url(name, club, **kwargs):
    return reverse(f"api-v1:club-finance-{name}", kwargs={"club_id": club.pk, **kwargs})


def signed_in(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def line(card="0.00", cash="0.00", credit_spent="0.00", returned="0.00"):
    received = Decimal(card) + Decimal(cash)
    return {
        "card": card,
        "cash": cash,
        "received": f"{received:.2f}",
        "credit_spent": credit_spent,
        "returned_as_credit": returned,
    }


# Season totals (FR-25, FR-49)


@pytest.mark.django_db
def test_season_totals_per_night_and_division(books, admin_of, club_a, season):
    answer = admin_of(club_a).get(url("summary", club_a), {"season": season.pk})

    assert answer.status_code == 200
    body = answer.json()
    assert body["season"] == {"id": season.pk, "name": "Spring"}
    tuesday, friday = body["nights"]
    assert tuesday["night"]["weekday"] == 1
    [division_2] = tuesday["divisions"]
    assert division_2["division"]["name"] == "Division 2"
    assert division_2["teams"] == 2
    assert division_2["expected"] == "700.00"
    # Lions paid 350 (100 card + 250 cash); Old Boys 120 card + 30 credit of 350.
    assert division_2["outstanding"] == "200.00"
    assert division_2["league"] == line(
        card="220.00", cash="250.00", credit_spent="30.00", returned="100.00"
    )
    assert division_2["team_credit_held"] == "40.00"
    assert division_2["friendly"] == line(cash="80.00")
    assert tuesday["expected"] == "700.00"
    assert tuesday["friendly"] == line(cash="80.00")

    [division_1] = friday["divisions"]
    assert division_1["teams"] == 1  # Late Starters are still waiting.
    assert (division_1["expected"], division_1["outstanding"]) == ("350.00", "350.00")
    assert division_1["league"] == line()

    totals = body["totals"]
    assert totals["teams"] == 3
    assert (totals["expected"], totals["outstanding"]) == ("1050.00", "550.00")
    assert totals["league"]["received"] == "470.00"
    assert body["booking"] == line(card="600.00", returned="300.00")
    assert body["credit_held"] == {
        "team": "40.00",
        "player": "100.00",
        "booking_user": "300.00",
    }
    assert body["received"] == "1150.00"  # 470 league + 80 friendly + 600 booking.


@pytest.mark.django_db
def test_a_refund_comes_off_its_method(books, admin_of, club_a, season, cashier):
    entry = LedgerEntry.objects.create(
        club=club_a, kind="refund", method="cash", category="league", amount=Decimal("50"),
        subject="team", team=books["lions"], reason="Overpaid", recorded_by=cashier,
    )  # fmt: skip
    assert entry.pk

    body = admin_of(club_a).get(url("summary", club_a), {"season": season.pk}).json()

    assert body["nights"][0]["divisions"][0]["league"]["cash"] == "200.00"
    assert body["nights"][0]["divisions"][0]["outstanding"] == "250.00"  # Lions owe 50 again.


@pytest.mark.django_db
def test_an_overpaid_team_owes_nothing_and_takes_nothing_off_others(
    books, admin_of, club_a, season, cashier
):
    ledger.record_payment(
        team=books["owls"], amount=Decimal("400"), method="cash", recorded_by=cashier
    )
    body = admin_of(club_a).get(url("summary", club_a), {"season": season.pk}).json()

    assert body["nights"][1]["outstanding"] == "0.00"
    assert body["totals"]["outstanding"] == "200.00"


@pytest.mark.django_db
def test_a_reversed_charge_is_not_expected(books, admin_of, club_a, season, cashier):
    charge = LedgerEntry.objects.get(team=books["owls"], kind="charge")
    ledger.reverse(charge, reason="Charged in error", recorded_by=cashier)

    body = admin_of(club_a).get(url("summary", club_a), {"season": season.pk}).json()

    assert body["nights"][1]["expected"] == "0.00"
    assert body["nights"][1]["outstanding"] == "0.00"


@pytest.mark.django_db
def test_filters_by_night_and_division(books, admin_of, club_a, season, friday_division):
    client = admin_of(club_a)

    by_night = client.get(
        url("summary", club_a), {"season": season.pk, "night": friday_division.night_id}
    ).json()
    assert [n["night"]["weekday"] for n in by_night["nights"]] == [4]
    assert by_night["totals"]["expected"] == "350.00"
    assert by_night["night"] == {"id": friday_division.night_id, "weekday": 4}
    # Club-wide figures are left out of a filtered view.
    assert by_night["booking"] is None
    assert by_night["credit_held"] == {"team": "0.00", "player": None, "booking_user": None}

    by_division = client.get(
        url("summary", club_a), {"season": season.pk, "division": friday_division.pk}
    ).json()
    assert by_division["division"] == {"id": friday_division.pk, "name": "Division 1"}
    assert by_division["totals"]["teams"] == 1


@pytest.mark.django_db
def test_another_season_has_its_own_totals(books, admin_of, club_a, season):
    autumn = Season.objects.create(
        club=club_a, name="Autumn", starts_on=dt.date(2020, 3, 1), ends_on=dt.date(2020, 5, 31)
    )
    body = admin_of(club_a).get(url("summary", club_a), {"season": autumn.pk}).json()

    assert body["totals"]["expected"] == "0.00"
    assert body["totals"]["teams"] == 0
    assert body["booking"]["received"] == "0.00"  # The booking is in Spring's dates.
    assert body["received"] == "0.00"


@pytest.mark.django_db
def test_summary_checks_its_query(books, admin_of, club_a, club_b, season, friday_division):
    client = admin_of(club_a)
    summary = url("summary", club_a)
    other_season = Season.objects.get(club=club_b)

    assert client.get(summary).status_code == 400
    assert client.get(summary, {"season": "spring"}).status_code == 400
    assert client.get(summary, {"season": "\u00b2"}).status_code == 400
    assert client.get(summary, {"season": season.pk, "night": "\u00b2"}).status_code == 400
    assert client.get(summary, {"season": other_season.pk}).status_code == 404
    tuesday_id = books["lions"].division.night_id
    mismatch = {"season": season.pk, "night": tuesday_id, "division": friday_division.pk}
    assert client.get(summary, mismatch).status_code == 400


@pytest.mark.django_db
def test_summary_never_counts_another_clubs_money(books, club_b, admin_of):
    season_b = Season.objects.get(club=club_b)
    body = admin_of(club_b).get(url("summary", club_b), {"season": season_b.pk}).json()

    assert body["totals"]["expected"] == "900.00"
    assert body["totals"]["league"]["card"] == "900.00"
    assert body["credit_held"]["player"] == "0.00"
    assert body["booking"]["received"] == "0.00"


# Comparison (FR-27)


@pytest.mark.django_db
def test_income_compared_across_seasons_and_nights(books, admin_of, club_a, season):
    autumn = Season.objects.create(
        club=club_a, name="Autumn", starts_on=dt.date(2020, 3, 1), ends_on=dt.date(2020, 5, 31)
    )
    answer = admin_of(club_a).get(url("comparison", club_a))

    assert answer.status_code == 200
    first, second = answer.json()
    assert first["season"]["name"] == "Autumn"  # Oldest first.
    assert first["received"] == "0.00"
    assert second["season"] == {"id": season.pk, "name": "Spring"}
    assert second["received"] == "1150.00"
    assert second["league"]["received"] == "470.00"
    assert second["friendly"]["received"] == "80.00"
    assert second["booking"]["received"] == "600.00"
    tuesday, friday = second["nights"]
    assert (tuesday["league"]["received"], tuesday["friendly"]["received"]) == (
        "470.00",
        "80.00",
    )
    assert friday["league"]["received"] == "0.00"

    only_spring = admin_of(club_a, "a2@example.com").get(
        url("comparison", club_a), {"seasons": f"{season.pk}"}
    )
    assert [s["season"]["name"] for s in only_spring.json()] == ["Spring"]
    assert autumn.pk


@pytest.mark.django_db
def test_comparison_takes_only_this_clubs_seasons(books, admin_of, club_a, club_b, season):
    client = admin_of(club_a)
    other = Season.objects.get(club=club_b)

    assert client.get(url("comparison", club_a), {"seasons": f"{other.pk}"}).status_code == 400
    assert client.get(url("comparison", club_a), {"seasons": "1,x"}).status_code == 400
    assert client.get(url("comparison", club_a), {"seasons": "\u00b2"}).status_code == 400
    both = client.get(url("comparison", club_a), {"seasons": f"{season.pk},{other.pk}"})
    assert both.status_code == 400


# Team ledger (FR-26)


@pytest.mark.django_db
def test_team_ledger_lines_newest_first(books, admin_of, club_a, people):
    boys = books["boys"]
    answer = admin_of(club_a).get(url("team-ledger", club_a, team_id=boys.pk))

    assert answer.status_code == 200
    body = answer.json()
    assert body["team"] == {"id": boys.pk, "name": "Old Boys"}
    assert body["night"]["weekday"] == 1
    assert (body["due"], body["paid"], body["outstanding"]) == ("350.00", "150.00", "200.00")
    assert body["paid_by_method"] == {"card": "120.00", "cash": "0.00", "credit": "30.00"}
    assert body["team_credit_held"] == "0.00"
    assert body["is_paid"] is False
    kinds = [(e["kind"], e["method"], e["amount"]) for e in body["entries"]]
    assert kinds == [
        ("payment", "credit", "30.00"),
        ("payment", "card", "120.00"),
        ("reversal", "cash", "50.00"),
        ("payment", "cash", "50.00"),
        ("charge", "", "350.00"),
    ]
    reversal = body["entries"][2]
    assert reversal["reason"] == "Wrong Team"
    assert reversal["recorded_by_name"] == "Cash Admin"
    assert body["entries"][0]["recorded_by_name"] == "Pieter"


@pytest.mark.django_db
def test_team_ledger_names_the_player_who_paid(books, admin_of, club_a, people):
    body = admin_of(club_a).get(url("team-ledger", club_a, team_id=books["lions"].pk)).json()

    sipho = [e for e in body["entries"] if e["method"] == "card"]
    assert sipho[0]["player"] == {"id": people["sipho"].pk, "name": "Sipho"}
    assert body["team_credit_held"] == "40.00"
    assert body["is_paid"] is True


@pytest.mark.django_db
def test_team_ledger_of_another_clubs_team_is_not_found(books, admin_of, club_a, club_b):
    from teams.models import Team

    other_team = Team.objects.get(club=club_b)
    client = admin_of(club_a)
    assert client.get(url("team-ledger", club_a, team_id=other_team.pk)).status_code == 404
    # Its own Club's URL, but not that Club's Admin.
    assert client.get(url("team-ledger", club_b, team_id=other_team.pk)).status_code == 403


# Who may see it


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["summary", "comparison", "team-ledger"])
def test_admins_only(name, books, api, club_a, club_b, people, admin_of, give_role, season):
    kwargs = {"team_id": books["lions"].pk} if name == "team-ledger" else {}
    target = url(name, club_a, **kwargs)
    query = {"season": season.pk}
    referee = people["lerato"]
    give_role(referee, club_a, ClubRole.Role.REFEREE)

    assert api.get(target, query).status_code == 401
    assert signed_in(people["thandi"]).get(target, query).status_code == 403  # The Captain.
    assert signed_in(referee).get(target, query).status_code == 403
    assert admin_of(club_b).get(target, query).status_code == 403
    assert admin_of(club_a).get(target, query).status_code == 200


@pytest.mark.django_db
def test_nothing_is_written(books, admin_of, club_a, season):
    before = LedgerEntry.objects.count()
    client = admin_of(club_a)
    client.get(url("summary", club_a), {"season": season.pk})
    client.get(url("comparison", club_a))
    assert client.post(url("summary", club_a), {}).status_code == 405
    assert LedgerEntry.objects.count() == before


# Services


@pytest.mark.django_db
def test_season_window_is_south_african_days(season):
    start, end = services.season_window(season)

    assert start.utcoffset() == dt.timedelta(hours=2)
    assert end - start == dt.timedelta(days=(season.ends_on - season.starts_on).days + 1)
