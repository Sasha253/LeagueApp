"""Admin reschedules (FR-7 to FR-9) and Captain requests (FR-18), on a frozen clock."""

import datetime as dt

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from accounts.models import ClubRole
from clubs.models import Field
from core.exceptions import Conflict
from fixtures import checkpoints, confirmations, lifecycle, reschedules
from fixtures.imports import local_kick_off
from fixtures.models import (
    CaptainRequest,
    Fixture,
    FixtureCheckpoint,
    FixtureFallback,
    FixtureReschedule,
    FixtureTransition,
    ReplacementOffer,
)
from notifications.models import Kind, Notification
from notifications.tests import conftest as notification_fixtures

player = notification_fixtures.player
match = notification_fixtures.match

pytestmark = pytest.mark.django_db

S = Fixture.Status
RS = CaptainRequest.Status


@pytest.fixture
def clock(time_machine):
    def at(fixture, hours=0, minutes=0):
        moment = fixture.kick_off - dt.timedelta(hours=hours, minutes=minutes)
        time_machine.move_to(moment, tick=False)
        return moment

    return at


@pytest.fixture
def admin(club_a, make_user, give_role):
    user = make_user("admin@example.com", name="Ada Admin")
    give_role(user, club_a, ClubRole.Role.ADMIN)
    return user


@pytest.fixture
def admin_api(admin):
    client = APIClient()
    client.force_authenticate(admin)
    return client


@pytest.fixture
def pitch_5(club_a, make_user, give_role):
    referee = make_user("reg@example.com", name="Reg Referee")
    give_role(referee, club_a, ClubRole.Role.REFEREE)
    return Field.objects.create(club=club_a, name="Pitch 5", referee=referee)


def as_user(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def week_later(fixture, hour=19, minute=40, days=7):
    """The same Night `days` later, at `hour`:`minute` South African time."""
    date = timezone.localtime(fixture.kick_off).date() + dt.timedelta(days=days)
    return local_kick_off(date, dt.time(hour, minute))


def updates(fixture, **filters):
    return Notification.objects.filter(fixture=fixture, kind=Kind.UPDATE, **filters)


def names(notifications):
    return sorted(n.recipient.name for n in notifications)


# Rescheduling (FR-7 to FR-9)


def test_a_reschedule_beyond_36_hours_moves_it_and_tells_only_the_right_people(
    match, admin, clock, player, make_user, give_role, club_b
):
    fixture, _ = match
    player("nomvula", nights=[])  # outside both Teams: never told
    other_admin = make_user("b-admin@example.com", name="Bea Admin")
    give_role(other_admin, club_b, ClubRole.Role.ADMIN)
    clock(fixture, hours=72)
    new = week_later(fixture)

    moved = reschedules.reschedule(fixture, new, admin=admin, note="Floodlights")

    fixture.refresh_from_db()
    assert fixture.kick_off == new
    assert fixture.status == S.SCHEDULED
    assert moved.from_kick_off == new - dt.timedelta(days=7)
    assert not moved.confirmations_sent
    told = updates(fixture)
    # FR-7: both Teams' Players; FR-8: only the Night's Admin and the pitch's Referee.
    assert names(told) == ["Ada Admin", "Ayanda", "Pieter", "Rita Referee", "Sipho", "Thandi"]
    assert moved.notified == 6
    assert told[0].title == "Rescheduled: Red Lions vs Old Boys"
    assert "(was " in told[0].body
    assert "go out as usual" in told[0].body
    assert not Notification.objects.filter(kind=Kind.CONFIRMATION).exists()


def test_a_player_who_opted_out_of_the_night_is_not_told(match, admin, clock, tuesday):
    fixture, people = match
    people["sipho"].player_profile.nights.clear()
    clock(fixture, hours=72)

    reschedules.reschedule(fixture, week_later(fixture), admin=admin)

    assert "Sipho" not in names(updates(fixture))


def test_within_36_hours_confirmations_go_out_now_and_the_lifecycle_restarts(match, admin, clock):
    fixture, people = match
    clock(fixture, hours=36)
    checkpoints.run_due()
    fixture.refresh_from_db()
    confirmations.answer(fixture, people["thandi"], "confirm", via="fixture")
    old_confirmations = list(Notification.objects.filter(kind=Kind.CONFIRMATION))
    clock(fixture, hours=30)
    later = fixture.kick_off + dt.timedelta(hours=1)

    moved = reschedules.reschedule(fixture, later, admin=admin)

    fixture.refresh_from_db()
    assert fixture.status == S.CONFIRMING
    assert moved.confirmations_sent
    moves = [(t.from_status, t.to_status, t.cause) for t in fixture.transitions.all()][-2:]
    assert moves == [
        (S.CONFIRMING, S.SCHEDULED, FixtureTransition.Cause.ADMIN),
        (S.SCHEDULED, S.CONFIRMING, FixtureTransition.Cause.ADMIN),
    ]
    # The old Confirmations stop taking answers; new ones go to both Teams (FR-9).
    for old in old_confirmations:
        old.refresh_from_db()
        assert old.closed_at is not None
    new = Notification.objects.filter(kind=Kind.CONFIRMATION, closed_at__isnull=True)
    assert names(new) == ["Ayanda", "Pieter", "Sipho", "Thandi"]
    assert new[0].answer_by == later - dt.timedelta(hours=6)
    assert FixtureCheckpoint.objects.filter(
        fixture=fixture, kind="confirmation", kick_off=later
    ).exists()
    # A new kick-off starts with no answers.
    assert confirmations.confirmed_count(fixture, fixture.home_team) == 0
    assert "going out now" in updates(fixture).first().body


def test_a_ready_match_moved_a_week_goes_back_to_scheduled_and_runs_again(match, admin, clock):
    fixture, _ = match
    lifecycle.transition(fixture, S.CONFIRMING, cause=FixtureTransition.Cause.CHECKPOINT)
    lifecycle.transition(fixture, S.READY, cause=FixtureTransition.Cause.CHECKPOINT)
    clock(fixture, hours=3)
    new = week_later(fixture)

    reschedules.reschedule(fixture, new, admin=admin)
    fixture.refresh_from_db()
    assert fixture.status == S.SCHEDULED

    clock(fixture, hours=36)
    ran = checkpoints.run_due()
    fixture.refresh_from_db()
    assert ran["confirmation"] == 1
    assert fixture.status == S.CONFIRMING


def test_a_new_pitch_at_the_same_kick_off_keeps_the_answers(match, admin, clock, pitch_5):
    fixture, people = match
    clock(fixture, hours=36)
    checkpoints.run_due()
    fixture.refresh_from_db()
    confirmations.answer(fixture, people["thandi"], "confirm", via="fixture")
    clock(fixture, hours=3)  # after the T-6h cutoff: a pitch can still change

    moved = reschedules.reschedule(fixture, fixture.kick_off, pitch_5, admin=admin)

    fixture.refresh_from_db()
    assert fixture.pitch == pitch_5
    assert fixture.status == S.CONFIRMING
    assert confirmations.confirmed_count(fixture, fixture.home_team) == 1
    assert not Notification.objects.filter(kind=Kind.CONFIRMATION, closed_at__isnull=False).exists()
    assert not moved.confirmations_sent
    # FR-8: the Referees of the old and the new pitch, and the Night's Admin.
    told = updates(fixture)
    assert {"Rita Referee", "Reg Referee", "Ada Admin"} <= set(names(told))
    assert told[0].title == "New pitch: Red Lions vs Old Boys"
    assert "Your reply stands." in told[0].body


def test_only_the_affected_pitchs_referee_is_told(match, admin, clock, pitch_5):
    fixture, _ = match
    clock(fixture, hours=72)

    reschedules.reschedule(fixture, week_later(fixture), admin=admin)

    assert "Reg Referee" not in names(updates(fixture))


def test_refusals_for_the_new_kick_off(match, admin, clock, season):
    fixture, _ = match
    clock(fixture, hours=72)
    kick_off = fixture.kick_off

    def refused(new, pitch=None):
        with pytest.raises(ValidationError) as error:
            reschedules.reschedule(fixture, new, pitch, admin=admin)
        return str(error.value.detail)

    assert "Pick a new kick-off or pitch" in refused(kick_off)
    now = kick_off - dt.timedelta(hours=72)
    assert "Players reply until 6 hours" in refused(now + dt.timedelta(hours=5))
    assert "isn't a Tuesday" in refused(kick_off + dt.timedelta(days=1))
    outside = week_later(fixture, days=7 * 20)
    assert "outside the Spring Season" in refused(outside)
    fixture.refresh_from_db()
    assert fixture.kick_off == kick_off
    assert not FixtureReschedule.objects.exists()


def test_another_clubs_pitch_is_refused(match, admin, clock, club_b):
    fixture, _ = match
    clock(fixture, hours=72)
    theirs = Field.objects.create(club=club_b, name="Their pitch")

    with pytest.raises(ValidationError):
        reschedules.reschedule(fixture, fixture.kick_off, theirs, admin=admin)


def test_a_taken_pitch_or_a_busy_team_is_refused(
    match, admin, clock, make_team, player, make_fixture
):
    fixture, _ = match
    clock(fixture, hours=72)
    new = week_later(fixture)
    bulls = make_team("Blue Bulls", player("bongi"))
    geckos = make_team("Green Geckos", player("gugu"))
    make_fixture(bulls, geckos, date=(new + dt.timedelta(hours=2)).date())

    with pytest.raises(Conflict, match="Pitch 3 already has a match"):
        reschedules.reschedule(fixture, new, admin=admin)

    other_lions = make_fixture(
        fixture.home_team, bulls, date=(new + dt.timedelta(hours=2)).date(), time="18:00"
    )
    assert other_lions.pk
    with pytest.raises(Conflict, match="Red Lions already has a match"):
        reschedules.reschedule(fixture, new + dt.timedelta(minutes=30), admin=admin)


@pytest.mark.parametrize("status", [S.ONE_TEAM_OUT, S.CANCELLED])
def test_a_match_that_moved_on_cannot_be_rescheduled(match, admin, clock, status):
    fixture, _ = match
    clock(fixture, hours=72)
    Fixture.objects.filter(pk=fixture.pk).update(status=status)
    fixture.refresh_from_db()

    with pytest.raises(Conflict, match="can't be rescheduled"):
        reschedules.reschedule(fixture, week_later(fixture), admin=admin)


def test_a_match_that_kicked_off_cannot_be_rescheduled(match, admin, clock):
    fixture, _ = match
    clock(fixture, hours=-1)

    with pytest.raises(Conflict, match="kicked off"):
        reschedules.reschedule(fixture, week_later(fixture), admin=admin)


# The Admin's endpoints


def url(name, club, fixture):
    return reverse(f"api-v1:club-fixtures-{name}", kwargs={"club_id": club.pk, "pk": fixture.pk})


def test_preview_says_what_will_happen_and_writes_nothing(match, admin_api, clock, club_a):
    fixture, _ = match
    clock(fixture, hours=72)

    response = admin_api.post(
        url("reschedule-preview", club_a, fixture),
        {"kick_off": week_later(fixture).isoformat()},
        format="json",
    )
    assert response.status_code == 200, response.data
    body = response.data
    assert body["status_after"] == "scheduled"
    assert body["confirmations_now"] is False
    assert (body["players"], body["officials"]) == (4, 2)
    assert body["kick_off_changed"] and not body["pitch_changed"]
    assert not Notification.objects.exists()

    # An hour later the same night, 30 hours from now: within the Confirmation window.
    clock(fixture, hours=30)
    response = admin_api.post(
        url("reschedule-preview", club_a, fixture),
        {"kick_off": (fixture.kick_off + dt.timedelta(hours=1)).isoformat()},
        format="json",
    )
    assert response.data["confirmations_now"] is True
    assert response.data["status_after"] == "confirming"


def test_reschedule_endpoint_answers_with_the_fixture(match, admin_api, clock, club_a, pitch_5):
    fixture, _ = match
    clock(fixture, hours=72)
    new = week_later(fixture, hour=20, minute=0)

    response = admin_api.post(
        url("reschedule", club_a, fixture),
        {"kick_off": new.isoformat(), "pitch": pitch_5.pk, "note": "Pitch 3 relaid"},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["pitch"]["name"] == "Pitch 5"
    (moved,) = response.data["reschedules"]
    assert moved["from_pitch"]["name"] == "Pitch 3"
    assert moved["to_pitch"]["name"] == "Pitch 5"
    assert moved["by_name"] == "Ada Admin"
    assert moved["note"] == "Pitch 3 relaid"


def test_reschedule_endpoint_errors(match, admin_api, clock, club_a, club_b):
    fixture, _ = match
    clock(fixture, hours=72)
    theirs = Field.objects.create(club=club_b, name="Their pitch")

    too_soon = admin_api.post(
        url("reschedule", club_a, fixture),
        {"kick_off": (fixture.kick_off - dt.timedelta(hours=70)).isoformat()},
        format="json",
    )
    assert too_soon.status_code == 400
    assert "kick_off" in too_soon.data
    other_pitch = admin_api.post(
        url("reschedule", club_a, fixture),
        {"kick_off": fixture.kick_off.isoformat(), "pitch": theirs.pk},
        format="json",
    )
    assert other_pitch.status_code == 400
    assert other_pitch.data["pitch"] == ["The club has no such pitch."]


def test_only_this_clubs_admins_can_reschedule(match, admin_of, clock, club_a, club_b, player):
    fixture, people = match
    clock(fixture, hours=72)
    body = {"kick_off": week_later(fixture).isoformat()}

    assert (
        as_user(people["thandi"]).post(url("reschedule", club_a, fixture), body).status_code == 403
    )
    other = admin_of(club_b)
    assert other.post(url("reschedule", club_b, fixture), body).status_code == 404
    assert other.post(url("reschedule", club_a, fixture), body).status_code == 403
    assert not FixtureReschedule.objects.exists()


# Captain requests (FR-18)


def requests_url(fixture):
    return reverse("api-v1:fixtures-requests", kwargs={"pk": fixture.pk})


def club_requests(club, name="list", captain_request=None):
    kwargs = {"club_id": club.pk}
    if captain_request is not None:
        kwargs["pk"] = captain_request.pk
    return reverse(f"api-v1:club-captain-requests-{name}", kwargs=kwargs)


def ask(fixture, captain, kind="cancel", reason="Half the team is at a wedding"):
    return reschedules.request(fixture, captain, kind, reason)


def test_a_captain_asks_and_the_nights_admins_are_told(match, admin, clock):
    fixture, people = match
    clock(fixture, hours=72)

    response = as_user(people["thandi"]).post(
        requests_url(fixture), {"kind": "postpone", "reason": "Wedding"}, format="json"
    )

    assert response.status_code == 201, response.data
    assert response.data["is_captain"] is True
    assert response.data["can_request"] is False  # one waits already
    (sent,) = response.data["requests"]
    assert (sent["kind"], sent["status"], sent["team"]["name"]) == (
        "postpone",
        "pending",
        "Red Lions",
    )
    told = updates(fixture).get()
    assert told.recipient == admin
    assert told.title == "Red Lions asks to postpone Red Lions vs Old Boys"
    assert "Wedding" in told.body
    fixture.refresh_from_db()
    assert fixture.status == S.SCHEDULED  # nothing changes until an Admin accepts


def test_team_players_see_the_request_but_only_the_captain_can_send(match, clock, player):
    fixture, people = match
    clock(fixture, hours=72)
    ask(fixture, people["thandi"])

    sipho = as_user(people["sipho"])
    seen = sipho.get(requests_url(fixture))
    assert seen.status_code == 200
    assert seen.data["is_captain"] is False
    assert len(seen.data["requests"]) == 1
    refused = sipho.post(requests_url(fixture), {"kind": "cancel", "reason": "x"}, format="json")
    assert refused.status_code == 403
    # The other Team doesn't see Red Lions' request; an outsider can't open the match.
    assert as_user(people["pieter"]).get(requests_url(fixture)).data["requests"] == []
    outsider = as_user(player("nomvula"))
    assert outsider.get(requests_url(fixture)).status_code == 404


def test_one_pending_request_per_team_and_none_after_kick_off(match, clock):
    fixture, people = match
    clock(fixture, hours=72)
    ask(fixture, people["thandi"])

    with pytest.raises(Conflict, match="already has a request"):
        ask(fixture, people["thandi"], "postpone")
    ask(fixture, people["pieter"])  # the other Team can

    clock(fixture, hours=-1)
    with pytest.raises(Conflict, match="can't be cancelled or postponed now"):
        reschedules.request(fixture, people["pieter"], "postpone", "late")


def test_not_a_captain(match, clock):
    fixture, people = match
    clock(fixture, hours=72)

    with pytest.raises(PermissionDenied):
        ask(fixture, people["sipho"])


def test_the_captain_withdraws(match, clock):
    fixture, people = match
    clock(fixture, hours=72)
    sent = ask(fixture, people["thandi"])
    withdraw = reverse("api-v1:captain-requests-withdraw", kwargs={"pk": sent.pk})

    assert as_user(people["pieter"]).post(withdraw).status_code == 404
    response = as_user(people["thandi"]).post(withdraw)

    assert response.status_code == 200
    assert response.data["status"] == "withdrawn"
    assert as_user(people["thandi"]).post(withdraw).status_code == 409


def test_accepting_a_cancellation_takes_the_team_out_and_looks_for_an_opponent(
    match, admin_api, clock, club_a, without_fallbacks, make_team, player
):
    fixture, people = match
    make_team("Blue Bulls", player("bongi"))
    clock(fixture, hours=72)
    sent = ask(fixture, people["thandi"])

    response = admin_api.post(club_requests(club_a, "accept", sent), {"note": "OK"}, format="json")

    assert response.status_code == 200, response.data
    assert response.data["status"] == "accepted"
    assert response.data["decided_by_name"] == "Ada Admin"
    fixture.refresh_from_db()
    assert fixture.status == S.REPLACEMENT_OFFERED
    offer = ReplacementOffer.objects.get(fixture=fixture)
    assert offer.out_team.name == "Red Lions"
    assert [c.team.name for c in offer.candidates.all()] == ["Blue Bulls"]
    moves = [(t.from_status, t.to_status) for t in fixture.transitions.all()][-2:]
    assert moves == [(S.SCHEDULED, S.ONE_TEAM_OUT), (S.ONE_TEAM_OUT, S.REPLACEMENT_OFFERED)]
    assert (
        updates(fixture, title="Cancellation accepted: Red Lions vs Old Boys").get().recipient
        == people["thandi"]
    )


def test_with_no_other_team_an_accepted_cancellation_falls_back(match, admin, clock):
    fixture, people = match
    clock(fixture, hours=72)
    sent = ask(fixture, people["pieter"])

    reschedules.accept(sent, admin)

    fixture.refresh_from_db()
    assert fixture.status == S.CANCELLED  # not friendly-eligible (FR-17, FR-43)
    assert FixtureFallback.objects.get(fixture=fixture).remaining_team.name == "Red Lions"


def test_accepting_a_postponement_reschedules_to_the_admins_kick_off(
    match, admin_api, clock, club_a
):
    fixture, people = match
    clock(fixture, hours=72)
    sent = ask(fixture, people["thandi"], "postpone")
    other = ask(fixture, people["pieter"])
    accept = club_requests(club_a, "accept", sent)

    missing = admin_api.post(accept, {}, format="json")
    assert missing.status_code == 400
    assert missing.data["kick_off"] == ["A postponement needs a new kick-off."]

    new = week_later(fixture)
    response = admin_api.post(accept, {"kick_off": new.isoformat()}, format="json")

    assert response.status_code == 200, response.data
    assert response.data["status"] == "accepted"
    fixture.refresh_from_db()
    assert fixture.kick_off == new
    assert FixtureReschedule.objects.get(fixture=fixture).request_id == sent.pk
    # Old Boys' request was for the old kick-off: it no longer applies, and Pieter is told.
    other.refresh_from_db()
    assert other.status == RS.CLOSED
    assert updates(fixture, recipient=people["pieter"], title__startswith="Your request").exists()
    assert updates(fixture, recipient=people["thandi"], title__startswith="Postponement").exists()


def test_declining_changes_nothing_and_tells_the_captain(match, admin_api, clock, club_a):
    fixture, people = match
    clock(fixture, hours=72)
    sent = ask(fixture, people["thandi"])

    response = admin_api.post(
        club_requests(club_a, "decline", sent), {"note": "Find a sub"}, format="json"
    )

    assert response.status_code == 200
    assert (response.data["status"], response.data["note"]) == ("declined", "Find a sub")
    fixture.refresh_from_db()
    assert fixture.status == S.SCHEDULED
    told = updates(fixture, recipient=people["thandi"]).get()
    assert "goes ahead as planned" in told.body and "Find a sub" in told.body
    again = admin_api.post(club_requests(club_a, "accept", sent), {}, format="json")
    assert again.status_code == 409


def test_a_request_whose_match_moved_on_cannot_be_accepted(match, admin, clock):
    fixture, people = match
    clock(fixture, hours=72)
    sent = ask(fixture, people["thandi"])
    lifecycle.transition(fixture, S.CANCELLED, cause=FixtureTransition.Cause.ADMIN)

    with pytest.raises(Conflict, match="moved on"):
        reschedules.accept(sent, admin)
    assert reschedules.decline(sent, admin).status == RS.DECLINED


def test_the_admin_lists_only_their_clubs_requests(
    match, admin_api, admin_of, clock, club_a, club_b
):
    fixture, people = match
    clock(fixture, hours=72)
    sent = ask(fixture, people["thandi"])

    listed = admin_api.get(club_requests(club_a), {"status": "pending"})
    assert [r["id"] for r in listed.data] == [sent.pk]
    assert listed.data[0]["fixture"]["home_team"]["name"] == "Red Lions"
    assert admin_api.get(club_requests(club_a), {"status": "declined"}).data == []

    other = admin_of(club_b)
    assert other.get(club_requests(club_b)).data == []
    assert other.post(club_requests(club_b, "accept", sent), {}).status_code == 404
    assert other.post(club_requests(club_a, "decline", sent), {}).status_code == 403
    sent.refresh_from_db()
    assert sent.status == RS.PENDING


def test_the_admins_fixture_detail_lists_requests(match, admin_api, clock, club_a):
    fixture, people = match
    clock(fixture, hours=72)
    ask(fixture, people["thandi"])

    detail = admin_api.get(url("detail", club_a, fixture))

    assert detail.data["captain_requests"][0]["reason"] == "Half the team is at a wedding"
    assert detail.data["reschedules"] == []
