"""The Admin adds one Fixture, checked as a row of the league import (fixtures/adding.py)."""

import datetime as dt

import pytest
from django.urls import reverse
from django.utils import timezone

from clubs.models import Field
from fixtures.imports import local_kick_off
from fixtures.models import Fixture, FixtureTransition

from .conftest import next_weekday


def club_fixtures(club):
    return reverse("api-v1:club-fixtures-list", kwargs={"club_id": club.pk})


@pytest.fixture
def body(season, division, pitch, lions_and_boys, next_tuesday):
    lions, boys = lions_and_boys

    def make(**changes):
        data = {
            "season": season.pk,
            "division": division.pk,
            "pitch": pitch.pk,
            "home_team": lions.pk,
            "away_team": boys.pk,
            "kick_off": local_kick_off(next_tuesday, dt.time(19, 40)).isoformat(),
        }
        return {**data, **changes}

    return make


@pytest.mark.django_db
def test_the_admin_adds_a_scheduled_fixture(admin_of, club_a, body, lions_and_boys, next_tuesday):
    admin = admin_of(club_a)

    answer = admin.post(club_fixtures(club_a), body(friendly_eligible=True), format="json")

    assert answer.status_code == 201
    fixture = Fixture.objects.get(pk=answer.json()["id"])
    assert fixture.status == Fixture.Status.SCHEDULED
    assert (fixture.home_team, fixture.away_team) == lions_and_boys
    assert fixture.kick_off == local_kick_off(next_tuesday, dt.time(19, 40))
    assert fixture.friendly_eligible
    assert fixture.friendly_eligible_changed_by == admin.user
    created = fixture.transitions.get()
    assert (created.cause, created.actor) == (FixtureTransition.Cause.ADMIN, admin.user)


@pytest.mark.django_db
def test_the_kick_off_is_on_the_divisions_night(admin_of, club_a, body):
    wednesday = local_kick_off(next_weekday(2), dt.time(19, 40))

    answer = admin_of(club_a).post(club_fixtures(club_a), body(kick_off=wednesday.isoformat()))

    assert answer.status_code == 400
    assert answer.json()["kick_off"] == ["Division 2 plays on Tuesdays."]


@pytest.mark.django_db
def test_import_rules_apply(admin_of, club_a, body, season, next_tuesday):
    season.ends_on = next_tuesday - dt.timedelta(days=1)
    season.save()

    answer = admin_of(club_a).post(club_fixtures(club_a), body())

    assert answer.status_code == 400
    assert "outside the Spring Season" in answer.json()["non_field_errors"][0]


@pytest.mark.django_db
def test_a_passed_kick_off_is_refused(admin_of, club_a, body, season):
    past = timezone.localdate() - dt.timedelta(days=1)
    past -= dt.timedelta(days=(past.weekday() - 1) % 7)  # The Tuesday before.

    answer = admin_of(club_a).post(
        club_fixtures(club_a), body(kick_off=local_kick_off(past, dt.time(19, 40)).isoformat())
    )

    assert answer.status_code == 400
    assert "passed" in answer.json()["non_field_errors"][0]


@pytest.mark.django_db
def test_a_busy_pitch_or_team_is_refused(
    admin_of, club_a, body, make_team, make_user, make_fixture, lions_and_boys
):
    lions, _ = lions_and_boys
    others = make_team("Others", make_user("o@example.com", position="outfield"))
    make_fixture(lions, others)
    admin = admin_of(club_a)

    answer = admin.post(club_fixtures(club_a), body())

    assert answer.status_code == 400
    errors = answer.json()["non_field_errors"]
    assert any("Pitch 3 already has" in e for e in errors)


@pytest.mark.django_db
def test_the_same_fixture_twice_is_refused(admin_of, club_a, body, club_b):
    other_pitch = Field.objects.create(club=club_a, name="Pitch 4")
    admin = admin_of(club_a)
    assert admin.post(club_fixtures(club_a), body()).status_code == 201

    again = admin.post(club_fixtures(club_a), body(pitch=other_pitch.pk))

    assert again.status_code == 400
    assert Fixture.objects.count() == 1


@pytest.mark.django_db
def test_teams_must_be_two_active_teams_of_the_division(
    admin_of, club_a, body, lions_and_boys, make_team, make_user, friday_division
):
    lions, _ = lions_and_boys
    friday = make_team(
        "Friday Team", make_user("f@example.com", position="outfield"), division=friday_division
    )
    waiting = make_team(
        "Waiting", make_user("w@example.com", position="outfield"), status="requested"
    )
    admin = admin_of(club_a)

    same = admin.post(club_fixtures(club_a), body(away_team=lions.pk)).json()
    elsewhere = admin.post(club_fixtures(club_a), body(away_team=friday.pk)).json()
    pending = admin.post(club_fixtures(club_a), body(away_team=waiting.pk)).json()

    assert same["away_team"] == ["Home and Away are the same Team."]
    assert "this Division" in elsewhere["away_team"][0]
    assert pending["away_team"] == ["This Team isn't active."]
    assert not Fixture.objects.exists()


@pytest.mark.django_db
def test_another_clubs_records_are_refused(admin_of, club_a, club_b, body):
    answer = admin_of(club_b).post(club_fixtures(club_b), body())

    assert answer.status_code == 400
    assert {"season", "division", "pitch", "home_team", "away_team"} <= set(answer.json())


@pytest.mark.django_db
def test_only_the_clubs_admins_add_fixtures(make_user, api, club_a, body):
    api.force_authenticate(make_user("p@example.com", position="outfield"))

    assert api.post(club_fixtures(club_a), body()).status_code == 403
