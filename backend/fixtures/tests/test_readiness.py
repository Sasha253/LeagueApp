"""The T-6h readiness check (FR-5, FR-6) and the Admin's Tonight queue, on a frozen clock."""

import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse

from accounts.models import ClubRole
from clubs.models import Division
from core.exceptions import Conflict
from fixtures import checkpoints, lifecycle, readiness
from fixtures.confirmations import answer
from fixtures.models import Fixture, FixtureCheckpoint, FixtureTransition, TeamReadiness
from ledger import services as ledger
from notifications.models import Kind, Notification
from notifications.tests import conftest as notification_fixtures

player = notification_fixtures.player
match = notification_fixtures.match

S = Fixture.Status
Outcome = TeamReadiness.Outcome
Reason = TeamReadiness.Reason

# What happens after both_teams_out or a lapsed offer is chunk 15's (test_fallbacks.py).
pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("without_fallbacks")]


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
def settled(monkeypatch):
    """Every `readiness_settled` signal sent, as (fixture id, status, out Team names, actor)."""
    sent = []

    def receiver(sender, fixture, out, actor, **kwargs):
        sent.append((fixture.pk, fixture.status, [t.name for t in out], actor))

    readiness.readiness_settled.connect(receiver, dispatch_uid="test-settled")
    yield sent
    readiness.readiness_settled.disconnect(dispatch_uid="test-settled")


@pytest.fixture
def confirming(match, clock):
    """The match after its T-36h Confirmations, with a Division minimum of 2."""
    fixture, people = match
    Division.objects.filter(pk=fixture.division_id).update(min_players=2)
    clock(fixture, hours=36)
    checkpoints.run_due()
    fixture.refresh_from_db()
    assert fixture.status == S.CONFIRMING
    return fixture, people


def confirm(fixture, *people):
    for person in people:
        answer(fixture, person, "confirm", via="fixture")


def owes(team, amount="350"):
    ledger.charge(club=team.club, amount=amount, category="league", reason="League fee", team=team)


def at_t6h(fixture, clock):
    clock(fixture, hours=6)
    return checkpoints.run_due()


def rows(fixture):
    return {r.team.name: r for r in TeamReadiness.objects.filter(fixture=fixture)}


def status(fixture):
    fixture.refresh_from_db()
    return fixture.status


def one_team_out(fixture):
    """The move to one team out; chunk 14 then offers the slot at once."""
    return fixture.transitions.get(to_status=S.ONE_TEAM_OUT)


def reminders(fixture):
    return Notification.objects.filter(fixture=fixture, kind=Kind.REMINDER)


# The check (FR-5, FR-6)


def test_both_teams_at_their_minimum_and_paid_are_ready(confirming, clock, settled):
    fixture, people = confirming
    confirm(fixture, *people.values())

    assert at_t6h(fixture, clock)["readiness"] == 1

    assert status(fixture) == S.READY
    found = rows(fixture)
    assert {r.outcome for r in found.values()} == {Outcome.PLAYING}
    assert found["Red Lions"].confirmed == 2
    assert found["Red Lions"].min_players == 2
    assert settled == [(fixture.pk, S.READY, [], None)]
    assert reminders(fixture).exists()
    last = fixture.transitions.last()
    assert (last.to_status, last.cause) == (S.READY, FixtureTransition.Cause.CHECKPOINT)


def test_a_team_below_the_minimum_is_out(confirming, clock, settled):
    fixture, people = confirming
    confirm(fixture, people["thandi"], people["pieter"], people["ayanda"])
    answer(fixture, people["sipho"], "decline", via="fixture")

    at_t6h(fixture, clock)

    assert status(fixture) == S.REPLACEMENT_OFFERED  # chunk 14 offers the slot at once
    found = rows(fixture)
    assert (found["Red Lions"].outcome, found["Red Lions"].reason) == (Outcome.OUT, Reason.SHORT)
    assert found["Red Lions"].confirmed == 1
    assert found["Old Boys"].outcome == Outcome.PLAYING
    assert settled == [(fixture.pk, S.ONE_TEAM_OUT, ["Red Lions"], None)]
    assert "Red Lions below the minimum (1 of 2)" in one_team_out(fixture).note
    assert not reminders(fixture).exists()  # chunk 14 tells them what happens next


def test_both_teams_below_the_minimum_are_both_out(confirming, clock, settled):
    fixture, people = confirming
    confirm(fixture, people["thandi"])

    at_t6h(fixture, clock)

    assert status(fixture) == S.BOTH_TEAMS_OUT
    assert {r.outcome for r in rows(fixture).values()} == {Outcome.OUT}
    assert settled == [(fixture.pk, S.BOTH_TEAMS_OUT, ["Red Lions", "Old Boys"], None)]


def test_the_division_minimum_is_read_at_the_check(confirming, clock):
    fixture, people = confirming
    confirm(fixture, *people.values())
    Division.objects.filter(pk=fixture.division_id).update(min_players=3)

    at_t6h(fixture, clock)

    assert status(fixture) == S.BOTH_TEAMS_OUT
    assert {r.min_players for r in rows(fixture).values()} == {3}


def test_an_unpaid_team_waits_for_the_admin(confirming, clock, settled):
    fixture, people = confirming
    confirm(fixture, *people.values())
    owes(fixture.away_team)

    at_t6h(fixture, clock)

    assert status(fixture) == S.CONFIRMING  # nothing decided automatically
    boys = rows(fixture)["Old Boys"]
    assert (boys.outcome, boys.reason) == (Outcome.PENDING, Reason.UNPAID)
    assert boys.outstanding == Decimal("350.00")
    assert rows(fixture)["Red Lions"].outcome == Outcome.PLAYING
    assert settled == []
    assert reminders(fixture).exists()  # the match may still go ahead


def test_a_team_that_has_paid_in_full_plays(confirming, clock, admin):
    fixture, people = confirming
    confirm(fixture, *people.values())
    owes(fixture.away_team)
    ledger.record_payment(team=fixture.away_team, amount="350", method="cash", recorded_by=admin)

    at_t6h(fixture, clock)

    assert status(fixture) == S.READY


def test_a_short_team_is_out_whether_or_not_it_paid(confirming, clock):
    fixture, people = confirming
    confirm(fixture, people["thandi"], people["sipho"], people["pieter"])
    owes(fixture.away_team)

    at_t6h(fixture, clock)

    boys = rows(fixture)["Old Boys"]
    assert (boys.outcome, boys.reason) == (Outcome.OUT, Reason.SHORT)
    assert one_team_out(fixture)


def test_answers_for_an_old_kick_off_do_not_count(confirming, clock):
    fixture, people = confirming
    confirm(fixture, *people.values())
    moved = fixture.kick_off + dt.timedelta(hours=1)
    Fixture.objects.filter(pk=fixture.pk).update(kick_off=moved)
    fixture.refresh_from_db()

    at_t6h(fixture, clock)

    assert status(fixture) == S.BOTH_TEAMS_OUT


def test_a_match_whose_confirmations_never_went_out_waits_for_the_admin(match, clock, settled):
    fixture, _ = match
    at_t6h(fixture, clock)

    assert status(fixture) == S.SCHEDULED
    assert {(r.outcome, r.reason) for r in rows(fixture).values()} == {
        (Outcome.PENDING, Reason.NO_REPLIES)
    }
    assert settled == []


# Timing and exactly once


def test_nothing_is_checked_before_the_cutoff(confirming, clock):
    fixture, _ = confirming
    clock(fixture, hours=6, minutes=1)
    assert checkpoints.run_due()["readiness"] == 0
    assert not TeamReadiness.objects.exists()


def test_the_check_runs_once(confirming, clock):
    fixture, people = confirming
    confirm(fixture, *people.values())
    owes(fixture.home_team)

    assert at_t6h(fixture, clock)["readiness"] == 1
    assert checkpoints.run_due()["readiness"] == 0
    assert not checkpoints.check_readiness(fixture.pk)
    assert TeamReadiness.objects.count() == 2
    assert FixtureCheckpoint.objects.filter(kind="readiness").count() == 1


def test_a_late_run_still_checks_before_kick_off(confirming, clock):
    fixture, _ = confirming
    clock(fixture, hours=1)
    assert checkpoints.run_due()["readiness"] == 1
    assert status(fixture) == S.BOTH_TEAMS_OUT


def test_no_check_after_kick_off(confirming, clock):
    fixture, _ = confirming
    clock(fixture, hours=0)
    assert checkpoints.run_due()["readiness"] == 0
    assert status(fixture) == S.CONFIRMING


def test_each_club_uses_its_own_cutoff(confirming, clock):
    fixture, people = confirming
    confirm(fixture, *people.values())
    club_settings = fixture.club.settings
    club_settings.readiness_hours_before = 8
    club_settings.save()

    clock(fixture, hours=8)
    assert checkpoints.run_due()["readiness"] == 1
    assert status(fixture) == S.READY


@pytest.mark.parametrize("state", [S.READY, S.ONE_TEAM_OUT, S.CANCELLED])
def test_matches_already_decided_are_not_checked(match, clock, state):
    fixture, _ = match
    Fixture.objects.filter(pk=fixture.pk).update(status=state)
    assert at_t6h(fixture, clock)["readiness"] == 0
    assert not TeamReadiness.objects.exists()


# The Admin's ruling (FR-6)


@pytest.fixture
def boys_unpaid(confirming, clock):
    fixture, people = confirming
    confirm(fixture, *people.values())
    owes(fixture.away_team)
    at_t6h(fixture, clock)
    return fixture, rows(fixture)["Old Boys"]


def test_the_admin_lets_an_unpaid_team_play(boys_unpaid, admin, settled):
    fixture, boys = boys_unpaid

    readiness.decide(boys, admin, "play", " Cash at the gate ")

    boys.refresh_from_db()
    assert boys.outcome == Outcome.PLAYING
    assert (boys.decided_by, boys.note) == (admin, "Cash at the gate")
    assert boys.decided_at is not None
    assert status(fixture) == S.READY
    last = fixture.transitions.last()
    assert (last.cause, last.actor) == (FixtureTransition.Cause.ADMIN, admin)
    assert settled == [(fixture.pk, S.READY, [], admin)]
    assert ledger.team_balance(fixture.away_team).outstanding == Decimal("350.00")  # no money moved


def test_the_admin_rules_an_unpaid_team_out(boys_unpaid, admin, settled):
    fixture, boys = boys_unpaid

    readiness.decide(boys, admin, "out")

    assert status(fixture) == S.REPLACEMENT_OFFERED
    assert settled == [(fixture.pk, S.ONE_TEAM_OUT, ["Old Boys"], admin)]
    assert "Old Boys ruled out" in one_team_out(fixture).note


def test_a_ruling_is_made_once(boys_unpaid, admin):
    _, boys = boys_unpaid
    readiness.decide(boys, admin, "play")
    with pytest.raises(Conflict, match="already been ruled playing"):
        readiness.decide(boys, admin, "out")


def test_a_team_the_check_decided_cannot_be_ruled_on(boys_unpaid, admin):
    fixture, _ = boys_unpaid
    lions = rows(fixture)["Red Lions"]
    with pytest.raises(Conflict):
        readiness.decide(lions, admin, "out")


def test_no_ruling_once_the_match_has_moved_on(boys_unpaid, admin):
    fixture, boys = boys_unpaid
    lifecycle.transition(fixture, S.CANCELLED, cause="admin", actor=admin)
    with pytest.raises(Conflict, match="moved on"):
        readiness.decide(boys, admin, "play")


def test_the_match_settles_only_when_both_teams_are_decided(match, clock, admin, settled):
    fixture, _ = match
    at_t6h(fixture, clock)  # never confirmed: both wait
    found = rows(fixture)

    readiness.decide(found["Red Lions"], admin, "play")
    assert status(fixture) == S.SCHEDULED
    assert settled == []

    readiness.decide(found["Old Boys"], admin, "play")
    assert status(fixture) == S.READY
    assert len(settled) == 1


def test_both_ruled_out(match, clock, admin):
    fixture, _ = match
    at_t6h(fixture, clock)
    for row in rows(fixture).values():
        readiness.decide(row, admin, "out")
    assert status(fixture) == S.BOTH_TEAMS_OUT


def test_a_readiness_row_is_never_deleted(boys_unpaid):
    _, boys = boys_unpaid
    with pytest.raises(ValueError):
        boys.delete()


# The API: Tonight and the ruling


def tonight_url(club):
    return reverse("api-v1:club-tonight", kwargs={"club_id": club.pk})


def decide_url(club, row):
    return reverse("api-v1:club-readiness-decide", kwargs={"club_id": club.pk, "pk": row.pk})


def test_tonight_shows_todays_matches_with_both_teams(confirming, clock, admin_of, club_a):
    fixture, people = confirming
    confirm(fixture, people["thandi"])
    owes(fixture.away_team, "350")
    clock(fixture, hours=7)  # before the check

    response = admin_of(club_a).get(tonight_url(club_a))

    assert response.status_code == 200
    [match] = response.json()
    assert match["fixture"]["id"] == fixture.pk
    assert (match["checked"], match["waiting"], match["at_risk"]) == (False, False, True)
    lions, boys = match["teams"]
    assert lions["team"]["name"] == "Red Lions"
    assert (lions["confirmed"], lions["min_players"], lions["below_minimum"]) == (1, 2, True)
    assert lions["readiness"] is None
    assert (boys["due"], boys["paid"], boys["outstanding"], boys["unpaid"]) == (
        "350.00",
        "0.00",
        "350.00",
        True,
    )


def test_tonight_after_the_check_shows_the_queue(boys_unpaid, admin_of, club_a):
    _, boys = boys_unpaid

    [match] = admin_of(club_a).get(tonight_url(club_a)).json()

    assert (match["checked"], match["waiting"], match["at_risk"]) == (True, True, True)
    readiness_of_boys = match["teams"][1]["readiness"]
    assert readiness_of_boys["id"] == boys.pk
    assert (readiness_of_boys["outcome"], readiness_of_boys["reason"]) == ("pending", "unpaid")
    assert readiness_of_boys["outstanding"] == "350.00"


def test_tonight_leaves_out_other_days_and_other_clubs(
    match, make_fixture, clock, admin_of, club_a, club_b, next_tuesday
):
    fixture, _ = match
    lions, boys = fixture.home_team, fixture.away_team
    make_fixture(lions, boys, date=next_tuesday + dt.timedelta(days=7))
    clock(fixture, hours=8)

    found = admin_of(club_a).get(tonight_url(club_a)).json()
    assert [m["fixture"]["id"] for m in found] == [fixture.pk]
    assert found[0]["at_risk"] is True  # both below the minimum of 5 before the check
    assert admin_of(club_b).get(tonight_url(club_b)).json() == []


def test_only_the_clubs_admins_see_tonight(match, admin_of, club_a, club_b, api, make_user):
    assert admin_of(club_b).get(tonight_url(club_a)).status_code == 403
    api.force_authenticate(make_user("p@example.com", position="outfield"))
    assert api.get(tonight_url(club_a)).status_code == 403


def test_the_admin_rules_through_the_api(boys_unpaid, admin_of, club_a):
    _, boys = boys_unpaid
    client = admin_of(club_a)

    response = client.post(decide_url(club_a, boys), {"decision": "play", "note": "Cash"})

    assert response.status_code == 200
    body = response.json()
    assert body["fixture"]["status"] == S.READY
    assert body["waiting"] is False
    assert body["teams"][1]["readiness"]["outcome"] == "playing"
    assert body["teams"][1]["readiness"]["decided_by_name"] == client.user.name
    assert body["teams"][1]["readiness"]["note"] == "Cash"

    again = client.post(decide_url(club_a, boys), {"decision": "out"})
    assert again.status_code == 409


def test_a_ruling_needs_play_or_out(boys_unpaid, admin_of, club_a):
    _, boys = boys_unpaid
    response = admin_of(club_a).post(decide_url(club_a, boys), {"decision": "maybe"})
    assert response.status_code == 400


def test_tonight_drops_a_waiting_match_that_has_moved_on(
    boys_unpaid, admin, admin_of, club_a, time_machine
):
    fixture, _ = boys_unpaid
    client = admin_of(club_a)
    time_machine.move_to(fixture.kick_off + dt.timedelta(days=1), tick=False)
    [match] = client.get(tonight_url(club_a)).json()  # still waiting the next day
    assert (match["waiting"], match["at_risk"]) == (True, True)

    lifecycle.transition(fixture, S.CANCELLED, cause="admin", actor=admin)

    assert client.get(tonight_url(club_a)).json() == []
    time_machine.move_to(fixture.kick_off, tick=False)  # on the day it is still listed
    [match] = client.get(tonight_url(club_a)).json()
    assert (match["waiting"], match["at_risk"]) == (False, False)


def test_another_clubs_admin_cannot_rule(boys_unpaid, admin_of, club_a, club_b):
    _, boys = boys_unpaid
    other = admin_of(club_b)
    assert other.post(decide_url(club_b, boys), {"decision": "out"}).status_code == 404
    assert other.post(decide_url(club_a, boys), {"decision": "out"}).status_code == 403
    boys.refresh_from_db()
    assert boys.outcome == Outcome.PENDING
