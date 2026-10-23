import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from barcodes import services, signing
from barcodes.models import Barcode, BarcodeScan
from barcodes.services import State
from core.exceptions import Conflict
from fixtures.models import Fixture
from ledger import services as ledger
from ledger.models import LedgerEntry
from notifications.models import Kind, Notification

pytestmark = pytest.mark.django_db


# Issued when the Team is paid (gateway mode: per match)


def test_paying_in_full_issues_a_barcode_for_the_next_match(owing, match, cashier, pay, people):
    pay(owing, cashier)
    barcode = Barcode.objects.get(team=owing)
    assert barcode.mode == Barcode.Mode.MATCH
    assert barcode.fixture == match
    assert barcode.season == owing.season
    assert barcode.issued_by is None
    assert signing.is_signed(barcode)
    told = Notification.objects.get(recipient=people["thandi"])
    assert told.kind == Kind.UPDATE
    assert told.title == "Payment Barcode for Red Lions"
    assert "Valid for your match on" in told.body


def test_paying_part_issues_nothing(owing, match, cashier, pay):
    pay(owing, cashier, "100")
    assert not Barcode.objects.exists()


def test_a_card_payment_issues_it_too(owing, match, people):
    """As the confirmed ITN records it (payments.services._apply)."""
    from payments import services as payments

    entry = payments.paying(
        owing,
        lambda: ledger.record_payment(
            team=owing,
            amount=Decimal("350"),
            method=LedgerEntry.Method.CARD,
            recorded_by=None,
            player=people["sipho"],
            reason="Card payment",
            money_taken=True,
        ),
    )
    assert entry.method == LedgerEntry.Method.CARD
    assert Barcode.objects.filter(team=owing, fixture=match).count() == 1


def test_paid_with_no_match_yet_issues_on_first_look(owing, cashier, pay, make_fixture, boys):
    pay(owing, cashier)
    assert not Barcode.objects.exists()
    assert services.current_for(owing).status.state == State.NO_MATCH

    match = make_fixture(owing, boys)
    current = services.current_for(owing)
    assert current.status.valid
    assert current.barcode.fixture == match
    assert services.current_for(owing).barcode == current.barcode  # Not issued twice.


def test_the_next_match_gets_its_own_barcode(owing, match, cashier, pay, make_fixture, boys):
    pay(owing, cashier)
    first = services.current_for(owing).barcode
    later = make_fixture(owing, boys, date=match.kick_off.date() + dt.timedelta(days=7))
    Fixture.objects.filter(pk=match.pk).update(status=Fixture.Status.PLAYED)

    second = services.current_for(owing).barcode
    assert second.fixture == later
    assert second.code != first.code
    assert services.status_of(Barcode.objects.get(pk=first.pk)).state == State.EXPIRED


def test_a_cancelled_match_skips_to_the_next(owing, match, cashier, pay, make_fixture, boys):
    pay(owing, cashier)
    later = make_fixture(owing, boys, date=match.kick_off.date() + dt.timedelta(days=7))
    Fixture.objects.filter(pk=match.pk).update(status=Fixture.Status.CANCELLED)
    assert services.current_for(owing).barcode.fixture == later


def test_a_past_match_is_not_the_current_one(owing, cashier, pay, make_fixture, boys):
    make_fixture(owing, boys, date=timezone.localdate() - dt.timedelta(days=1))
    pay(owing, cashier)
    assert services.current_for(owing).status.state == State.NO_MATCH


def test_tonights_match_is_current_after_kick_off(owing, cashier, pay, make_fixture, boys):
    tonight = make_fixture(owing, boys, date=timezone.localdate(), time="00:01")
    pay(owing, cashier)
    current = services.current_for(owing)
    assert current.status.valid
    assert current.barcode.fixture == tonight


def test_an_unpaid_team_has_no_barcode(owing, match):
    current = services.current_for(owing)
    assert current.barcode is None
    assert current.status == services.Status(State.UNPAID, "Red Lions still owes R 350.")
    assert not Barcode.objects.exists()


def test_a_barcode_stops_counting_when_the_payment_is_reversed(owing, match, cashier, pay):
    entry = pay(owing, cashier)
    barcode = Barcode.objects.get()
    ledger.reverse(entry, reason="Counted twice", recorded_by=cashier)

    assert services.status_of(barcode).state == State.UNPAID
    current = services.current_for(owing)
    assert current.barcode is None
    assert current.status.state == State.UNPAID


def test_paying_again_after_a_reversal_keeps_the_same_barcode(owing, match, cashier, pay):
    entry = pay(owing, cashier)
    ledger.reverse(entry, reason="Counted twice", recorded_by=cashier)
    pay(owing, cashier)
    assert Barcode.objects.count() == 1
    assert services.current_for(owing).status.valid


# Cash-only mode: valid for the rest of the Season


def test_cash_only_issues_a_season_barcode(cash_only, owing, cashier, pay, people):
    pay(owing, cashier)
    barcode = Barcode.objects.get()
    assert barcode.mode == Barcode.Mode.SEASON
    assert barcode.fixture is None
    assert services.current_for(owing).barcode == barcode
    body = Notification.objects.get(recipient=people["thandi"]).body
    assert f"Valid until {owing.season.ends_on:%a} {owing.season.ends_on.day}" in body


def test_a_season_barcode_lasts_across_matches(cash_only, owing, match, cashier, pay):
    pay(owing, cashier)
    Fixture.objects.filter(pk=match.pk).update(status=Fixture.Status.PLAYED)
    assert services.current_for(owing).barcode.mode == Barcode.Mode.SEASON
    assert Barcode.objects.count() == 1


def test_a_season_barcode_ends_with_its_season(cash_only, owing, cashier, pay):
    pay(owing, cashier)
    season = owing.season
    season.ends_on = timezone.localdate() - dt.timedelta(days=1)
    season.save()
    barcode = Barcode.objects.get()
    assert services.status_of(barcode) == services.Status(
        State.EXPIRED, "The Spring Season has ended."
    )
    assert services.current_for(owing).barcode is None


# Revoking and reissuing


def test_a_revoked_barcode_is_not_issued_again_by_itself(owing, match, cashier, pay):
    pay(owing, cashier)
    barcode = Barcode.objects.get()
    services.revoke(barcode, by=cashier, reason="Shared on WhatsApp")

    current = services.current_for(owing)
    assert current.barcode is None
    assert current.status == services.Status(
        State.REVOKED, "This Barcode was revoked: Shared on WhatsApp"
    )
    assert Barcode.objects.count() == 1


def test_revoking_twice_is_refused(owing, match, cashier, pay):
    pay(owing, cashier)
    barcode = Barcode.objects.get()
    services.revoke(barcode, by=cashier, reason="Lost phone")
    with pytest.raises(Conflict):
        services.revoke(barcode, by=cashier, reason="Again")


def test_an_admin_reissues_and_the_old_one_is_revoked(owing, match, cashier, pay, people):
    pay(owing, cashier)
    old = Barcode.objects.get()
    new = services.issue(owing, by=cashier)

    old.refresh_from_db()
    assert old.revoked_at is not None
    assert old.revoke_reason == "Reissued by an Admin."
    assert services.status_of(old).state == State.REVOKED
    assert new.issued_by == cashier
    assert new.code != old.code
    assert services.current_for(owing).barcode == new
    assert Notification.objects.filter(recipient=people["thandi"]).count() == 2


def test_an_admin_reissues_after_a_revocation(owing, match, cashier, pay):
    pay(owing, cashier)
    services.revoke(Barcode.objects.get(), by=cashier, reason="Lost phone")
    new = services.issue(owing, by=cashier)
    assert services.current_for(owing).barcode == new


@pytest.mark.parametrize("state", ["unpaid", "no_match"])
def test_an_admin_cant_issue_one_without_payment_or_match(state, owing, cashier, pay, request):
    if state == "unpaid":
        request.getfixturevalue("match")
    else:
        pay(owing, cashier)
    with pytest.raises(Conflict):
        services.issue(owing, by=cashier)


def test_a_barcode_is_never_deleted(owing, match, cashier, pay):
    pay(owing, cashier)
    barcode = Barcode.objects.get()
    with pytest.raises(ValueError):
        barcode.delete()
    with pytest.raises(ValueError):
        Barcode.objects.all().delete()


# Integrity


def test_a_barcode_moved_to_another_team_is_not_genuine(owing, match, cashier, pay, boys):
    pay(owing, cashier)
    Barcode.objects.update(team=boys)
    assert services.status_of(Barcode.objects.get()).state == State.NOT_GENUINE


def test_a_barcode_written_without_the_key_is_not_genuine(owing, match, cashier, pay):
    pay(owing, cashier)
    Barcode.objects.update(code="ABCDEFGH12")
    assert services.status_of(Barcode.objects.get()).state == State.NOT_GENUINE


def test_codes_are_unique_and_retried(owing, match, cashier, pay, monkeypatch, make_fixture):
    pay(owing, cashier)
    taken = Barcode.objects.get().code
    codes = iter([taken, "ZZZZZZZZZZ"])
    monkeypatch.setattr(signing, "sign", lambda barcode: next(codes))
    new = services.issue(owing, by=cashier)
    assert new.code == "ZZZZZZZZZZ"


# Scanning: every scan is logged


def test_a_valid_scan_reads_paid(owing, match, cashier, pay, club_a):
    pay(owing, cashier)
    barcode = Barcode.objects.get()
    result = services.scan(
        signing.display(barcode.code).lower(), club=club_a, by=cashier, method="manual"
    )
    assert result.paid
    assert result.barcode == barcode
    scan = BarcodeScan.objects.get()
    assert (scan.result, scan.barcode, scan.method) == ("paid", barcode, "manual")


def test_an_unknown_code_reads_not_paid_and_is_logged(club_a, cashier):
    result = services.scan("NOT A CODE", club=club_a, by=cashier, method="camera")
    assert not result.paid
    assert result.status.state == State.NOT_FOUND
    scan = BarcodeScan.objects.get()
    assert (scan.code, scan.barcode, scan.result) == ("NOT A CODE", None, "not_paid")


def test_another_clubs_barcode_is_not_found(owing, match, cashier, pay, club_b, make_user):
    pay(owing, cashier)
    result = services.scan(Barcode.objects.get().code, club=club_b, by=cashier, method="camera")
    assert result.status.state == State.NOT_FOUND
    assert BarcodeScan.objects.get().club == club_b


def test_a_revoked_barcode_reads_not_paid(owing, match, cashier, pay, club_a):
    pay(owing, cashier)
    barcode = Barcode.objects.get()
    services.revoke(barcode, by=cashier, reason="Lost phone")
    result = services.scan(barcode.code, club=club_a, by=cashier, method="camera")
    assert result.status.state == State.REVOKED
    assert BarcodeScan.objects.get().reason == "This Barcode was revoked: Lost phone"


def test_a_scan_is_never_changed_or_deleted(club_a, cashier):
    services.scan("X", club=club_a, by=cashier, method="camera")
    scan = BarcodeScan.objects.get()
    with pytest.raises(ValueError):
        scan.save()
    with pytest.raises(ValueError):
        scan.delete()
    with pytest.raises(ValueError):
        BarcodeScan.objects.update(reason="")
    with pytest.raises(ValueError):
        BarcodeScan.objects.all().delete()
