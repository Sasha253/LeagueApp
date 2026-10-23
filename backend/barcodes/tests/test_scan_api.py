"""POST /api/v1/clubs/{club_id}/scans/: the gate, for the club's Admins and Referees."""

import pytest
from django.utils import timezone

from accounts.models import ClubRole
from barcodes import signing
from barcodes.models import Barcode, BarcodeScan
from fixtures.models import Fixture

pytestmark = pytest.mark.django_db


def url(club) -> str:
    return f"/api/v1/clubs/{club.pk}/scans/"


@pytest.fixture
def barcode(owing, tonight, cashier, pay):
    pay(owing, cashier)
    return Barcode.objects.get()


@pytest.fixture
def referee(make_user, give_role, club_a, signed_in):
    user = make_user("gate@example.com", name="Rita Gate")
    give_role(user, club_a, ClubRole.Role.REFEREE)
    return signed_in(user)


def test_an_admin_scans_a_paid_team(barcode, tonight, cashier, signed_in, club_a):
    response = signed_in(cashier).post(
        url(club_a), {"code": signing.display(barcode.code), "method": "camera"}, format="json"
    )
    assert response.status_code == 201
    body = response.json()
    assert body["paid"] is True
    assert body["state"] == "valid"
    assert body["reason"] == ""
    assert body["code"] == signing.display(barcode.code)
    assert body["display_code"] == signing.display(barcode.code)
    assert body["team"] == {"id": barcode.team_id, "name": "Red Lions"}
    assert body["fixture"]["id"] == tonight.pk
    assert body["fixture"]["away_team"]["name"] == "Old Boys"
    assert body["fixture"]["pitch"]["name"] == "Pitch 3"
    assert body["mode"] == "match"
    assert body["valid_until"] == timezone.localdate().isoformat()
    assert body["paid_amount"] == "350.00"
    assert body["paid_methods"] == ["cash"]
    scan = BarcodeScan.objects.get()
    assert (scan.pk, scan.scanned_by, scan.method) == (body["id"], cashier, "camera")


def test_a_referee_of_the_club_scans_and_a_reused_barcode_reads_not_paid(barcode, referee, club_a):
    first = referee.post(url(club_a), {"code": barcode.code, "method": "camera"}, format="json")
    assert first.json()["paid"] is True
    again = referee.post(url(club_a), {"code": barcode.code, "method": "manual"}, format="json")
    body = again.json()
    assert again.status_code == 201
    assert (body["paid"], body["state"]) == (False, "used")
    assert "by Rita Gate" in body["reason"]
    assert body["team"]["name"] == "Red Lions"
    assert body["paid_amount"] is None
    assert body["paid_methods"] == []


def test_an_unknown_code_answers_not_found(cashier, signed_in, club_a):
    body = (
        signed_in(cashier)
        .post(url(club_a), {"code": "AB 1234 5678", "method": "manual"}, format="json")
        .json()
    )
    assert body["paid"] is False
    assert body["state"] == "not_found"
    assert body["reason"] == "No Barcode has this code."
    assert (body["team"], body["fixture"], body["display_code"]) == (None, None, None)


def test_the_gate_can_name_the_match(barcode, tonight, cashier, signed_in, club_a):
    response = signed_in(cashier).post(
        url(club_a),
        {"code": barcode.code, "method": "camera", "fixture": tonight.pk},
        format="json",
    )
    assert response.json()["paid"] is True


def test_another_clubs_match_cannot_be_named(
    barcode, make_fixture, cashier, signed_in, club_a, club_b, lions, boys
):
    elsewhere = make_fixture(lions, boys, time="20:20")
    Fixture.objects.filter(pk=elsewhere.pk).update(club=club_b)  # Another club's match.
    response = signed_in(cashier).post(
        url(club_a),
        {"code": barcode.code, "method": "camera", "fixture": elsewhere.pk},
        format="json",
    )
    assert response.status_code == 400
    assert "fixture" in response.json()
    assert not BarcodeScan.objects.exists()


def test_a_bad_method_is_refused(cashier, signed_in, club_a):
    response = signed_in(cashier).post(url(club_a), {"code": "X", "method": "laser"}, format="json")
    assert response.status_code == 400


@pytest.mark.parametrize("who", ["captain", "player", "other_admin", "other_referee"])
def test_only_the_clubs_admins_and_referees_scan(
    who, barcode, people, signed_in, admin_of, club_a, club_b, make_user, give_role
):
    if who == "captain":
        client = signed_in(people["thandi"])
    elif who == "player":
        client = signed_in(people["lerato"])
    elif who == "other_admin":
        client = admin_of(club_b)
    else:
        user = make_user("ref-b@example.com", name="Other Ref")
        give_role(user, club_b, ClubRole.Role.REFEREE)
        client = signed_in(user)
    response = client.post(url(club_a), {"code": barcode.code, "method": "camera"}, format="json")
    assert response.status_code == 403
    assert not BarcodeScan.objects.exists()


def test_signed_out_is_refused(api, club_a):
    assert api.post(url(club_a), {"code": "X", "method": "camera"}).status_code == 401


def test_another_clubs_admin_finds_nothing_at_their_own_gate(barcode, admin_of, club_b):
    body = (
        admin_of(club_b)
        .post(url(club_b), {"code": barcode.code, "method": "camera"}, format="json")
        .json()
    )
    assert body["state"] == "not_found"
    assert body["team"] is None
    assert BarcodeScan.objects.get().club == club_b
