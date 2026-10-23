"""The Fixture lists and details: the club's Admin, and Players in the Fixture's Teams."""

import datetime as dt

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import ClubRole
from clubs.models import Field, Season
from fixtures import lifecycle
from fixtures.models import Fixture
from teams.models import TeamMembership

from .conftest import next_weekday

S = Fixture.Status


def club_url(club, fixture=None):
    if fixture is None:
        return reverse("api-v1:club-fixtures-list", kwargs={"club_id": club.pk})
    return reverse("api-v1:club-fixtures-detail", kwargs={"club_id": club.pk, "pk": fixture.pk})


def signed_in(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def fixture(make_fixture, lions_and_boys):
    return make_fixture(*lions_and_boys)


# The club's Admin


@pytest.mark.django_db
def test_admin_lists_the_clubs_fixtures_by_kick_off(admin_of, club_a, fixture, make_fixture):
    lions, boys = fixture.home_team, fixture.away_team
    early = make_fixture(boys, lions, time="18:30")

    answer = admin_of(club_a).get(club_url(club_a))

    assert answer.status_code == 200
    body = answer.json()
    assert [f["id"] for f in body] == [early.pk, fixture.pk]
    first = body[1]
    assert first["home_team"] == {"id": lions.pk, "name": "Red Lions"}
    assert first["pitch"] == {"id": fixture.pitch_id, "name": "Pitch 3"}
    assert first["weekday"] == 1
    assert first["status"] == "scheduled"
    assert first["referee_name"] == "Rita Referee"
    assert first["friendly_eligible"] is False
    assert "transitions" not in first


@pytest.mark.django_db
def test_admin_filters_by_night_season_and_status(
    admin_of, club_a, fixture, make_fixture, make_team, make_user, friday_division, season
):
    friday_pitch = Field.objects.create(club=club_a, name="Pitch 1")
    a = make_team("Fri A", make_user("fa@example.com"), division=friday_division)
    b = make_team("Fri B", make_user("fb@example.com"), division=friday_division)
    friday = make_fixture(a, b, division=friday_division, pitch=friday_pitch, date=next_weekday(4))
    lifecycle.transition(friday, S.CANCELLED, cause="admin")
    admin = admin_of(club_a)

    def ids(**query):
        return [f["id"] for f in admin.get(club_url(club_a), query).json()]

    assert ids(night=friday_division.night_id) == [friday.pk]
    assert ids(division=fixture.division_id) == [fixture.pk]
    assert ids(status="cancelled") == [friday.pk]
    assert sorted(ids(season=season.pk)) == sorted([fixture.pk, friday.pk])


@pytest.mark.django_db
def test_without_a_season_only_seasons_that_havent_ended(admin_of, club_a, fixture, season):
    season.starts_on = dt.date(2020, 1, 1)
    season.ends_on = dt.date(2020, 6, 1)
    season.save()
    admin = admin_of(club_a)

    assert admin.get(club_url(club_a)).json() == []
    assert len(admin.get(club_url(club_a), {"season": season.pk}).json()) == 1


@pytest.mark.django_db
def test_admin_sees_a_fixture_with_its_history(admin_of, club_a, fixture):
    admin = admin_of(club_a)
    lifecycle.transition(fixture, S.CONFIRMING, cause="checkpoint")
    lifecycle.transition(fixture, S.CANCELLED, cause="admin", actor=admin.user, note="Rain")

    answer = admin.get(club_url(club_a, fixture))

    assert answer.status_code == 200
    history = [
        (t["from_status"], t["to_status"], t["cause"], t["actor_name"], t["note"])
        for t in answer.json()["transitions"]
    ]
    assert history == [
        ("", "scheduled", "admin", None, ""),
        ("scheduled", "confirming", "checkpoint", None, ""),
        ("confirming", "cancelled", "admin", "Admin of Club A", "Rain"),
    ]


@pytest.mark.django_db
def test_admin_marks_a_fixture_friendly_eligible(admin_of, club_a, fixture):
    admin = admin_of(club_a)

    answer = admin.patch(club_url(club_a, fixture), {"friendly_eligible": True}, format="json")

    assert answer.status_code == 200
    assert answer.json()["friendly_eligible"] is True
    assert answer.json()["friendly_eligible_changed_by_name"] == "Admin of Club A"
    fixture.refresh_from_db()
    assert fixture.friendly_eligible is True
    assert fixture.friendly_eligible_changed_by == admin.user


@pytest.mark.django_db
def test_only_friendly_eligible_can_be_changed(admin_of, club_a, fixture):
    admin = admin_of(club_a)

    answer = admin.patch(
        club_url(club_a, fixture),
        {"friendly_eligible": False, "status": "played", "kick_off": "2030-01-01T10:00:00Z"},
        format="json",
    )

    assert answer.status_code == 200
    fixture.refresh_from_db()
    assert fixture.status == S.SCHEDULED
    assert fixture.kick_off.year != 2030
    assert admin.patch(club_url(club_a, fixture), {}, format="json").status_code == 400
    assert admin.put(club_url(club_a, fixture), {}, format="json").status_code == 405
    assert admin.delete(club_url(club_a, fixture)).status_code == 405


@pytest.mark.django_db
def test_friendly_eligible_cant_change_once_cancelled(admin_of, club_a, fixture):
    lifecycle.transition(fixture, S.CANCELLED, cause="admin")

    answer = admin_of(club_a).patch(
        club_url(club_a, fixture), {"friendly_eligible": True}, format="json"
    )

    assert answer.status_code == 409


@pytest.mark.django_db
def test_another_clubs_admin_sees_and_changes_nothing(admin_of, club_a, club_b, fixture):
    other = admin_of(club_b)

    assert other.get(club_url(club_a)).status_code == 403
    assert other.get(club_url(club_a, fixture)).status_code == 403
    assert other.patch(club_url(club_a, fixture), {"friendly_eligible": True}).status_code == 403
    # Under their own club's URL, club A's Fixture doesn't exist.
    assert other.get(club_url(club_b)).json() == []
    assert other.get(club_url(club_b, fixture)).status_code == 404
    assert other.patch(club_url(club_b, fixture), {"friendly_eligible": True}).status_code == 404
    fixture.refresh_from_db()
    assert fixture.friendly_eligible is False


@pytest.mark.django_db
def test_referees_players_and_strangers_cant_use_the_admin_views(
    api, club_a, fixture, make_user, give_role
):
    referee = make_user("r@example.com")
    give_role(referee, club_a, ClubRole.Role.REFEREE)
    for client in [signed_in(referee), signed_in(fixture.home_team.captain)]:
        assert client.get(club_url(club_a)).status_code == 403
        assert client.get(club_url(club_a, fixture)).status_code == 403
    assert api.get(club_url(club_a)).status_code == 401


@pytest.mark.django_db
def test_fixtures_keep_their_division_pitch_and_season(admin_of, club_a, fixture, season):
    admin = admin_of(club_a)
    division_url = reverse(
        "api-v1:club-divisions-detail", kwargs={"club_id": club_a.pk, "pk": fixture.division_id}
    )
    field_url = reverse(
        "api-v1:club-fields-detail", kwargs={"club_id": club_a.pk, "pk": fixture.pitch_id}
    )

    assert admin.delete(division_url).status_code == 409
    assert admin.delete(field_url).status_code == 409
    assert Season.objects.filter(pk=season.pk).exists()


# Players and Captains


@pytest.mark.django_db
def test_a_player_sees_their_teams_upcoming_fixtures(make_user, fixture, make_fixture, make_team):
    lions, boys = fixture.home_team, fixture.away_team
    sipho = make_user("sipho@example.com", position="outfield")
    TeamMembership.objects.create(team=boys, player=sipho, joined_at=fixture.created_at)
    others = make_team("Others", make_user("o@example.com"))
    make_fixture(others, lions, time="21:00")  # Not Sipho's.
    past = make_fixture(lions, boys, date=next_weekday(1, after_days=-14))

    answer = signed_in(sipho).get(reverse("api-v1:my-fixtures"))

    assert answer.status_code == 200
    body = answer.json()
    assert [f["id"] for f in body] == [fixture.pk]
    assert body[0]["my_team_id"] == boys.pk
    assert body[0]["club"]["name"] == "Club A"
    assert "referee_name" not in body[0]
    past_answer = signed_in(sipho).get(reverse("api-v1:my-fixtures"), {"when": "past"})
    assert [f["id"] for f in past_answer.json()] == [past.pk]


@pytest.mark.django_db
def test_a_captain_sees_their_teams_fixtures(fixture):
    captain = signed_in(fixture.home_team.captain)

    body = captain.get(reverse("api-v1:my-fixtures")).json()

    assert [(f["id"], f["my_team_id"]) for f in body] == [(fixture.pk, fixture.home_team_id)]


@pytest.mark.django_db
def test_a_player_who_left_no_longer_sees_the_teams_fixtures(make_user, fixture):
    sipho = make_user("sipho@example.com", position="outfield")
    TeamMembership.objects.create(
        team=fixture.home_team,
        player=sipho,
        joined_at=fixture.created_at,
        left_at=fixture.created_at,
    )
    client = signed_in(sipho)

    assert client.get(reverse("api-v1:my-fixtures")).json() == []
    assert client.get(reverse("api-v1:fixtures-detail", args=[fixture.pk])).status_code == 404


@pytest.mark.django_db
def test_a_fixture_is_open_to_players_of_its_teams_only(make_user, fixture, club_a, admin_of):
    detail = reverse("api-v1:fixtures-detail", args=[fixture.pk])
    captain = signed_in(fixture.away_team.captain)
    stranger = signed_in(make_user("x@example.com", position="outfield"))
    booking_user = signed_in(make_user("b@example.com", booking=True))

    answer = captain.get(detail)
    assert answer.status_code == 200
    assert answer.json()["my_team_id"] == fixture.away_team_id
    assert stranger.get(detail).status_code == 404
    assert booking_user.get(detail).status_code == 403
    assert booking_user.get(reverse("api-v1:my-fixtures")).status_code == 403
    # An Admin who doesn't play uses the club's views.
    assert admin_of(club_a).get(detail).status_code == 403
