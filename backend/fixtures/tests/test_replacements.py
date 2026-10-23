"""One Team out: the replacement opponent (FR-13 to FR-16), on a frozen clock."""

import datetime as dt

import pytest
from django.urls import reverse

from accounts.models import ClubRole
from clubs.models import Division
from core.exceptions import Conflict
from fixtures import checkpoints, confirmations, lifecycle, readiness, replacements
from fixtures.models import (
    Fixture,
    FixtureTransition,
    ReplacementCandidate,
    ReplacementOffer,
)
from ledger import services as ledger
from notifications.models import ACTIONS, FIND_MATCH, Kind, Notification
from notifications.tests import conftest as notification_fixtures
from teams.models import Team

player = notification_fixtures.player
match = notification_fixtures.match

S = Fixture.Status
Status = ReplacementOffer.Status

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
def lapsed(monkeypatch):
    """Every `replacement_lapsed` signal sent, as (fixture id, offer id)."""
    sent = []

    def receiver(sender, fixture, offer, **kwargs):
        sent.append((fixture.pk, offer.pk))

    replacements.replacement_lapsed.connect(receiver, dispatch_uid="test-lapsed")
    yield sent
    replacements.replacement_lapsed.disconnect(dispatch_uid="test-lapsed")


@pytest.fixture
def others(make_team, player):
    """Two more Teams of Division 2 that can take a slot: Blue Bulls and Green Geckos."""
    people = {
        "bongi": player("bongi"),
        "bheki": player("bheki"),
        "gugu": player("gugu"),
        "lerato": player("lerato", nights=[]),  # hasn't opted into Tuesday
    }
    bulls = make_team("Blue Bulls", people["bongi"], people["bheki"], people["lerato"])
    geckos = make_team("Green Geckos", people["gugu"])
    return {"bulls": bulls, "geckos": geckos}, people


@pytest.fixture
def lions_out(match, others, clock, admin):
    """At T-6h Red Lions (home) are below the minimum of 2; Old Boys play. The slot opens."""
    fixture, people = match
    Division.objects.filter(pk=fixture.division_id).update(min_players=2)
    clock(fixture, hours=36)
    checkpoints.run_due()
    fixture.refresh_from_db()
    for person in (people["thandi"], people["pieter"], people["ayanda"]):
        confirmations.answer(fixture, person, "confirm", via="fixture")
    clock(fixture, hours=6)
    checkpoints.run_due()
    fixture.refresh_from_db()
    assert fixture.status == S.REPLACEMENT_OFFERED
    return fixture, {**people, **others[1]}, others[0]


def offer_of(fixture):
    return ReplacementOffer.objects.get(fixture=fixture)


def sent(fixture, kind, **filters):
    return Notification.objects.filter(fixture=fixture, kind=kind, **filters)


def names(notifications):
    return sorted(n.recipient.name for n in notifications)


def offer_to(fixture, team):
    return ReplacementCandidate.objects.get(offer__fixture=fixture, team=team).notification


# Opening the offer (FR-13 to FR-16)


def test_one_team_out_offers_the_slot(lions_out):
    fixture, _, teams = lions_out
    offer = offer_of(fixture)

    assert offer.status == Status.OPEN
    assert (offer.out_team.name, offer.remaining_team.name) == ("Red Lions", "Old Boys")
    assert offer.slot == ReplacementOffer.Slot.HOME
    assert offer.closes_at == fixture.kick_off - dt.timedelta(hours=2)
    assert {c.team for c in offer.candidates.all()} == {teams["bulls"], teams["geckos"]}
    moves = [(t.from_status, t.to_status) for t in fixture.transitions.all()][-2:]
    assert moves == [(S.CONFIRMING, S.ONE_TEAM_OUT), (S.ONE_TEAM_OUT, S.REPLACEMENT_OFFERED)]
    assert fixture.transitions.last().cause == FixtureTransition.Cause.SYSTEM


def test_the_out_team_gets_a_general_notification_with_find_a_match(lions_out):
    fixture, _, _ = lions_out
    general = sent(fixture, Kind.GENERAL)

    assert names(general) == ["Sipho", "Thandi"]
    assert general[0].title == "Red Lions is out of Red Lions vs Old Boys"
    assert FIND_MATCH in [key for key, _, _ in ACTIONS[Kind.GENERAL]]  # the button
    assert "Find a match" in general[0].body


def test_the_remaining_team_and_the_officials_get_updates(lions_out):
    fixture, _, _ = lions_out
    updates = sent(fixture, Kind.UPDATE)

    team = updates.filter(title="Red Lions withdrew")
    assert names(team) == ["Ayanda", "Pieter"]
    assert "finding Old Boys a new opponent" in team[0].body
    officials = updates.filter(title="Red Lions is out of Red Lions vs Old Boys")
    assert names(officials) == ["Ada Admin", "Rita Referee"]
    assert "Offered to 2 Teams until" in officials[0].body


def test_each_eligible_captain_gets_an_offer_until_it_closes(lions_out):
    fixture, _, teams = lions_out
    offers = sent(fixture, Kind.CONFIRMATION, replacement_candidate__isnull=False)

    assert names(offers) == ["Bongi", "Gugu"]
    bulls = offer_to(fixture, teams["bulls"])
    assert bulls.title == "Open slot: play Old Boys"
    assert "Take it for Blue Bulls?" in bulls.body
    assert bulls.answer_by == offer_of(fixture).closes_at
    # Only Captains: the Bulls' other Players hear nothing yet.
    assert not Notification.objects.filter(recipient__name="Bheki").exists()


def test_who_is_eligible(match, others, make_team, make_fixture, player, friday_division, clock):
    fixture, _ = match
    owing = make_team("Owing United", player("olwethu"))
    ledger.charge(club=owing.club, amount="350", category="league", reason="Fee", team=owing)
    busy = make_team("Busy Rovers", player("busisiwe"))
    busy_rival = make_team("Busy Rivals", player("rivaldo"))
    make_fixture(busy, busy_rival, time="18:00")
    make_team("Friday Five", player("fikile"), division=friday_division)
    make_team("Waiting FC", player("wanda"), status=Team.Status.REQUESTED)
    make_team("Quiet Captains", player("quinton", nights=[]))
    lifecycle.transition(fixture, S.ONE_TEAM_OUT, cause=FixtureTransition.Cause.SYSTEM)

    offer = replacements.open_offer(fixture, fixture.home_team)

    offered = sorted(c.team.name for c in offer.candidates.all())
    assert offered == ["Blue Bulls", "Green Geckos"]


def test_with_no_eligible_team_it_lapses_at_once(match, clock, admin, lapsed):
    fixture, _ = match
    clock(fixture, hours=6)
    lifecycle.transition(fixture, S.ONE_TEAM_OUT, cause=FixtureTransition.Cause.SYSTEM)

    offer = replacements.open_offer(fixture, fixture.away_team)

    offer.refresh_from_db()
    assert offer.status == Status.LAPSED
    assert lapsed == [(fixture.pk, offer.pk)]
    officials = sent(fixture, Kind.UPDATE, recipient__name="Ada Admin").get()
    assert "No other Team can take the slot." in officials.body


def test_an_offer_opened_after_its_close_time_lapses_at_once(match, others, clock, lapsed):
    fixture, _ = match
    clock(fixture, hours=1)
    lifecycle.transition(fixture, S.ONE_TEAM_OUT, cause=FixtureTransition.Cause.SYSTEM)

    offer = replacements.open_offer(fixture, fixture.away_team)

    assert offer.candidates.count() == 0
    offer.refresh_from_db()
    assert offer.status == Status.LAPSED
    assert lapsed == [(fixture.pk, offer.pk)]


def test_an_admin_ruling_a_team_out_opens_the_offer_as_the_admin(match, others, clock, admin):
    fixture, people = match
    Division.objects.filter(pk=fixture.division_id).update(min_players=2)
    clock(fixture, hours=36)
    checkpoints.run_due()
    fixture.refresh_from_db()
    for person in (people["thandi"], people["sipho"], people["pieter"], people["ayanda"]):
        confirmations.answer(fixture, person, "confirm", via="fixture")
    ledger.charge(
        club=fixture.club, amount="350", category="league", reason="Fee", team=fixture.away_team
    )
    clock(fixture, hours=6)
    checkpoints.run_due()
    boys = fixture.readiness.get(team=fixture.away_team)

    readiness.decide(boys, admin, "out")

    offer = offer_of(fixture)
    assert (offer.out_team.name, offer.slot) == ("Old Boys", ReplacementOffer.Slot.AWAY)
    last = fixture.transitions.last()
    assert (last.to_status, last.cause, last.actor) == (
        S.REPLACEMENT_OFFERED,
        FixtureTransition.Cause.ADMIN,
        admin,
    )


def test_both_teams_out_opens_no_offer(match, clock):
    fixture, _ = match
    clock(fixture, hours=36)
    checkpoints.run_due()
    clock(fixture, hours=6)
    checkpoints.run_due()

    fixture.refresh_from_db()
    assert fixture.status == S.BOTH_TEAMS_OUT
    assert not ReplacementOffer.objects.exists()


# Accepting (FR-15, FR-16)


def take(client_user, notification, value="confirm"):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(client_user)
    return client.post(
        reverse("api-v1:notification-answer", kwargs={"notification_id": notification.pk}),
        {"answer": value},
        format="json",
    )


def test_the_first_captain_to_accept_takes_the_slot(lions_out):
    fixture, people, teams = lions_out

    response = take(people["bongi"], offer_to(fixture, teams["bulls"]))

    assert response.status_code == 200
    fixture.refresh_from_db()
    assert (fixture.home_team, fixture.away_team.name) == (teams["bulls"], "Old Boys")
    assert fixture.status == S.READY  # after T-6h
    offer = offer_of(fixture)
    assert (offer.status, offer.accepted_team, offer.accepted_by) == (
        Status.ACCEPTED,
        teams["bulls"],
        people["bongi"],
    )
    last = fixture.transitions.last()
    assert (last.cause, last.actor, last.note) == (
        FixtureTransition.Cause.CAPTAIN,
        people["bongi"],
        "Blue Bulls replaces Red Lions.",
    )


def test_the_new_opponent_gets_confirmations_and_everyone_else_an_update(lions_out):
    fixture, people, teams = lions_out
    take(people["bongi"], offer_to(fixture, teams["bulls"]))

    new = sent(
        fixture,
        Kind.CONFIRMATION,
        replacement_candidate__isnull=True,
        recipient__team_memberships__team=teams["bulls"],
    )
    assert names(new) == ["Bheki", "Bongi"]  # Lerato hasn't opted into Tuesday
    assert new[0].title == "Blue Bulls vs Old Boys"
    assert new[0].answer_by == fixture.kick_off
    remaining = sent(fixture, Kind.UPDATE, title="New opponent: Blue Bulls")
    assert names(remaining) == ["Ayanda", "Pieter"]
    officials = sent(fixture, Kind.UPDATE, title="Blue Bulls replaces Red Lions")
    assert names(officials) == ["Ada Admin", "Rita Referee"]


def test_every_offer_closes_once_taken(lions_out):
    fixture, people, teams = lions_out
    take(people["bongi"], offer_to(fixture, teams["bulls"]))

    geckos = offer_to(fixture, teams["geckos"])
    assert geckos.closed_at is not None
    response = take(people["gugu"], geckos)
    assert response.status_code == 409
    geckos.refresh_from_db()
    assert geckos.answer == ""


def test_a_second_accept_is_refused(lions_out):
    fixture, people, teams = lions_out
    first = ReplacementCandidate.objects.get(offer__fixture=fixture, team=teams["bulls"])
    second = ReplacementCandidate.objects.get(offer__fixture=fixture, team=teams["geckos"])
    replacements.accept(first, people["bongi"])

    with pytest.raises(Conflict, match="Another Team took this slot first"):
        replacements.accept(second, people["gugu"])

    fixture.refresh_from_db()
    assert fixture.home_team == teams["bulls"]


def test_declining_only_records_the_answer(lions_out):
    fixture, people, teams = lions_out

    response = take(people["bongi"], offer_to(fixture, teams["bulls"]), "decline")

    assert response.status_code == 200
    assert offer_of(fixture).status == Status.OPEN
    # Changing their mind while it is open takes the slot.
    assert take(people["bongi"], offer_to(fixture, teams["bulls"])).status_code == 200
    assert offer_of(fixture).accepted_team == teams["bulls"]


def test_only_the_teams_captain_can_accept(lions_out):
    fixture, people, teams = lions_out
    Team.objects.filter(pk=teams["bulls"].pk).update(captain=people["bheki"])

    response = take(people["bongi"], offer_to(fixture, teams["bulls"]))

    assert response.status_code == 409
    assert "Only Blue Bulls's Captain" in response.json()["detail"]
    assert offer_of(fixture).status == Status.OPEN


def test_a_team_that_now_owes_money_cannot_accept(lions_out):
    fixture, people, teams = lions_out
    ledger.charge(
        club=fixture.club, amount="350", category="league", reason="Fee", team=teams["bulls"]
    )

    response = take(people["bongi"], offer_to(fixture, teams["bulls"]))

    assert response.status_code == 409
    assert "still owes money" in response.json()["detail"]


def test_a_team_that_took_another_slot_that_day_cannot_take_this_one(
    lions_out, make_team, make_fixture, player
):
    fixture, people, teams = lions_out
    make_fixture(
        teams["bulls"],
        make_team("Purple Pythons", player("palesa")),
        time="21:00",
        date=fixture.kick_off.date(),
    )

    response = take(people["bongi"], offer_to(fixture, teams["bulls"]))

    assert response.status_code == 409
    assert "already has a match that day" in response.json()["detail"]


def test_no_accept_after_the_offer_closes(lions_out, clock):
    fixture, people, teams = lions_out
    candidate = ReplacementCandidate.objects.get(offer__fixture=fixture, team=teams["bulls"])
    clock(fixture, hours=2)

    with pytest.raises(Conflict, match="This slot closed at"):
        replacements.accept(candidate, people["bongi"])
    assert take(people["bongi"], candidate.notification).status_code == 409


def test_no_accept_once_the_match_moved_on(lions_out):
    fixture, people, teams = lions_out
    lifecycle.transition(fixture, S.CANCELLED, cause=FixtureTransition.Cause.ADMIN)
    candidate = ReplacementCandidate.objects.get(offer__fixture=fixture, team=teams["bulls"])

    with pytest.raises(Conflict, match="moved on"):
        replacements.accept(candidate, people["bongi"])


# Status and answers by when the slot is taken


def open_early(fixture, clock, hours):
    clock(fixture, hours=hours)
    lifecycle.transition(fixture, S.ONE_TEAM_OUT, cause=FixtureTransition.Cause.CAPTAIN)
    return replacements.open_offer(fixture, fixture.home_team)


def test_taken_before_t36h_the_match_is_scheduled_again(match, others, clock):
    fixture, _ = match
    teams, people = others
    offer = open_early(fixture, clock, hours=48)
    candidate = offer.candidates.get(team=teams["bulls"])

    replacements.accept(candidate, people["bongi"])

    fixture.refresh_from_db()
    assert fixture.status == S.SCHEDULED
    assert not sent(fixture, Kind.CONFIRMATION, replacement_candidate__isnull=True).exists()
    clock(fixture, hours=36)
    checkpoints.run_due()  # the T-36h Confirmations go to both Teams as usual
    got = sent(fixture, Kind.CONFIRMATION, replacement_candidate__isnull=True)
    assert "Bongi" in names(got) and "Pieter" in names(got)


def test_taken_before_t6h_confirmations_run_to_the_cutoff(match, others, clock):
    fixture, _ = match
    teams, people = others
    clock(fixture, hours=36)
    checkpoints.run_due()
    fixture.refresh_from_db()
    offer = open_early(fixture, clock, hours=20)

    replacements.accept(offer.candidates.get(team=teams["bulls"]), people["bongi"])

    fixture.refresh_from_db()
    assert fixture.status == S.CONFIRMING
    new = sent(
        fixture, Kind.CONFIRMATION, recipient=people["bongi"], replacement_candidate__isnull=True
    ).get()
    assert new.answer_by == fixture.kick_off - dt.timedelta(hours=6)


def test_taken_before_t6h_without_confirmations_both_teams_get_them(match, others, clock):
    fixture, _ = match
    teams, others_people = others
    offer = open_early(fixture, clock, hours=40)
    clock(fixture, hours=20)  # the T-36h checkpoint skipped it: it was out

    replacements.accept(offer.candidates.get(team=teams["bulls"]), others_people["bongi"])

    got = names(sent(fixture, Kind.CONFIRMATION, replacement_candidate__isnull=True))
    assert got == ["Ayanda", "Bheki", "Bongi", "Pieter"]


def test_a_late_replacement_answers_until_kick_off(lions_out, clock):
    fixture, people, teams = lions_out
    take(people["bongi"], offer_to(fixture, teams["bulls"]))
    fixture.refresh_from_db()
    clock(fixture, minutes=30)

    confirmations.answer(fixture, people["bheki"], "confirm", via="fixture")
    squad = confirmations.squad(fixture, teams["bulls"])

    assert squad.confirmed == 1
    assert squad.replies_open
    assert squad.answer_by == fixture.kick_off
    with pytest.raises(Conflict):  # the remaining Team's cutoff hasn't moved
        confirmations.answer(fixture, people["pieter"], "decline", via="fixture")
    clock(fixture)
    with pytest.raises(Conflict, match="closed"):
        confirmations.answer(fixture, people["bheki"], "decline", via="fixture")


# Lapsing and withdrawing


def test_an_offer_no_one_takes_lapses_and_hands_off(lions_out, clock, lapsed):
    fixture, _, teams = lions_out
    clock(fixture, hours=2, minutes=1)
    assert replacements.lapse_due() == {"lapsed": 0, "withdrawn": 0}

    clock(fixture, hours=2)
    assert replacements.lapse_due() == {"lapsed": 1, "withdrawn": 0}

    offer = offer_of(fixture)
    assert offer.status == Status.LAPSED
    assert lapsed == [(fixture.pk, offer.pk)]
    assert offer_to(fixture, teams["bulls"]).closed_at is not None
    fixture.refresh_from_db()
    assert fixture.status == S.REPLACEMENT_OFFERED  # chunk 15 is disconnected here
    assert replacements.lapse_due() == {"lapsed": 0, "withdrawn": 0}
    assert lapsed == [(fixture.pk, offer.pk)]


def test_an_offer_for_a_match_that_moved_on_is_withdrawn(lions_out, lapsed):
    fixture, _, teams = lions_out
    lifecycle.transition(fixture, S.CANCELLED, cause=FixtureTransition.Cause.ADMIN)

    assert replacements.lapse_due() == {"lapsed": 0, "withdrawn": 1}

    assert offer_of(fixture).status == Status.WITHDRAWN
    assert offer_to(fixture, teams["geckos"]).closed_at is not None
    assert lapsed == []


def test_the_task_ends_due_offers(lions_out, clock):
    from fixtures.tasks import run_checkpoints

    fixture, _, _ = lions_out
    clock(fixture, hours=2)

    result = run_checkpoints.apply().get()

    assert result["replacement_lapsed"] == 1


# What the Admin sees


def test_the_admin_sees_the_search_on_the_fixture(lions_out, admin_of, club_a, club_b):
    fixture, people, teams = lions_out
    take(people["bongi"], offer_to(fixture, teams["bulls"]))
    url = reverse("api-v1:club-fixtures-detail", kwargs={"club_id": club_a.pk, "pk": fixture.pk})

    body = admin_of(club_a).get(url).json()

    (offer,) = body["replacements"]
    assert offer["status"] == "accepted"
    assert offer["out_team"]["name"] == "Red Lions"
    assert offer["accepted_team"]["name"] == "Blue Bulls"
    assert offer["accepted_by_name"] == "Bongi"
    assert sorted(t["name"] for t in offer["offered_to"]) == ["Blue Bulls", "Green Geckos"]
    other = reverse("api-v1:club-fixtures-detail", kwargs={"club_id": club_b.pk, "pk": fixture.pk})
    assert admin_of(club_b).get(other).status_code == 404


def test_offers_and_their_candidates_are_never_deleted(lions_out):
    fixture, _, _ = lions_out
    offer = offer_of(fixture)
    with pytest.raises(ValueError):
        offer.delete()
    with pytest.raises(ValueError):
        offer.candidates.first().delete()
