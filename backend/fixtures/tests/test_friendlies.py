"""Friendly fees (FR-24, FR-49): the fee, who pays it, the Captain and the friendly's
Barcode, on a frozen clock."""

import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import ClubRole
from barcodes import services as barcodes
from barcodes import signing
from barcodes.models import Barcode
from core.exceptions import Conflict
from fixtures import fallbacks, friendlies
from fixtures.models import Fixture, FixtureFallback, FriendlyFee, FriendlyInvite
from ledger import services as ledger
from ledger.models import LedgerEntry
from notifications import services as notifications
from notifications.models import Kind, Notification
from notifications.tests import conftest as notification_fixtures

player = notification_fixtures.player
match = notification_fixtures.match

S = Fixture.Status
Cause = FixtureFallback.Cause
Payer = FriendlyFee.Payer

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin(club_a, make_user, give_role):
    user = make_user("admin@example.com", name="Ada Admin")
    give_role(user, club_a, ClubRole.Role.ADMIN)
    return user


@pytest.fixture
def outsiders(player):
    """Players in neither Team, opted into Tuesday."""
    return {"zola": player("zola"), "nomsa": player("nomsa"), "kgosi": player("kgosi")}


@pytest.fixture
def at(time_machine):
    """Freezes the clock `hours` before the Fixture's kick-off."""

    def move(fixture, hours=10):
        moment = fixture.kick_off - dt.timedelta(hours=hours)
        time_machine.move_to(moment, tick=False)
        return moment

    return move


def _friendly(fixture, cause, remaining=None):
    status = S.BOTH_TEAMS_OUT if cause == Cause.BOTH_TEAMS_OUT else S.REPLACEMENT_OFFERED
    Fixture.objects.filter(pk=fixture.pk).update(status=status, friendly_eligible=True)
    fallbacks.fall_back(fixture, cause, remaining=remaining)
    fixture.refresh_from_db()
    return fixture


@pytest.fixture
def both_out(match, outsiders, at):
    """Red Lions vs Old Boys became a friendly with both Teams out; Zola and Nomsa joined."""
    fixture, people = match
    at(fixture)
    _friendly(fixture, Cause.BOTH_TEAMS_OUT)
    for name in ("zola", "nomsa"):
        join(fixture, outsiders[name])
    return fixture, {**people, **outsiders}


@pytest.fixture
def lions_left(match, outsiders, at):
    """Old Boys were out and no Team took the slot: a friendly with Red Lions still in.
    Zola joined, and so did Sipho of Red Lions."""
    fixture, people = match
    at(fixture)
    _friendly(fixture, Cause.NO_REPLACEMENT, remaining=fixture.home_team)
    join(fixture, outsiders["zola"])
    join(fixture, people["sipho"])
    return fixture, {**people, **outsiders}


def join(fixture, person):
    invite = FriendlyInvite.objects.get(fallback__fixture=fixture, player=person)
    notifications.answer(invite.notification, "confirm")


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def friendly_url(fixture, *, payments=False):
    name = "api-v1:club-fixtures-friendly-payments" if payments else "api-v1:club-fixtures-friendly"
    return reverse(name, kwargs={"club_id": fixture.club_id, "pk": fixture.pk})


def terms(fixture, admin, *, fee="150", payer=Payer.BORROWED_PLAYERS, captain=None):
    return friendlies.set_terms(fixture, fee=Decimal(fee), payer=payer, captain=captain, by=admin)


def live(fixture):
    return Barcode.objects.filter(fixture=fixture, friendly__isnull=False, revoked_at=None)


# Setting the terms


def test_admin_sets_fee_payer_and_captain(both_out, admin, club_a):
    fixture, people = both_out
    club_a.settings.friendly_fee = Decimal("200.00")
    club_a.settings.save()

    data = client_for(admin).get(friendly_url(fixture)).json()
    assert data["default_fee"] == "200.00"
    assert data["terms"] is None
    assert data["payer_choices"] == ["borrowed_players", "club"]  # No Team is still in.
    assert [p["name"] for p in data["captain_candidates"]] == ["Nomsa", "Zola"]

    response = client_for(admin).post(
        friendly_url(fixture),
        {"fee": "150.00", "payer": "borrowed_players", "captain": people["zola"].pk},
        format="json",
    )
    assert response.status_code == 200, response.content
    data = response.json()
    assert data["terms"]["fee"] == "150.00"
    assert data["terms"]["captain"]["name"] == "Zola"
    assert data["terms"]["set_by"]["name"] == "Ada Admin"
    assert (data["due"], data["paid"], data["outstanding"], data["settled"]) == (
        "150.00",
        "0.00",
        "150.00",
        False,
    )
    assert [p["name"] for p in data["payers"]] == ["Nomsa", "Zola"]
    assert data["barcode"]["state"] == "unpaid"
    assert data["barcode"]["reason"] == "The friendly still owes R 150."


def test_team_players_pay_only_when_a_team_is_still_in(both_out, admin):
    fixture, _ = both_out
    with pytest.raises(Conflict, match="Both Teams are out"):
        terms(fixture, admin, payer=Payer.TEAM_PLAYERS)


def test_team_players_are_the_remaining_teams_current_players(lions_left, admin):
    fixture, people = lions_left
    friendly = terms(fixture, admin, payer=Payer.TEAM_PLAYERS, captain=people["thandi"])
    assert [p.name for p in friendlies.payers(friendly)] == ["Sipho", "Thandi"]


def test_borrowed_players_are_those_who_joined_from_outside_the_team(lions_left, admin):
    fixture, _ = lions_left
    friendly = terms(fixture, admin)
    assert [p.name for p in friendlies.payers(friendly)] == ["Zola"]


def test_the_captain_must_play_in_the_friendly(both_out, admin):
    fixture, people = both_out
    with pytest.raises(Conflict, match="Captain must be a Player in the friendly"):
        terms(fixture, admin, captain=people["kgosi"])  # Invited, but didn't join.
    with pytest.raises(Conflict, match="Captain must be a Player in the friendly"):
        terms(fixture, admin, captain=people["thandi"])  # Her Team is out.


def test_the_remaining_teams_captain_can_captain_it(lions_left, admin):
    fixture, people = lions_left
    friendly = terms(fixture, admin, captain=people["thandi"])
    assert friendly.captain == people["thandi"]


def test_a_negative_fee_is_refused(both_out, admin):
    fixture, _ = both_out
    response = client_for(admin).post(
        friendly_url(fixture), {"fee": "-1", "payer": "club"}, format="json"
    )
    assert response.status_code == 400


def test_only_a_friendly_has_terms(match, admin, at):
    fixture, _ = match
    at(fixture)
    response = client_for(admin).get(friendly_url(fixture))
    assert response.status_code == 409


def test_terms_close_at_kick_off(both_out, admin, time_machine):
    fixture, _ = both_out
    time_machine.move_to(fixture.kick_off + dt.timedelta(minutes=1), tick=False)
    with pytest.raises(Conflict, match="kicked off"):
        terms(fixture, admin)


def test_only_the_clubs_admins_see_or_set_terms(both_out, admin_of, club_b, make_user):
    fixture, people = both_out
    other_admin = admin_of(club_b)
    assert other_admin.get(friendly_url(fixture)).status_code in (403, 404)
    body = {"fee": "0", "payer": "club"}
    assert other_admin.post(friendly_url(fixture), body, format="json").status_code in (403, 404)
    assert client_for(people["zola"]).get(friendly_url(fixture)).status_code == 403
    assert not FriendlyFee.objects.exists()


# Paying


def test_admin_records_cash_from_a_payer_as_friendly_income(both_out, admin):
    fixture, people = both_out
    terms(fixture, admin)
    response = client_for(admin).post(
        friendly_url(fixture, payments=True),
        {"player": people["zola"].pk, "amount": "100.00"},
        format="json",
    )
    assert response.status_code == 201, response.content
    data = response.json()
    assert (data["paid"], data["outstanding"]) == ("100.00", "50.00")
    assert data["money_fixed"] is True
    entry = LedgerEntry.objects.get(category="friendly")
    assert (entry.kind, entry.method, entry.subject) == ("payment", "cash", "player")
    assert (entry.user, entry.team, entry.fixture) == (people["zola"], None, fixture)
    assert entry.recorded_by == admin
    # No Team's league account changes.
    assert ledger.team_balance(fixture.home_team).paid == 0
    assert data["payments"][0]["player"]["name"] == "Zola"


def test_cash_only_from_a_payer_and_never_more_than_owed(both_out, admin):
    fixture, people = both_out
    terms(fixture, admin)
    with pytest.raises(Conflict, match="isn't one of the friendly's payers"):
        friendlies.record_cash(fixture, player=people["kgosi"], amount=Decimal("10"), by=admin)
    with pytest.raises(Conflict, match="more than the friendly still owes"):
        friendlies.record_cash(fixture, player=people["zola"], amount=Decimal("151"), by=admin)
    friendlies.record_cash(fixture, player=people["zola"], amount=Decimal("150"), by=admin)
    with pytest.raises(Conflict, match="nothing left to pay"):
        friendlies.record_cash(fixture, player=people["nomsa"], amount=Decimal("1"), by=admin)


def test_nothing_is_collected_when_the_club_pays(both_out, admin):
    fixture, people = both_out
    friendly = terms(fixture, admin, payer=Payer.CLUB)
    assert friendlies.totals(friendly).settled
    with pytest.raises(Conflict, match="Nothing is collected"):
        friendlies.record_cash(fixture, player=people["zola"], amount=Decimal("10"), by=admin)


def test_fee_and_payer_are_fixed_once_paid_but_the_captain_can_change(both_out, admin):
    fixture, people = both_out
    terms(fixture, admin, captain=people["zola"])
    friendlies.record_cash(fixture, player=people["zola"], amount=Decimal("10"), by=admin)
    with pytest.raises(Conflict, match="fixed"):
        terms(fixture, admin, fee="100", captain=people["zola"])
    with pytest.raises(Conflict, match="fixed"):
        terms(fixture, admin, payer=Payer.CLUB, captain=people["zola"])
    assert terms(fixture, admin, captain=people["nomsa"]).captain == people["nomsa"]


def test_a_cancelled_friendly_returns_payments_as_player_credit(both_out, admin):
    fixture, people = both_out
    terms(fixture, admin)
    friendlies.record_cash(fixture, player=people["zola"], amount=Decimal("80"), by=admin)
    fallbacks.cancel_match(fixture, actor=admin, note="Rain")
    assert ledger.player_credit(fixture.club, people["zola"]) == Decimal("80.00")
    assert ledger.friendly_paid(fixture) == 0


# The friendly's Barcode


def test_the_captain_gets_the_barcode_once_the_fee_is_paid(both_out, admin):
    fixture, people = both_out
    friendly = terms(fixture, admin, captain=people["zola"])
    assert not live(fixture).exists()
    friendlies.record_cash(fixture, player=people["nomsa"], amount=Decimal("150"), by=admin)

    barcode = live(fixture).get()
    assert (barcode.team, barcode.friendly, barcode.mode) == (None, friendly, "match")
    assert signing.is_signed(barcode)
    assert barcodes.status_of(barcode).valid
    told = Notification.objects.get(recipient=people["zola"], kind=Kind.UPDATE)
    assert told.title == "Payment Barcode for the friendly"


def test_a_free_or_club_paid_friendly_gets_its_barcode_at_once(both_out, admin):
    fixture, people = both_out
    terms(fixture, admin, fee="0", captain=people["zola"])
    assert live(fixture).count() == 1


def test_a_new_captain_revokes_the_old_barcode(both_out, admin):
    fixture, people = both_out
    terms(fixture, admin, payer=Payer.CLUB, captain=people["zola"])
    old = live(fixture).get()
    terms(fixture, admin, payer=Payer.CLUB, captain=people["nomsa"])
    old.refresh_from_db()
    assert old.revoke_reason == "The friendly's Captain changed."
    assert live(fixture).get().pk != old.pk


def test_the_barcode_lapses_when_the_friendly_is_cancelled(both_out, admin):
    fixture, people = both_out
    terms(fixture, admin, payer=Payer.CLUB, captain=people["zola"])
    barcode = live(fixture).get()
    fallbacks.cancel_match(fixture, actor=admin, note="Rain")
    barcode.refresh_from_db()
    assert barcodes.status_of(barcode).state == "expired"


def test_moving_a_barcode_to_another_friendly_breaks_its_signature(both_out, admin):
    fixture, people = both_out
    terms(fixture, admin, payer=Payer.CLUB, captain=people["zola"])
    barcode = live(fixture).get()
    barcode.friendly_id = barcode.friendly_id + 1
    assert not signing.is_signed(barcode)


def test_only_the_captain_and_admins_see_the_friendly_barcode(both_out, admin):
    fixture, people = both_out
    terms(fixture, admin, payer=Payer.CLUB, captain=people["zola"])
    url = reverse("api-v1:friendly-barcode", kwargs={"fixture_id": fixture.pk})

    data = client_for(people["zola"]).get(url).json()
    assert data["state"] == "valid"
    assert data["barcode"]["team"] is None
    assert data["barcode"]["holder"] == "Friendly: Red Lions vs Old Boys"
    assert client_for(admin).get(url).status_code == 200
    assert client_for(people["nomsa"]).get(url).status_code == 404

    mine = client_for(people["zola"]).get(reverse("api-v1:my-friendlies")).json()
    assert [row["fixture"]["id"] for row in mine] == [fixture.pk]
    assert client_for(people["nomsa"]).get(reverse("api-v1:my-friendlies")).json() == []


def test_the_captain_sees_why_there_is_no_barcode_yet(both_out, admin):
    fixture, people = both_out
    terms(fixture, admin, captain=people["zola"])
    url = reverse("api-v1:friendly-barcode", kwargs={"fixture_id": fixture.pk})
    data = client_for(people["zola"]).get(url).json()
    assert (data["state"], data["barcode"]) == ("unpaid", None)


# At the gate (FR-23)


@pytest.fixture
def at_the_gate(time_machine):
    def move(fixture):
        time_machine.move_to(fixture.kick_off - dt.timedelta(minutes=30), tick=False)

    return move


def test_the_friendly_barcode_lets_it_in_once(both_out, admin, at_the_gate):
    fixture, people = both_out
    terms(fixture, admin, captain=people["zola"])
    friendlies.record_cash(fixture, player=people["zola"], amount=Decimal("150"), by=admin)
    barcode = live(fixture).get()
    at_the_gate(fixture)

    first = barcodes.scan(barcode.code, club=fixture.club, by=admin, method="manual")
    assert first.paid, first.status
    assert first.match == fixture
    second = barcodes.scan(barcode.code, club=fixture.club, by=admin, method="manual")
    assert second.status.state == "used"


def test_the_gate_answer_names_the_friendly(both_out, admin, at_the_gate):
    fixture, people = both_out
    terms(fixture, admin, captain=people["zola"])
    friendlies.record_cash(fixture, player=people["zola"], amount=Decimal("150"), by=admin)
    barcode = live(fixture).get()
    at_the_gate(fixture)
    url = reverse("api-v1:club-scans", kwargs={"club_id": fixture.club_id})
    data = client_for(admin).post(url, {"code": barcode.code, "method": "manual"}).json()
    assert data["paid"] is True
    assert (data["team"], data["holder"]) == (None, "Friendly: Red Lions vs Old Boys")
    assert (data["paid_amount"], data["paid_methods"]) == ("150.00", ["cash"])


def test_a_teams_own_barcode_doesnt_let_it_into_a_friendly(match, admin, at, at_the_gate):
    fixture, _ = match
    at(fixture)
    lions = fixture.home_team
    barcode = Barcode(
        club=fixture.club,
        team=lions,
        mode="match",
        season=lions.season,
        fixture=fixture,
        nonce=signing.new_nonce(),
    )
    barcode.code = signing.sign(barcode)
    barcode.save()
    _friendly(fixture, Cause.NO_REPLACEMENT, remaining=lions)
    at_the_gate(fixture)
    result = barcodes.scan(barcode.code, club=fixture.club, by=admin, method="manual")
    assert not result.paid
    assert result.status.state in ("friendly", "expired")
    assert "friendly" in result.status.reason


def test_a_teams_next_match_skips_a_friendly(match, at):
    fixture, _ = match
    at(fixture)
    _friendly(fixture, Cause.BOTH_TEAMS_OUT)
    assert barcodes.next_match(fixture.home_team) is None
    assert timezone.now() < fixture.kick_off
