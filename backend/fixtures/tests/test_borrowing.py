"""Player and Goalkeeper Requests (FR-35 to FR-37, the visibility rule), on a frozen clock."""

import datetime as dt

import pytest
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from clubs.models import Division, Night
from core.exceptions import Conflict
from fixtures import borrowing, checkpoints, confirmations, lifecycle, reschedules
from fixtures.models import (
    BorrowedPlayer,
    Fixture,
    FixtureTransition,
    PlayerRequest,
    TeamReadiness,
)
from fixtures.tests import test_reschedules as base
from notifications import services as notifications
from notifications.models import Kind, Notification

player = base.player
match = base.match
clock = base.clock
admin = base.admin

pytestmark = pytest.mark.django_db

S = Fixture.Status
RS = PlayerRequest.Status


def as_user(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def outsiders(player):
    """Players opted into Tuesday in neither Team, and one who isn't opted in."""
    return {
        "nomvula": player("nomvula"),
        "lerato": player("lerato"),
        "kagiso": player("kagiso", "goalkeeper"),
        "bongani": player("bongani", "both"),
        "zola": player("zola", nights=[]),
    }


def invites(kind=Kind.PLAYER_REQUEST):
    return Notification.objects.filter(kind=kind)


def names(notifications_or_users):
    return sorted(getattr(n, "recipient", n).name for n in notifications_or_users)


def accept(person, request_=None):
    found = Notification.objects.get(
        recipient=person,
        kind__in=[Kind.PLAYER_REQUEST, Kind.GOALKEEPER_REQUEST],
        **({"player_request_invite__request": request_} if request_ else {}),
    )
    return notifications.answer(found, "accept")


# Raising a request (FR-35, FR-36)


def test_a_player_request_goes_only_to_outfield_players_outside_both_teams(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)

    raised = borrowing.raise_request(fixture, people["thandi"], "player", 1)

    sent = invites()
    # Outfield or both, opted into Tuesday, in neither Team; never Ayanda (Old Boys).
    assert names(sent) == ["Bongani", "Lerato", "Nomvula"]
    assert raised.notified == 3
    assert raised.status == RS.OPEN
    assert raised.team == fixture.home_team
    assert raised.kick_off == fixture.kick_off
    assert not invites(Kind.GOALKEEPER_REQUEST).exists()
    first = sent.first()
    assert first.title == "Red Lions need a player: Red Lions vs Old Boys"
    assert "Can you play for Red Lions?" in first.body
    assert first.answer_by == fixture.kick_off
    assert first.answers == ["accept", "decline"]


def test_a_goalkeeper_request_goes_only_to_goalkeepers(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)

    borrowing.raise_request(fixture, people["pieter"], "goalkeeper", 1)

    assert names(invites(Kind.GOALKEEPER_REQUEST)) == ["Bongani", "Kagiso"]
    assert not invites(Kind.PLAYER_REQUEST).exists()
    assert "Old Boys need a goalkeeper" in invites(Kind.GOALKEEPER_REQUEST).first().title


def test_players_of_another_club_or_night_are_never_asked(match, outsiders, clock, player, club_b):
    fixture, people = match
    other_night = Night.objects.create(club=club_b, weekday=Night.Weekday.TUESDAY)
    player("busi", nights=[other_night])
    clock(fixture, hours=48)

    borrowing.raise_request(fixture, people["thandi"], "player", 1)

    assert "Busi" not in names(invites())
    assert "Zola" not in names(invites())


def test_only_a_captain_of_the_match_can_raise_one(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)

    with pytest.raises(PermissionDenied):
        borrowing.raise_request(fixture, people["sipho"], "player", 1)
    with pytest.raises(PermissionDenied):
        borrowing.raise_request(fixture, outsiders["nomvula"], "player", 1)
    with pytest.raises(PermissionDenied):
        borrowing.preview(fixture, people["sipho"], "player")


def test_places_are_one_up_to_the_division_minimum(match, outsiders, clock):
    fixture, people = match
    Division.objects.filter(pk=fixture.division_id).update(min_players=2)
    clock(fixture, hours=48)

    with pytest.raises(ValidationError):
        borrowing.raise_request(fixture, people["thandi"], "player", 3)
    with pytest.raises(ValidationError):
        borrowing.raise_request(fixture, people["thandi"], "player", 0)
    assert borrowing.raise_request(fixture, people["thandi"], "player", 2).places == 2


def test_one_open_request_per_team_and_kind(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)
    borrowing.raise_request(fixture, people["thandi"], "player", 1)

    with pytest.raises(Conflict, match="already has an open request for players"):
        borrowing.raise_request(fixture, people["thandi"], "player", 1)
    borrowing.raise_request(fixture, people["thandi"], "goalkeeper", 1)  # another kind
    borrowing.raise_request(fixture, people["pieter"], "player", 1)  # the other Team


def test_no_request_when_no_one_can_be_asked(match, clock):
    fixture, people = match
    clock(fixture, hours=48)

    with pytest.raises(Conflict, match="No one can be asked"):
        borrowing.raise_request(fixture, people["thandi"], "goalkeeper", 1)
    assert not PlayerRequest.objects.exists()


def test_no_request_after_kick_off_or_for_a_match_that_is_not_going_ahead(match, outsiders, clock):
    fixture, people = match
    clock(fixture, minutes=-1)
    with pytest.raises(Conflict, match="can't be requested"):
        borrowing.raise_request(fixture, people["thandi"], "player", 1)

    clock(fixture, hours=48)
    lifecycle.transition(fixture, S.CANCELLED, cause=FixtureTransition.Cause.ADMIN)
    fixture.refresh_from_db()
    with pytest.raises(Conflict):
        borrowing.raise_request(fixture, people["thandi"], "player", 1)


def test_the_preview_counts_who_would_be_asked(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)

    planned = borrowing.preview(fixture, people["thandi"], "goalkeeper")

    assert (planned.recipients, planned.night, planned.max_places) == (2, "Tuesday", 5)


# Accepting (FR-37)


def test_the_first_to_accept_joins_and_the_request_closes(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)
    raised = borrowing.raise_request(fixture, people["thandi"], "player", 1)

    accept(outsiders["lerato"])

    raised.refresh_from_db()
    assert raised.status == RS.FILLED
    joined = BorrowedPlayer.objects.get()
    assert (joined.player, joined.team, joined.kick_off) == (
        outsiders["lerato"],
        fixture.home_team,
        fixture.kick_off,
    )
    # Every invite now stops taking answers.
    assert not invites().filter(closed_at__isnull=True).exists()
    with pytest.raises(Conflict):
        accept(outsiders["nomvula"])
    assert BorrowedPlayer.objects.count() == 1


def test_the_captain_is_told_when_it_fills(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)
    borrowing.raise_request(fixture, people["thandi"], "player", 2)

    accept(outsiders["lerato"])
    assert not Notification.objects.filter(kind=Kind.UPDATE).exists()  # one place left
    accept(outsiders["nomvula"])

    told = Notification.objects.get(kind=Kind.UPDATE)
    assert told.recipient == people["thandi"]
    assert told.title == "Request filled: Red Lions vs Old Boys"
    assert told.body.startswith("Lerato, Nomvula will play for Red Lions as players.")
    assert PlayerRequest.objects.get().status == RS.FILLED


def test_a_captain_opted_out_of_the_night_is_not_told(match, outsiders, clock):
    fixture, people = match
    people["thandi"].player_profile.nights.clear()
    clock(fixture, hours=48)
    borrowing.raise_request(fixture, people["thandi"], "player", 1)

    accept(outsiders["lerato"])

    assert not Notification.objects.filter(kind=Kind.UPDATE).exists()


def test_decline_is_only_recorded_and_can_change_to_accept(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)
    borrowing.raise_request(fixture, people["thandi"], "player", 1)
    mine = invites().get(recipient=outsiders["lerato"])

    notifications.answer(mine, "decline")
    assert not BorrowedPlayer.objects.exists()
    notifications.answer(mine, "accept")

    assert BorrowedPlayer.objects.get().player == outsiders["lerato"]


def test_a_player_who_joined_cannot_take_it_back(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)
    borrowing.raise_request(fixture, people["thandi"], "player", 2)
    accept(outsiders["lerato"])

    with pytest.raises(Conflict):
        notifications.answer(invites().get(recipient=outsiders["lerato"]), "decline")


def test_a_player_joins_only_one_team_of_a_match(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)
    lions = borrowing.raise_request(fixture, people["thandi"], "player", 1)
    boys = borrowing.raise_request(fixture, people["pieter"], "player", 1)
    accept(outsiders["bongani"], lions)

    with pytest.raises(Conflict, match="already joined"):
        accept(outsiders["bongani"], boys)
    # The refused answer was not saved.
    assert (
        invites().get(player_request_invite__request=boys, recipient=outsiders["bongani"]).answer
        == ""
    )


def test_someone_already_borrowed_is_not_asked_again(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)
    borrowing.raise_request(fixture, people["thandi"], "player", 1)
    accept(outsiders["bongani"])

    borrowing.raise_request(fixture, people["thandi"], "goalkeeper", 1)

    assert names(invites(Kind.GOALKEEPER_REQUEST)) == ["Kagiso"]


def test_a_player_who_since_joined_a_team_of_the_match_cannot_accept(match, outsiders, clock):
    from teams.models import TeamMembership

    fixture, people = match
    clock(fixture, hours=48)
    borrowing.raise_request(fixture, people["pieter"], "player", 1)
    TeamMembership.objects.create(
        team=fixture.home_team, player=outsiders["lerato"], joined_at=fixture.kick_off
    )

    with pytest.raises(Conflict, match="in one of this match's Teams"):
        accept(outsiders["lerato"])


def test_a_player_who_changed_position_cannot_accept(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)
    borrowing.raise_request(fixture, people["thandi"], "player", 1)
    outsiders["lerato"].player_profile.position = "goalkeeper"
    outsiders["lerato"].player_profile.save()

    with pytest.raises(Conflict, match="isn't open to you"):
        accept(outsiders["lerato"])


def test_a_reschedule_closes_the_request(match, outsiders, clock, admin):
    fixture, people = match
    clock(fixture, hours=72)
    raised = borrowing.raise_request(fixture, people["thandi"], "player", 1)
    reschedules.reschedule(fixture, base.week_later(fixture), admin=admin)
    fixture.refresh_from_db()

    with pytest.raises(Conflict):
        accept(outsiders["lerato"])
    assert borrowing.status_of(raised, fixture, fixture.kick_off - dt.timedelta(days=3)) == (
        RS.CLOSED
    )
    # A new request for the new kick-off can go out.
    borrowing.raise_request(fixture, people["thandi"], "player", 1)
    raised.refresh_from_db()
    assert raised.status == RS.CLOSED


def test_a_request_for_a_team_no_longer_in_the_match_cannot_be_accepted(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)
    borrowing.raise_request(fixture, people["thandi"], "player", 1)
    lifecycle.transition(fixture, S.ONE_TEAM_OUT, cause=FixtureTransition.Cause.ADMIN)

    with pytest.raises(Conflict, match="no longer applies"):
        accept(outsiders["lerato"])


def test_requests_can_be_answered_until_kick_off(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)
    borrowing.raise_request(fixture, people["thandi"], "player", 1)
    clock(fixture, minutes=-1)

    with pytest.raises(Conflict):
        accept(outsiders["lerato"])


# Withdrawing


def test_the_captain_withdraws_an_open_request_and_who_joined_stays(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)
    raised = borrowing.raise_request(fixture, people["thandi"], "player", 2)
    accept(outsiders["lerato"])

    with pytest.raises(PermissionDenied):
        borrowing.withdraw(raised, people["pieter"])
    borrowing.withdraw(raised, people["thandi"])

    raised.refresh_from_db()
    assert raised.status == RS.WITHDRAWN
    assert BorrowedPlayer.objects.count() == 1
    with pytest.raises(Conflict):
        accept(outsiders["nomvula"])
    with pytest.raises(Conflict, match="already been withdrawn"):
        borrowing.withdraw(raised, people["thandi"])


# Counting (FR-5, FR-38)


def test_borrowed_players_count_as_confirmed_at_t6h(match, outsiders, clock):
    fixture, people = match
    Division.objects.filter(pk=fixture.division_id).update(min_players=2)
    clock(fixture, hours=36)
    checkpoints.run_due()
    fixture.refresh_from_db()
    for person in ("thandi", "pieter", "ayanda"):
        confirmations.answer(fixture, people[person], "confirm", via="fixture")
    confirmations.answer(fixture, people["sipho"], "decline", via="fixture")
    borrowing.raise_request(fixture, people["thandi"], "player", 1)
    accept(outsiders["lerato"])

    clock(fixture, hours=6)
    checkpoints.run_due()

    fixture.refresh_from_db()
    assert fixture.status == S.READY
    lions = TeamReadiness.objects.get(fixture=fixture, team=fixture.home_team)
    assert lions.confirmed == 2


def test_the_squad_shows_borrowed_players(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)
    borrowing.raise_request(fixture, people["thandi"], "player", 1)
    accept(outsiders["lerato"])

    response = as_user(people["sipho"]).get(reverse("api-v1:fixtures-squad", args=[fixture.pk]))

    assert response.status_code == 200
    assert response.data["confirmed"] == 1
    assert [p["name"] for p in response.data["borrowed"]] == ["Lerato"]
    assert response.data["borrowed"][0]["kind"] == "player"
    other = as_user(people["pieter"]).get(reverse("api-v1:fixtures-squad", args=[fixture.pk]))
    assert other.data["borrowed"] == []


# The API


def test_the_captain_raises_and_the_team_sees_it(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)
    url = reverse("api-v1:fixtures-player-requests", args=[fixture.pk])

    response = as_user(people["thandi"]).post(url, {"kind": "goalkeeper", "places": 1})

    assert response.status_code == 201
    assert response.data["is_captain"] and response.data["can_request"]
    assert response.data["max_places"] == 5
    (sent,) = response.data["requests"]
    assert (sent["kind"], sent["status"], sent["notified"], sent["filled"]) == (
        "goalkeeper",
        "open",
        2,
        0,
    )
    seen = as_user(people["sipho"]).get(url)
    assert seen.status_code == 200
    assert not seen.data["is_captain"] and not seen.data["can_request"]
    assert len(seen.data["requests"]) == 1
    assert as_user(people["pieter"]).get(url).data["requests"] == []  # the other Team's


def test_only_the_captain_can_post_or_preview(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)
    url = reverse("api-v1:fixtures-player-requests", args=[fixture.pk])

    assert as_user(people["sipho"]).post(url, {"kind": "player"}).status_code == 403
    preview = reverse("api-v1:fixtures-player-requests-preview", args=[fixture.pk])
    assert as_user(people["sipho"]).get(preview, {"kind": "player"}).status_code == 403
    answer = as_user(people["thandi"]).get(preview, {"kind": "player"})
    assert answer.status_code == 200
    assert answer.data == {"kind": "player", "recipients": 3, "night": "Tuesday", "max_places": 5}
    assert as_user(people["thandi"]).get(preview, {"kind": "keeper"}).status_code == 400
    # Not in the match at all: 404.
    assert as_user(outsiders["lerato"]).get(url).status_code == 404


def test_answering_from_the_inbox_joins_and_a_late_accept_is_refused(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)
    borrowing.raise_request(fixture, people["thandi"], "player", 1)

    def answer_as(person):
        mine = invites().get(recipient=person)
        url = reverse("api-v1:notification-answer", kwargs={"notification_id": mine.pk})
        return as_user(person).post(url, {"answer": "accept"})

    assert answer_as(outsiders["lerato"]).status_code == 200
    late = answer_as(outsiders["nomvula"])
    assert late.status_code == 409
    assert invites().get(recipient=outsiders["nomvula"]).answer == ""


def test_my_games_to_join(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)
    borrowing.raise_request(fixture, people["thandi"], "player", 2)
    url = reverse("api-v1:my-player-requests")

    (game,) = as_user(outsiders["lerato"]).get(url).data
    assert (game["kind"], game["team"]["name"], game["places_left"]) == ("player", "Red Lions", 2)
    assert game["can_answer"] and not game["joined"] and game["status"] == "open"
    assert game["fixture"]["id"] == fixture.pk
    assert as_user(outsiders["kagiso"]).get(url).data == []  # a goalkeeper: never sent

    accept(outsiders["lerato"])
    (game,) = as_user(outsiders["lerato"]).get(url).data
    assert game["joined"] and not game["can_answer"] and game["my_answer"] == "accept"
    assert as_user(outsiders["nomvula"]).get(url).data[0]["places_left"] == 1

    accept(outsiders["nomvula"])
    # Filled: Bongani was asked but can no longer join, so it leaves his list.
    assert as_user(outsiders["bongani"]).get(url).data == []


def test_withdraw_through_the_api(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)
    raised = borrowing.raise_request(fixture, people["thandi"], "player", 1)
    url = reverse("api-v1:player-requests-withdraw", args=[raised.pk])

    assert as_user(people["sipho"]).post(url).status_code == 404
    response = as_user(people["thandi"]).post(url)
    assert response.status_code == 200
    assert response.data["status"] == "withdrawn"
    assert as_user(people["thandi"]).post(url).status_code == 409
