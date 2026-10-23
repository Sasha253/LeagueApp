"""Seasons, Nights, Divisions and Fields, through the Admin API."""

from decimal import Decimal

import pytest
from django.urls import reverse

from accounts.models import ClubRole
from clubs.models import ClubSettings, Division, Field, Night


def list_url(club, name):
    return reverse(f"api-v1:club-{name}-list", kwargs={"club_id": club.pk})


def detail_url(club, name, pk):
    return reverse(f"api-v1:club-{name}-detail", kwargs={"club_id": club.pk, "pk": pk})


@pytest.fixture
def division(tuesday):
    return Division.objects.create(night=tuesday, name="Division 2", min_players=5)


# Seasons


@pytest.mark.django_db
def test_admin_adds_edits_and_deletes_a_season(admin_of, club_a):
    client = admin_of(club_a)
    body = {"name": "Spring 2026", "starts_on": "2026-08-04", "ends_on": "2026-11-24"}

    created = client.post(list_url(club_a, "seasons"), body, format="json")
    assert created.status_code == 201
    pk = created.json()["id"]

    edited = client.patch(detail_url(club_a, "seasons", pk), {"name": "Spring"}, format="json")
    assert edited.json()["name"] == "Spring"
    assert client.get(list_url(club_a, "seasons")).json()[0]["name"] == "Spring"

    assert client.delete(detail_url(club_a, "seasons", pk)).status_code == 204
    assert club_a.seasons.count() == 0


@pytest.mark.django_db
def test_a_season_ends_after_it_starts_and_has_its_own_name(admin_of, club_a):
    client = admin_of(club_a)
    url = list_url(club_a, "seasons")
    client.post(url, {"name": "Spring", "starts_on": "2026-08-04", "ends_on": "2026-11-24"})

    backwards = client.post(
        url, {"name": "Autumn", "starts_on": "2026-08-04", "ends_on": "2026-08-01"}
    )
    same_name = client.post(
        url, {"name": "Spring", "starts_on": "2027-08-04", "ends_on": "2027-11-24"}
    )

    assert backwards.status_code == 400 and "ends_on" in backwards.json()
    assert same_name.status_code == 400 and "name" in same_name.json()


# Nights


@pytest.mark.django_db
def test_admin_adds_a_night_once_per_weekday(admin_of, club_a, club_b):
    Night.objects.create(club=club_b, weekday=Night.Weekday.FRIDAY)
    client = admin_of(club_a)

    first = client.post(list_url(club_a, "nights"), {"weekday": 4}, format="json")
    again = client.post(list_url(club_a, "nights"), {"weekday": 4}, format="json")

    assert first.status_code == 201
    assert first.json() == {"id": first.json()["id"], "weekday": 4, "divisions": []}
    assert again.status_code == 400


@pytest.mark.django_db
def test_lists_nights_with_their_divisions(admin_of, club_a, division):
    body = admin_of(club_a).get(list_url(club_a, "nights")).json()

    assert body[0]["divisions"][0]["name"] == "Division 2"


@pytest.mark.django_db
def test_a_night_with_divisions_cant_be_deleted(admin_of, club_a, tuesday, division):
    response = admin_of(club_a).delete(detail_url(club_a, "nights", tuesday.pk))

    assert response.status_code == 409
    assert Night.objects.filter(pk=tuesday.pk).exists()


@pytest.mark.django_db
def test_an_empty_night_can_be_deleted(admin_of, club_a, tuesday):
    assert admin_of(club_a).delete(detail_url(club_a, "nights", tuesday.pk)).status_code == 204


# Divisions


@pytest.mark.django_db
def test_a_new_division_starts_from_the_clubs_minimum(admin_of, club_a, tuesday):
    ClubSettings.objects.filter(club=club_a).update(division_min_players=6)
    url = list_url(club_a, "divisions")

    response = admin_of(club_a).post(url, {"night": tuesday.pk, "name": "Division 1"})

    assert response.status_code == 201
    assert response.json()["min_players"] == 6


@pytest.mark.django_db
def test_a_division_fee_overrides_the_clubs(admin_of, club_a, division):
    ClubSettings.objects.filter(club=club_a).update(league_fee=Decimal("350"))
    client = admin_of(club_a)
    url = detail_url(club_a, "divisions", division.pk)

    assert client.get(url).json()["effective_league_fee"] == "350.00"
    response = client.patch(url, {"league_fee": "400", "min_players": 7}, format="json")
    assert response.json()["effective_league_fee"] == "400.00"
    assert response.json()["min_players"] == 7

    cleared = client.patch(url, {"league_fee": None}, format="json")
    assert cleared.json()["effective_league_fee"] == "350.00"


@pytest.mark.django_db
def test_effective_fee_is_null_while_no_fee_is_set(admin_of, club_a, division):
    body = admin_of(club_a).get(detail_url(club_a, "divisions", division.pk)).json()

    assert body["effective_league_fee"] is None


@pytest.mark.django_db
@pytest.mark.parametrize("change", [{"min_players": 0}, {"league_fee": "-5"}])
def test_refuses_a_bad_division(admin_of, club_a, division, change):
    url = detail_url(club_a, "divisions", division.pk)

    assert admin_of(club_a).patch(url, change, format="json").status_code == 400


@pytest.mark.django_db
def test_division_names_are_unique_per_night(admin_of, club_a, tuesday, division):
    url = list_url(club_a, "divisions")

    response = admin_of(club_a).post(url, {"night": tuesday.pk, "name": "Division 2"})

    assert response.status_code == 400 and "name" in response.json()


@pytest.mark.django_db
def test_a_division_cant_go_under_another_clubs_night(admin_of, club_a, club_b):
    friday_b = Night.objects.create(club=club_b, weekday=Night.Weekday.FRIDAY)

    response = admin_of(club_a).post(
        list_url(club_a, "divisions"), {"night": friday_b.pk, "name": "Sneaky"}
    )

    assert response.status_code == 400 and "night" in response.json()


# Fields


@pytest.mark.django_db
def test_admin_adds_a_field_with_its_referee(admin_of, make_user, give_role, club_a):
    referee = make_user("ref@example.com", name="Thabo Ref")
    give_role(referee, club_a, ClubRole.Role.REFEREE)

    response = admin_of(club_a).post(
        list_url(club_a, "fields"), {"name": "Pitch 3", "referee": referee.pk}
    )

    assert response.status_code == 201
    assert response.json()["referee_name"] == "Thabo Ref"


@pytest.mark.django_db
def test_a_fields_referee_must_be_a_referee_of_this_club(
    admin_of, make_user, give_role, club_a, club_b
):
    elsewhere = make_user("ref-b@example.com")
    give_role(elsewhere, club_b, ClubRole.Role.REFEREE)
    player = make_user("player@example.com", position="outfield")
    url = list_url(club_a, "fields")
    client = admin_of(club_a)

    for user in (elsewhere, player):
        response = client.post(url, {"name": "Pitch 1", "referee": user.pk})
        assert response.status_code == 400 and "referee" in response.json()


@pytest.mark.django_db
def test_field_names_are_unique_per_club(admin_of, club_a, club_b):
    Field.objects.create(club=club_b, name="Pitch 1")
    client = admin_of(club_a)

    assert client.post(list_url(club_a, "fields"), {"name": "Pitch 1"}).status_code == 201
    assert client.post(list_url(club_a, "fields"), {"name": "Pitch 1"}).status_code == 400
