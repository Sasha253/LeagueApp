"""A match that can't go ahead: a friendly or a cancellation (FR-10 to FR-12, FR-17, FR-43),
on a frozen clock."""

import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import ClubRole
from clubs.models import Division
from core.exceptions import Conflict
from fixtures import checkpoints, confirmations, fallbacks, lifecycle, readiness, replacements
from fixtures.models import (
    ConfirmationAnswer,
    Fixture,
    FixtureFallback,
    FixtureTransition,
    FriendlyInvite,
    ReplacementOffer,
)
from ledger import services as ledger
from ledger.models import LedgerEntry
from notifications.models import Kind, Notification
from notifications.tests import conftest as notification_fixtures

player = notification_fixtures.player
match = notification_fixtures.match

S = Fixture.Status
Cause = FixtureFallback.Cause
Outcome = FixtureFallback.Outcome

pytestmark = pytest.mark.django_db


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
def outsiders(player, make_team):
    """Players in neither Team: Zola (Blue Bulls, which owes money so it can't take a slot),
    Nomsa (no Team), Kgosi (a goalkeeper, no Team) and Lerato (not opted into Tuesday)."""
    people = {
        "zola": player("zola"),
        "nomsa": player("nomsa"),
        "kgosi": player("kgosi", "goalkeeper"),
        "lerato": player("lerato", nights=[]),
    }
    bulls = make_team("Blue Bulls", people["zola"])
    ledger.charge(club=bulls.club, amount="350", category="league", reason="Fee", team=bulls)
    return people


@pytest.fixture
def confirming(match, outsiders, clock, admin):
    """The match after its T-36h Confirmations, with a Division minimum of 2."""
    fixture, people = match
    Division.objects.filter(pk=fixture.division_id).update(min_players=2)
    clock(fixture, hours=36)
    checkpoints.run_due()
    fixture.refresh_from_db()
    return fixture, {**people, **outsiders}


def eligible(fixture, value=True):
    Fixture.objects.filter(pk=fixture.pk).update(friendly_eligible=value)
    fixture.refresh_from_db()


def both_out(fixture, clock):
    """No one confirmed: at T-6h both Teams are below the minimum."""
    clock(fixture, hours=6)
    checkpoints.run_due()
    fixture.refresh_from_db()
    return fixture


def lions_out(fixture, people, clock):
    """Only Old Boys reach the minimum; no other Team can take the slot, so it lapses."""
    for person in (people["pieter"], people["ayanda"]):
        confirmations.answer(fixture, person, "confirm", via="fixture")
    clock(fixture, hours=6)
    checkpoints.run_due()
    fixture.refresh_from_db()
    return fixture


def sent(fixture, kind, **filters):
    return Notification.objects.filter(fixture=fixture, kind=kind, **filters)


def names(notifications):
    return sorted(n.recipient.name for n in notifications)


def invite_of(fixture, person):
    return FriendlyInvite.objects.get(fallback__fixture=fixture, player=person).notification


def answer_invite(user, notification, value="confirm"):
    client = APIClient()
    client.force_authenticate(user)
    return client.post(
        reverse("api-v1:notification-answer", kwargs={"notification_id": notification.pk}),
        {"answer": value},
        format="json",
    )


# Both Teams out (FR-10 to FR-12)


def test_both_teams_out_and_not_friendly_eligible_is_cancelled(confirming, clock):
    fixture, _ = confirming
    both_out(fixture, clock)

    assert fixture.status == S.CANCELLED
    fallback = fixture.fallback
    assert (fallback.cause, fallback.outcome, fallback.remaining_team) == (
        Cause.BOTH_TEAMS_OUT,
        Outcome.CANCELLED,
        None,
    )
    assert fallback.kick_off == fixture.kick_off
    moves = [(t.from_status, t.to_status) for t in fixture.transitions.all()][-2:]
    assert moves == [(S.CONFIRMING, S.BOTH_TEAMS_OUT), (S.BOTH_TEAMS_OUT, S.CANCELLED)]
    assert fixture.transitions.last().cause == FixtureTransition.Cause.SYSTEM
    assert not FriendlyInvite.objects.exists()


def test_a_cancellation_tells_both_teams_and_the_officials(confirming, clock):
    fixture, _ = confirming
    both_out(fixture, clock)

    general = sent(fixture, Kind.GENERAL, title="Red Lions vs Old Boys is cancelled")
    assert names(general) == ["Ayanda", "Pieter", "Sipho", "Thandi"]
    assert "Find a match" in general[0].body
    officials = sent(fixture, Kind.UPDATE, title="Red Lions vs Old Boys is cancelled")
    assert names(officials) == ["Ada Admin", "Rita Referee"]
    assert "Both Teams are out." in officials[0].body
    assert not sent(fixture, Kind.CONFIRMATION, closed_at__isnull=True).exists()


def test_both_teams_out_and_friendly_eligible_becomes_a_friendly(confirming, clock):
    fixture, _ = confirming
    eligible(fixture)
    both_out(fixture, clock)

    assert fixture.status == S.FRIENDLY
    assert fixture.fallback.outcome == Outcome.FRIENDLY
    assert fixture.transitions.last().note == "Both Teams are out; it is open as a friendly."


def test_a_friendly_from_both_teams_out_notifies_as_the_prd_says(confirming, clock):
    fixture, _ = confirming
    eligible(fixture)
    both_out(fixture, clock)

    # FR-10: both Teams' Players, with "Find a match".
    general = sent(fixture, Kind.GENERAL)
    assert names(general) == ["Ayanda", "Pieter", "Sipho", "Thandi"]
    assert {n.title for n in general} == {
        "Red Lions vs Old Boys is off for Red Lions",
        "Red Lions vs Old Boys is off for Old Boys",
    }
    # FR-11: Players outside both Teams, opted into the Night, free to join until kick-off.
    invites = sent(fixture, Kind.CONFIRMATION, closed_at__isnull=True)
    assert names(invites) == ["Kgosi", "Nomsa", "Zola"]
    assert {n.answer_by for n in invites} == {fixture.kick_off}
    assert invites[0].title == "Friendly: free to join"
    assert FriendlyInvite.objects.count() == 3
    # FR-12: the Night's Admins and the pitch's Referee.
    officials = sent(fixture, Kind.UPDATE, title="Red Lions vs Old Boys is now a friendly")
    assert names(officials) == ["Ada Admin", "Rita Referee"]
    assert "3 Players invited to join." in officials[0].body


def test_the_league_confirmations_close_when_it_becomes_a_friendly(confirming, clock):
    fixture, people = confirming
    eligible(fixture)
    league = sent(fixture, Kind.CONFIRMATION, recipient=people["thandi"]).get()
    both_out(fixture, clock)

    league.refresh_from_db()
    assert league.closed_at is not None


def test_an_admin_ruling_that_leaves_both_out_after_kick_off_cancels(match, clock, admin):
    """The Confirmations never went out, so both Teams wait for the Admin, who rules them
    out only after kick-off: too late for a friendly."""
    fixture, _ = match
    eligible(fixture)
    clock(fixture, hours=6)
    checkpoints.run_due()
    clock(fixture, hours=-1)

    for row in fixture.readiness.all():
        readiness.decide(row, admin, "out")

    fixture.refresh_from_db()
    assert fixture.status == S.CANCELLED
    last = fixture.transitions.last()
    assert (last.cause, last.actor) == (FixtureTransition.Cause.ADMIN, admin)


# No replacement found (FR-17)


def test_no_replacement_and_not_friendly_eligible_is_cancelled(confirming, clock):
    fixture, _ = confirming
    lions_out(fixture, confirming[1], clock)

    assert ReplacementOffer.objects.get(fixture=fixture).status == "lapsed"
    assert fixture.status == S.CANCELLED
    fallback = fixture.fallback
    assert (fallback.cause, fallback.remaining_team.name) == (Cause.NO_REPLACEMENT, "Old Boys")
    remaining = sent(fixture, Kind.UPDATE, title="Red Lions vs Old Boys is cancelled")
    assert names(remaining.exclude(recipient__name__in=["Ada Admin", "Rita Referee"])) == [
        "Ayanda",
        "Pieter",
    ]
    assert "No new opponent was found." in remaining.get(recipient__name="Pieter").body
    out = sent(fixture, Kind.GENERAL, title="Red Lions vs Old Boys is cancelled")
    assert names(out) == ["Sipho", "Thandi"]


def test_no_replacement_and_friendly_eligible_becomes_a_friendly(confirming, clock):
    fixture, people = confirming
    eligible(fixture)
    lions_out(fixture, people, clock)

    assert fixture.status == S.FRIENDLY
    # FR-17: General to the out Team, Confirmation to every Player outside it.
    out = sent(fixture, Kind.GENERAL, title="Red Lions vs Old Boys is off for Red Lions")
    assert names(out) == ["Sipho", "Thandi"]
    invites = sent(fixture, Kind.CONFIRMATION, closed_at__isnull=True)
    assert names(invites) == ["Ayanda", "Kgosi", "Nomsa", "Pieter", "Zola"]
    assert invites[0].title == "Friendly with Old Boys: free to join"
    officials = sent(fixture, Kind.UPDATE, title="Red Lions vs Old Boys is now a friendly")
    assert names(officials) == ["Ada Admin", "Rita Referee"]
    assert "Red Lions is out and no other Team took the slot." in officials[0].body


def test_an_offer_that_lapses_later_falls_back_then(match, make_team, player, clock, admin):
    fixture, people = match
    eligible(fixture)
    Division.objects.filter(pk=fixture.division_id).update(min_players=2)
    make_team("Green Geckos", player("gugu"))  # can take the slot, but doesn't
    clock(fixture, hours=36)
    checkpoints.run_due()
    lions_out(fixture, people, clock)
    assert fixture.status == S.REPLACEMENT_OFFERED

    clock(fixture, hours=2)
    replacements.lapse_due()

    fixture.refresh_from_db()
    assert fixture.status == S.FRIENDLY
    assert fixture.fallback.cause == Cause.NO_REPLACEMENT
    # The Captain's offer is closed; Gugu is invited to the friendly instead.
    assert names(sent(fixture, Kind.CONFIRMATION, closed_at__isnull=True)) == [
        "Ayanda",
        "Gugu",
        "Pieter",
    ]


def test_falling_back_happens_once(confirming, clock):
    fixture, _ = confirming
    both_out(fixture, clock)
    first = fixture.fallback

    assert fallbacks.fall_back(fixture, Cause.BOTH_TEAMS_OUT) == first
    assert FixtureFallback.objects.count() == 1


def test_only_a_match_that_is_out_falls_back(match):
    fixture, _ = match
    with pytest.raises(Conflict):
        fallbacks.fall_back(fixture, Cause.BOTH_TEAMS_OUT)
    lifecycle.transition(fixture, S.BOTH_TEAMS_OUT, cause=FixtureTransition.Cause.SYSTEM)
    with pytest.raises(Conflict):
        fallbacks.fall_back(fixture, Cause.NO_REPLACEMENT, remaining=fixture.home_team)


# Credit on cancel (FR-43, FR-52)


@pytest.fixture
def payments(confirming, make_fixture, next_tuesday):
    """Paid for this match: Thandi's own R 100 (card) and R 200 for the whole of Old Boys
    (cash). Not for it: Red Lions' season fee R 350 and Sipho's R 80 for another match."""
    fixture, people = confirming
    lions, boys = fixture.home_team, fixture.away_team
    pay = ledger.record_payment
    thandi = pay(
        team=lions,
        amount="100",
        method="card",
        recorded_by=None,
        player=people["thandi"],
        fixture=fixture,
    )
    whole = pay(team=boys, amount="200", method="cash", recorded_by=None, fixture=fixture)
    pay(team=lions, amount="350", method="cash", recorded_by=None)
    other = make_fixture(lions, boys, date=next_tuesday + dt.timedelta(days=7))
    pay(
        team=lions,
        amount="80",
        method="card",
        recorded_by=None,
        player=people["sipho"],
        fixture=other,
    )
    return fixture, people, {"thandi": thandi, "whole": whole}


def test_a_cancellation_returns_each_payment_as_credit_to_whoever_paid(payments, clock):
    fixture, people, paid = payments
    both_out(fixture, clock)

    club = fixture.club
    assert ledger.player_credit(club, people["thandi"]) == Decimal("100.00")
    assert ledger.team_credit(fixture.away_team) == Decimal("200.00")
    assert ledger.player_credit(club, people["sipho"]) == Decimal("0.00")
    assert ledger.team_credit(fixture.home_team) == Decimal("0.00")
    credits = LedgerEntry.objects.filter(kind="credit", fixture=fixture)
    assert {c.source_id for c in credits} == {paid["thandi"].pk, paid["whole"].pk}
    assert {c.reason for c in credits} == {"Match cancelled: Red Lions vs Old Boys, Tue 27 Oct"}
    # The payments stay paid (chunk 8): no card refund.
    assert ledger.team_balance(fixture.away_team).paid == Decimal("200.00")
    officials = sent(fixture, Kind.UPDATE, title="Red Lions vs Old Boys is cancelled")
    assert "R 300 returned as credit." in officials[0].body
    general = sent(fixture, Kind.GENERAL).first()
    assert "Anything paid for this match is now credit." in general.body


def test_only_what_is_left_of_a_payment_is_returned_and_reversed_ones_are_skipped(payments, clock):
    fixture, people, paid = payments
    ledger.return_as_credit(paid["thandi"], reason="Goodwill", recorded_by=None, amount="40")
    ledger.reverse(paid["whole"], reason="Recorded twice", recorded_by=None)
    both_out(fixture, clock)

    assert ledger.player_credit(fixture.club, people["thandi"]) == Decimal("100.00")
    assert ledger.team_credit(fixture.away_team) == Decimal("0.00")
    again = ledger.return_fixture_payments(fixture, reason="Again", recorded_by=None)
    assert again == []


def test_a_friendly_returns_no_credit(payments, clock):
    fixture, _, _ = payments
    eligible(fixture)
    both_out(fixture, clock)

    assert fixture.status == S.FRIENDLY
    assert not LedgerEntry.objects.filter(kind="credit").exists()


def test_cancel_match_records_who_cancelled(payments, admin):
    fixture, _, _ = payments
    credits = fallbacks.cancel_match(fixture, actor=admin, note="Pitch flooded.")

    assert len(credits) == 2
    assert {c.recorded_by for c in credits} == {admin}
    last = fixture.transitions.last()
    assert (last.to_status, last.actor, last.note) == (S.CANCELLED, admin, "Pitch flooded.")


# Joining the friendly (FR-11, FR-17)


@pytest.fixture
def friendly(confirming, clock):
    fixture, people = confirming
    eligible(fixture)
    clock(fixture, hours=6)
    checkpoints.run_due()
    fixture.refresh_from_db()
    assert fixture.status == S.FRIENDLY
    return fixture, people


def test_an_invited_player_joins_and_can_change_their_mind(friendly):
    fixture, people = friendly
    invite = invite_of(fixture, people["nomsa"])

    assert answer_invite(people["nomsa"], invite).status_code == 200
    assert [i.player for i in fallbacks.joined(fixture.fallback)] == [people["nomsa"]]
    assert answer_invite(people["nomsa"], invite, "decline").status_code == 200
    assert list(fallbacks.joined(fixture.fallback)) == []
    assert not ConfirmationAnswer.objects.filter(player=people["nomsa"]).exists()


def test_no_joining_after_kick_off(friendly, clock):
    fixture, people = friendly
    clock(fixture, hours=0)

    response = answer_invite(people["zola"], invite_of(fixture, people["zola"]))

    assert response.status_code == 409


def test_no_joining_once_the_friendly_is_off(friendly):
    fixture, people = friendly
    lifecycle.transition(fixture, S.CANCELLED, cause=FixtureTransition.Cause.ADMIN)
    invite = invite_of(fixture, people["kgosi"])

    response = answer_invite(people["kgosi"], invite)

    assert response.status_code == 409
    assert "no longer on" in response.json()["detail"]
    invite.refresh_from_db()
    assert invite.answer == ""


# What the Admin sees


def test_the_admin_sees_the_friendly_and_who_joined(friendly, admin_of, club_a, club_b):
    fixture, people = friendly
    answer_invite(people["kgosi"], invite_of(fixture, people["kgosi"]))
    url = reverse("api-v1:club-fixtures-detail", kwargs={"club_id": club_a.pk, "pk": fixture.pk})

    body = admin_of(club_a).get(url).json()["fallback"]

    assert (body["cause"], body["outcome"], body["remaining_team"]) == (
        "both_teams_out",
        "friendly",
        None,
    )
    assert body["invited"] == 3
    assert [(p["name"], p["position"]) for p in body["joined"]] == [("Kgosi", "goalkeeper")]
    assert (body["credit_returned"], body["credits"]) == ("0.00", 0)
    other = reverse("api-v1:club-fixtures-detail", kwargs={"club_id": club_b.pk, "pk": fixture.pk})
    assert admin_of(club_b).get(other).status_code == 404


def test_the_admin_sees_the_credit_returned(payments, clock, admin_of, club_a):
    fixture, _, _ = payments
    both_out(fixture, clock)
    url = reverse("api-v1:club-fixtures-detail", kwargs={"club_id": club_a.pk, "pk": fixture.pk})

    body = admin_of(club_a).get(url).json()["fallback"]

    assert (body["outcome"], body["credit_returned"], body["credits"]) == ("cancelled", "300.00", 2)


def test_no_fallback_while_the_match_is_on(match, admin_of, club_a):
    fixture, _ = match
    url = reverse("api-v1:club-fixtures-detail", kwargs={"club_id": club_a.pk, "pk": fixture.pk})

    assert admin_of(club_a).get(url).json()["fallback"] is None


def test_fallbacks_and_invites_are_never_changed_or_deleted(friendly):
    fixture, _ = friendly
    fallback = fixture.fallback
    with pytest.raises(ValueError):
        fallback.save()
    with pytest.raises(ValueError):
        fallback.delete()
    with pytest.raises(ValueError):
        fallback.invites.first().delete()
