"""Answering Confirmations (FR-3) and who has answered (FR-38), on a frozen clock."""

import datetime as dt

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from fixtures import checkpoints, confirmations, lifecycle
from fixtures.models import ConfirmationAnswer, Fixture
from notifications import services
from notifications.models import Kind, Notification
from notifications.tests import conftest as notification_fixtures
from teams.models import TeamMembership

# The Notifications tests' pytest fixtures: Players opted into Tuesday, and a match.
player = notification_fixtures.player
match = notification_fixtures.match

S = Fixture.Status

pytestmark = pytest.mark.django_db


@pytest.fixture
def clock(time_machine):
    """Stops the clock at `fixture.kick_off - hours` (and `minutes`)."""

    def at(fixture, hours=0, minutes=0):
        moment = fixture.kick_off - dt.timedelta(hours=hours, minutes=minutes)
        time_machine.move_to(moment, tick=False)
        return moment

    return at


@pytest.fixture
def confirming(match, clock):
    """The match at T-36h, after its Confirmations went out."""
    fixture, people = match
    clock(fixture, hours=36)
    assert checkpoints.send_confirmations(fixture.pk)
    fixture.refresh_from_db()
    return fixture, people


def signed_in(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def answer_url(fixture):
    return reverse("api-v1:fixtures-answer", kwargs={"pk": fixture.pk})


def squad_url(fixture):
    return reverse("api-v1:fixtures-squad", kwargs={"pk": fixture.pk})


def confirmation_of(fixture, user):
    return Notification.objects.get(fixture=fixture, recipient=user, kind=Kind.CONFIRMATION)


def answer_of(fixture, user):
    return ConfirmationAnswer.objects.filter(fixture=fixture, player=user).first()


# Answering from the match screen (FR-3)


def test_player_confirms_from_the_match_screen(confirming):
    fixture, people = confirming

    response = signed_in(people["sipho"]).post(answer_url(fixture), {"answer": "confirm"})

    assert response.status_code == 200
    saved = answer_of(fixture, people["sipho"])
    assert saved.answer == "confirm"
    assert saved.via == "fixture"
    assert saved.team == fixture.home_team
    assert saved.kick_off == fixture.kick_off
    body = response.json()
    assert body["my_answer"] == "confirm"
    assert body["confirmed"] == 1
    # The inbox shows the same answer, so the resend skips this Player (FR-2).
    notification = confirmation_of(fixture, people["sipho"])
    assert notification.answer == "confirm"
    assert notification.read_at is not None


def test_player_can_change_the_answer_until_the_cutoff(confirming, clock):
    fixture, people = confirming
    client = signed_in(people["sipho"])
    client.post(answer_url(fixture), {"answer": "confirm"})

    clock(fixture, hours=6, minutes=1)
    response = client.post(answer_url(fixture), {"answer": "decline"})

    assert response.status_code == 200
    assert ConfirmationAnswer.objects.filter(fixture=fixture).count() == 1
    assert answer_of(fixture, people["sipho"]).answer == "decline"
    assert confirmation_of(fixture, people["sipho"]).answer == "decline"


def test_no_answer_or_change_at_or_after_the_cutoff(confirming, clock):
    fixture, people = confirming
    client = signed_in(people["sipho"])
    client.post(answer_url(fixture), {"answer": "confirm"})

    clock(fixture, hours=6)
    response = client.post(answer_url(fixture), {"answer": "decline"})

    assert response.status_code == 409
    assert "closed" in response.json()["detail"]
    assert answer_of(fixture, people["sipho"]).answer == "confirm"


def test_the_cutoff_comes_from_the_clubs_settings(confirming, clock):
    fixture, people = confirming
    club_settings = fixture.club.settings
    club_settings.readiness_hours_before = 8
    club_settings.save()

    clock(fixture, hours=7)
    response = signed_in(people["sipho"]).post(answer_url(fixture), {"answer": "confirm"})

    assert response.status_code == 409
    assert response.json()["detail"].startswith("Replies for this match closed")


def test_no_answer_before_the_confirmations_go_out(match, clock):
    fixture, people = match
    clock(fixture, hours=40)

    response = signed_in(people["sipho"]).post(answer_url(fixture), {"answer": "confirm"})

    assert response.status_code == 409
    assert "36 hours" in response.json()["detail"]
    assert not ConfirmationAnswer.objects.exists()


@pytest.mark.parametrize("status", [S.READY, S.ONE_TEAM_OUT, S.CANCELLED])
def test_no_answer_once_the_match_left_confirming(confirming, status):
    fixture, people = confirming
    lifecycle.transition(fixture, status, cause="checkpoint")

    response = signed_in(people["sipho"]).post(answer_url(fixture), {"answer": "confirm"})

    assert response.status_code == 409


def test_answer_must_be_confirm_or_decline(confirming):
    fixture, people = confirming

    response = signed_in(people["sipho"]).post(answer_url(fixture), {"answer": "accept"})

    assert response.status_code == 400


def test_a_player_without_the_nights_notifications_still_answers(confirming, player):
    fixture, _ = confirming
    quiet = player("quiet", nights=[])
    TeamMembership.objects.create(team=fixture.home_team, player=quiet, joined_at=timezone.now())
    assert not Notification.objects.filter(recipient=quiet).exists()

    response = signed_in(quiet).post(answer_url(fixture), {"answer": "confirm"})

    assert response.status_code == 200
    assert answer_of(fixture, quiet).answer == "confirm"


# Who may answer and see


def test_someone_outside_both_teams_gets_404(confirming, player):
    fixture, _ = confirming
    outsider = player("zaid")

    client = signed_in(outsider)
    assert client.post(answer_url(fixture), {"answer": "confirm"}).status_code == 404
    assert client.get(squad_url(fixture)).status_code == 404


def test_a_player_who_left_the_team_can_no_longer_answer(confirming):
    fixture, people = confirming
    TeamMembership.objects.filter(player=people["sipho"]).update(left_at=timezone.now())

    response = signed_in(people["sipho"]).post(answer_url(fixture), {"answer": "confirm"})

    assert response.status_code == 404


def test_an_admin_who_is_not_a_player_cannot_answer(confirming, admin_of, club_a):
    fixture, _ = confirming

    response = admin_of(club_a).post(answer_url(fixture), {"answer": "confirm"})

    assert response.status_code == 403


def test_anonymous_gets_401(confirming):
    fixture, _ = confirming

    assert APIClient().get(squad_url(fixture)).status_code == 401


# Answering from the Confirmation Notification


def test_answering_the_notification_records_the_answer(confirming):
    fixture, people = confirming

    services.answer(confirmation_of(fixture, people["pieter"]), "decline")

    saved = answer_of(fixture, people["pieter"])
    assert saved.answer == "decline"
    assert saved.via == "notification"
    assert saved.team == fixture.away_team


def test_notification_answer_changes_follow_the_match(confirming):
    fixture, people = confirming
    signed_in(people["pieter"]).post(answer_url(fixture), {"answer": "confirm"})

    services.answer(confirmation_of(fixture, people["pieter"]), "decline")

    assert ConfirmationAnswer.objects.filter(fixture=fixture).count() == 1
    assert answer_of(fixture, people["pieter"]).answer == "decline"


def test_notification_answer_is_refused_when_the_match_stopped_taking_replies(confirming):
    fixture, people = confirming
    lifecycle.transition(fixture, S.CANCELLED, cause="admin")
    notification = confirmation_of(fixture, people["pieter"])

    response = signed_in(people["pieter"]).post(
        reverse("api-v1:notification-answer", kwargs={"notification_id": notification.pk}),
        {"answer": "confirm"},
    )

    assert response.status_code == 409
    notification.refresh_from_db()
    assert notification.answer == ""  # Rolled back with the refusal.
    assert not ConfirmationAnswer.objects.exists()


def test_notification_answer_is_refused_for_a_player_who_left(confirming):
    fixture, people = confirming
    TeamMembership.objects.filter(player=people["pieter"]).update(left_at=timezone.now())
    notification = confirmation_of(fixture, people["pieter"])

    with pytest.raises(Exception, match="not in either Team"):
        services.answer(notification, "confirm")
    notification.refresh_from_db()
    assert notification.answer == ""


def test_the_resend_skips_players_who_answered_on_the_match_screen(confirming, clock):
    fixture, people = confirming
    signed_in(people["sipho"]).post(answer_url(fixture), {"answer": "decline"})

    clock(fixture, hours=24)
    assert checkpoints.resend_confirmations(fixture.pk)

    resent = set(
        Notification.objects.filter(fixture=fixture, resent_at__isnull=False).values_list(
            "recipient__name", flat=True
        )
    )
    assert resent == {"Thandi", "Pieter", "Ayanda"}


# The squad (FR-38)


def test_team_members_see_their_teams_replies_against_the_minimum(confirming):
    fixture, people = confirming
    signed_in(people["thandi"]).post(answer_url(fixture), {"answer": "confirm"})
    signed_in(people["sipho"]).post(answer_url(fixture), {"answer": "decline"})
    signed_in(people["pieter"]).post(answer_url(fixture), {"answer": "confirm"})

    body = signed_in(people["sipho"]).get(squad_url(fixture)).json()

    assert body["team"] == {"id": fixture.home_team_id, "name": "Red Lions"}
    assert body["min_players"] == 5
    assert (body["confirmed"], body["declined"], body["waiting"]) == (1, 1, 0)
    assert body["below_minimum"] is True
    assert body["short_by"] == 4
    assert body["replies_open"] is True
    assert body["my_answer"] == "decline"
    answer_by = dt.datetime.fromisoformat(body["answer_by"])
    assert answer_by == fixture.kick_off - dt.timedelta(hours=6)
    players = body["players"]
    # The Captain first; only this Team's Players (Pieter's answer isn't shown).
    assert [p["name"] for p in players] == ["Thandi", "Sipho"]
    assert players[0]["is_captain"] is True
    assert players[0]["answer"] == "confirm"
    assert players[1]["is_me"] is True
    assert players[1]["answer"] == "decline"


def test_the_minimum_is_the_divisions_own(confirming):
    fixture, people = confirming
    division = fixture.division
    division.min_players = 1
    division.save()
    signed_in(people["thandi"]).post(answer_url(fixture), {"answer": "confirm"})

    body = signed_in(people["thandi"]).get(squad_url(fixture)).json()

    assert body["min_players"] == 1
    assert body["below_minimum"] is False
    assert body["short_by"] == 0


def test_squad_before_the_confirmations_lists_everyone_as_waiting(match, clock):
    fixture, people = match
    clock(fixture, hours=48)

    body = signed_in(people["ayanda"]).get(squad_url(fixture)).json()

    assert body["team"]["name"] == "Old Boys"
    assert (body["confirmed"], body["waiting"]) == (0, 2)
    assert body["replies_open"] is False
    assert body["my_answer"] == ""


def test_players_who_left_drop_out_of_the_squad_and_the_count(confirming):
    fixture, people = confirming
    signed_in(people["sipho"]).post(answer_url(fixture), {"answer": "confirm"})
    TeamMembership.objects.filter(player=people["sipho"]).update(left_at=timezone.now())

    body = signed_in(people["thandi"]).get(squad_url(fixture)).json()

    assert [p["name"] for p in body["players"]] == ["Thandi"]
    assert body["confirmed"] == 0
    assert confirmations.confirmed_count(fixture, fixture.home_team) == 0


def test_answers_for_an_old_kick_off_do_not_count(confirming):
    fixture, people = confirming
    signed_in(people["thandi"]).post(answer_url(fixture), {"answer": "confirm"})
    assert confirmations.confirmed_count(fixture, fixture.home_team) == 1

    Fixture.objects.filter(pk=fixture.pk).update(kick_off=fixture.kick_off + dt.timedelta(days=7))
    fixture.refresh_from_db()

    assert confirmations.confirmed_count(fixture, fixture.home_team) == 0
    body = signed_in(people["thandi"]).get(squad_url(fixture)).json()
    assert body["players"][0]["answer"] == ""
