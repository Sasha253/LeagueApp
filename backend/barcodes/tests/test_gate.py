"""The gate (FR-23): a valid Barcode also has to fit the match, today, once."""

import datetime as dt

import pytest
from django.db import IntegrityError
from django.utils import timezone

from barcodes import services
from barcodes.models import Barcode, BarcodeScan
from barcodes.services import State, Status
from fixtures.models import Fixture, ReplacementOffer, TeamReadiness
from ledger import services as ledger
from ledger.models import LedgerEntry

pytestmark = pytest.mark.django_db


@pytest.fixture
def at_gate(club_a, cashier):
    """Scans `code` at Club A's gate as the cashier (an Admin)."""

    def run(code, *, fixture=None, by=None, method="camera"):
        return services.scan(code, club=club_a, by=by or cashier, method=method, fixture=fixture)

    return run


@pytest.fixture
def paid_tonight(owing, tonight, cashier, pay):
    pay(owing, cashier)
    barcode = Barcode.objects.get()
    assert barcode.fixture == tonight
    return barcode


def test_a_barcode_for_tonight_reads_paid_and_names_the_match(paid_tonight, tonight, at_gate):
    result = at_gate(paid_tonight.code)
    assert result.paid
    assert result.match == tonight
    scan = BarcodeScan.objects.get()
    assert (scan.result, scan.fixture, scan.reason) == ("paid", tonight, "")


def test_a_barcode_lets_its_team_in_once(paid_tonight, at_gate, make_user, give_role, club_a):
    at_gate(paid_tonight.code)
    referee = make_user("gate-ref@example.com", name="Rita")
    give_role(referee, club_a, "referee")
    again = at_gate(paid_tonight.code, by=referee)
    assert not again.paid
    assert again.status.state == State.USED
    first = BarcodeScan.objects.filter(result="paid").get()
    at = timezone.localtime(first.scanned_at)
    assert again.status.reason == (
        f"Already scanned at {at:%H:%M} by Cash Admin. A Barcode lets its Team in once per match."
    )
    assert list(BarcodeScan.objects.values_list("result", flat=True)) == ["not_paid", "paid"]


def test_a_barcode_for_a_later_match_is_not_valid_today(owing, match, cashier, pay, at_gate):
    pay(owing, cashier)
    result = at_gate(Barcode.objects.get().code)
    assert result.status.state == State.NOT_TODAY
    day = timezone.localdate(match.kick_off)
    assert result.status.reason == (
        f"This Barcode is for {day:%a} {day.day} {day:%b}. It isn't valid today."
    )
    assert BarcodeScan.objects.get().fixture == match


def test_the_gate_naming_another_match_reads_not_paid(
    paid_tonight, at_gate, make_fixture, make_team, make_user
):
    others = make_team("Arrows", make_user("a@example.com", position="outfield"))
    rivals = make_team("Swallows", make_user("s@example.com", position="outfield"))
    other = make_fixture(others, rivals, date=timezone.localdate(), time="00:02")
    result = at_gate(paid_tonight.code, fixture=other)
    assert result.status.state == State.WRONG_MATCH
    assert result.status.reason.startswith("This Barcode is for Red Lions's match on ")
    assert BarcodeScan.objects.get().fixture == other


def test_the_gate_naming_the_right_match_reads_paid(paid_tonight, tonight, at_gate):
    assert at_gate(paid_tonight.code, fixture=tonight).paid


def test_a_team_ruled_out_is_not_let_in(paid_tonight, tonight, at_gate, owing):
    TeamReadiness.objects.create(
        fixture=tonight,
        team=owing,
        kick_off=tonight.kick_off,
        checked_at=timezone.now(),
        confirmed=3,
        min_players=5,
        outcome=TeamReadiness.Outcome.OUT,
        reason=TeamReadiness.Reason.SHORT,
    )
    result = at_gate(paid_tonight.code)
    assert result.status.state == State.RULED_OUT
    assert result.status.reason == "Red Lions was ruled out of this match."


@pytest.mark.parametrize("offer_status", ["open", "lapsed"])
def test_a_team_whose_cancellation_was_accepted_is_not_let_in(
    paid_tonight, tonight, at_gate, owing, offer_status
):
    # A Captain's cancellation the Admin accepted leaves no T-6h record, only the offer of
    # the Team's slot to other Teams (open, or lapsed into a friendly).
    remaining = tonight.away_team if tonight.home_team_id == owing.pk else tonight.home_team
    ReplacementOffer.objects.create(
        fixture=tonight,
        kick_off=tonight.kick_off,
        out_team=owing,
        remaining_team=remaining,
        slot="home" if tonight.home_team_id == owing.pk else "away",
        opened_at=timezone.now(),
        closes_at=tonight.kick_off,
        status=offer_status,
    )
    result = at_gate(paid_tonight.code)
    assert result.status.state == State.RULED_OUT
    assert result.status.reason == "Red Lions is out of this match."
    assert BarcodeScan.objects.get().result == "not_paid"


def test_an_offer_for_an_earlier_kick_off_does_not_rule_the_team_out(
    paid_tonight, tonight, at_gate, owing
):
    remaining = tonight.away_team if tonight.home_team_id == owing.pk else tonight.home_team
    ReplacementOffer.objects.create(
        fixture=tonight,
        kick_off=tonight.kick_off - dt.timedelta(days=7),
        out_team=owing,
        remaining_team=remaining,
        slot="home" if tonight.home_team_id == owing.pk else "away",
        opened_at=timezone.now(),
        closes_at=tonight.kick_off,
        status="withdrawn",
    )
    assert at_gate(paid_tonight.code).paid


def test_a_team_let_play_at_t6h_is_let_in(paid_tonight, tonight, at_gate, owing):
    TeamReadiness.objects.create(
        fixture=tonight,
        team=owing,
        kick_off=tonight.kick_off,
        checked_at=timezone.now(),
        confirmed=6,
        min_players=5,
        outcome=TeamReadiness.Outcome.PLAYING,
    )
    assert at_gate(paid_tonight.code).paid


def test_a_match_with_both_teams_out_lets_nobody_in(paid_tonight, tonight, at_gate):
    Fixture.objects.filter(pk=tonight.pk).update(status=Fixture.Status.BOTH_TEAMS_OUT)
    result = at_gate(paid_tonight.code)
    assert result.status.state == State.MATCH_OFF
    assert result.status.reason.endswith("is off: both Teams are out.")


def test_a_reversed_payment_reads_not_paid_at_the_gate(paid_tonight, at_gate, cashier):
    entry = LedgerEntry.objects.get(kind=LedgerEntry.Kind.PAYMENT)
    ledger.reverse(entry, reason="Counted twice", recorded_by=cashier)
    result = at_gate(paid_tonight.code)
    assert result.status.state == State.UNPAID
    assert result.status.reason == "Red Lions still owes R 350."
    assert BarcodeScan.objects.get().result == "not_paid"


# Season Barcodes (cash-only mode): the Team's match today, once each


def test_a_season_barcode_needs_a_match_today(cash_only, owing, match, cashier, pay, at_gate):
    pay(owing, cashier)
    barcode = Barcode.objects.get(mode=Barcode.Mode.SEASON)
    result = at_gate(barcode.code)
    assert result.status.state == State.NO_MATCH_TODAY
    assert result.status.reason == "Red Lions has no match today."
    assert result.match is None


def test_a_season_barcode_lets_the_team_in_once_per_match(
    cash_only, owing, boys, tonight, make_fixture, cashier, pay, at_gate
):
    later = make_fixture(owing, boys, date=timezone.localdate(), time="00:05")
    pay(owing, cashier)
    barcode = Barcode.objects.get(mode=Barcode.Mode.SEASON)
    first = at_gate(barcode.code)
    second = at_gate(barcode.code)
    third = at_gate(barcode.code)
    assert (first.paid, first.match) == (True, tonight)
    assert (second.paid, second.match) == (True, later)
    assert (third.status.state, third.match) == (State.USED, tonight)


def test_a_season_barcode_for_a_match_its_team_doesnt_play(
    cash_only, owing, tonight, cashier, pay, at_gate, make_fixture, make_team, make_user
):
    pay(owing, cashier)
    barcode = Barcode.objects.get(mode=Barcode.Mode.SEASON)
    others = make_team("Arrows", make_user("a@example.com", position="outfield"))
    rivals = make_team("Swallows", make_user("s@example.com", position="outfield"))
    other = make_fixture(others, rivals, date=timezone.localdate(), time="00:02")
    result = at_gate(barcode.code, fixture=other)
    assert result.status.state == State.WRONG_MATCH
    assert result.status.reason == "Red Lions doesn't play in this match."
    assert at_gate(barcode.code, fixture=tonight).paid


def test_a_season_barcode_for_a_cancelled_match(cash_only, owing, tonight, cashier, pay, at_gate):
    pay(owing, cashier)
    barcode = Barcode.objects.get(mode=Barcode.Mode.SEASON)
    Fixture.objects.filter(pk=tonight.pk).update(status=Fixture.Status.CANCELLED)
    assert at_gate(barcode.code).status.state == State.NO_MATCH_TODAY
    named = at_gate(barcode.code, fixture=Fixture.objects.get(pk=tonight.pk))
    assert named.status.state == State.MATCH_OFF
    assert named.status.reason.endswith("was cancelled.")


def test_a_season_barcode_for_another_days_match(cash_only, owing, match, cashier, pay, at_gate):
    pay(owing, cashier)
    barcode = Barcode.objects.get(mode=Barcode.Mode.SEASON)
    assert at_gate(barcode.code, fixture=match).status.state == State.NOT_TODAY


# Single use holds even when two gates scan at once


def test_the_database_allows_one_paid_scan_per_barcode_and_match(paid_tonight, tonight, cashier):
    fields = {
        "club": paid_tonight.club,
        "barcode": paid_tonight,
        "code": paid_tonight.code,
        "method": "camera",
        "fixture": tonight,
        "scanned_by": cashier,
    }
    BarcodeScan.objects.create(**fields, result="paid")
    BarcodeScan.objects.create(**fields, result="not_paid", reason="Already scanned.")
    with pytest.raises(IntegrityError):
        BarcodeScan.objects.create(**fields, result="paid")


def test_a_second_gate_in_the_same_moment_reads_already_scanned(
    paid_tonight, tonight, at_gate, monkeypatch
):
    at_gate(paid_tonight.code)
    # The other gate checked before the first scan was saved: it thinks it may let them in.
    monkeypatch.setattr(
        services, "_at_the_gate", lambda barcode, fixture: (Status(State.VALID), tonight)
    )
    result = at_gate(paid_tonight.code)
    assert result.status.state == State.USED
    assert result.status.reason.startswith("Already scanned at ")
    assert BarcodeScan.objects.filter(result="paid").count() == 1


def test_a_past_match_barcode_is_logged_against_its_match(
    owing, boys, make_fixture, cashier, pay, at_gate
):
    yesterday = make_fixture(owing, boys, date=timezone.localdate() - dt.timedelta(days=1))
    pay(owing, cashier, "350")
    barcode = services.Barcode.objects.create(
        club=owing.club,
        team=owing,
        mode=Barcode.Mode.MATCH,
        season=owing.season,
        fixture=yesterday,
        nonce="n",
        code="X",
    )
    barcode.code = services.signing.sign(barcode)
    Barcode.objects.filter(pk=barcode.pk).update(code=barcode.code)
    result = at_gate(barcode.code)
    assert result.status.state == State.EXPIRED
    assert BarcodeScan.objects.get().fixture == yesterday
