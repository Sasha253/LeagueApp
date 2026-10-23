import pytest

from accounts.models import ClubRole
from barcodes import signing
from barcodes.models import Barcode

pytestmark = pytest.mark.django_db


def url(team) -> str:
    return f"/api/v1/teams/{team.pk}/barcode/"


def list_url(team) -> str:
    return f"/api/v1/teams/{team.pk}/barcodes/"


def revoke_url(barcode) -> str:
    return f"/api/v1/barcodes/{barcode.pk}/revoke/"


@pytest.fixture
def paid(owing, match, cashier, pay):
    pay(owing, cashier)
    return owing


# The Captain's Barcode


def test_the_captain_sees_the_barcode(paid, match, people, signed_in):
    response = signed_in(people["thandi"]).get(url(paid))
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "valid"
    barcode = Barcode.objects.get()
    assert body["barcode"]["code"] == barcode.code
    assert body["barcode"]["display_code"] == signing.display(barcode.code)
    assert body["barcode"]["mode"] == "match"
    assert body["barcode"]["team"] == {"id": paid.pk, "name": "Red Lions"}
    assert body["barcode"]["fixture"]["id"] == match.pk
    assert body["barcode"]["fixture"]["pitch"]["name"] == "Pitch 3"
    assert body["barcode"]["valid_until"] == match.kick_off.astimezone().date().isoformat()


def test_an_unpaid_team_shows_why(owing, match, people, signed_in):
    body = signed_in(people["thandi"]).get(url(owing)).json()
    assert body == {"state": "unpaid", "reason": "Red Lions still owes R 350.", "barcode": None}


def test_a_revoked_barcode_is_not_shown(paid, people, signed_in, cashier):
    Barcode.objects.get()  # Issued on payment.
    from barcodes import services

    services.revoke(Barcode.objects.get(), by=cashier, reason="Lost phone")
    body = signed_in(people["thandi"]).get(url(paid)).json()
    assert body["state"] == "revoked"
    assert body["barcode"] is None


def test_a_player_who_isnt_captain_gets_404(paid, people, signed_in):
    assert signed_in(people["sipho"]).get(url(paid)).status_code == 404


def test_the_clubs_admin_sees_it(paid, admin_of, club_a):
    assert admin_of(club_a).get(url(paid)).json()["state"] == "valid"


def test_another_clubs_admin_and_referee_get_404(paid, admin_of, club_b, club_a, make_user):
    assert admin_of(club_b).get(url(paid)).status_code == 404


def test_a_referee_of_the_club_gets_404(paid, club_a, make_user, give_role, signed_in):
    referee = make_user("referee2@example.com", name="Ref")
    give_role(referee, club_a, ClubRole.Role.REFEREE)
    assert signed_in(referee).get(url(paid)).status_code == 404


def test_signed_out_gets_401(paid, api):
    assert api.get(url(paid)).status_code == 401


# Admins: list, issue, revoke


def test_an_admin_lists_the_teams_barcodes(paid, admin_of, club_a):
    body = admin_of(club_a).get(list_url(paid)).json()
    assert len(body) == 1
    assert body[0]["state"] == "valid"
    assert body[0]["scans"] == 0
    assert body[0]["issued_by"] is None
    assert body[0]["revoked_at"] is None


def test_an_admin_reissues(paid, admin_of, club_a):
    admin = admin_of(club_a)
    response = admin.post(list_url(paid))
    assert response.status_code == 201
    assert response.json()["issued_by"]["id"] == admin.user.pk
    states = [row["state"] for row in admin.get(list_url(paid)).json()]
    assert states == ["valid", "revoked"]


def test_issuing_for_an_unpaid_team_is_409(owing, match, admin_of, club_a):
    response = admin_of(club_a).post(list_url(owing))
    assert response.status_code == 409
    assert response.json()["detail"] == "This Team hasn't paid yet."


def test_an_admin_revokes_with_a_reason(paid, admin_of, club_a):
    admin = admin_of(club_a)
    barcode = Barcode.objects.get()
    response = admin.post(revoke_url(barcode), {"reason": "Lost phone"}, format="json")
    assert response.status_code == 200
    assert response.json()["state"] == "revoked"
    assert response.json()["revoke_reason"] == "Lost phone"
    assert response.json()["revoked_by"]["id"] == admin.user.pk
    again = admin.post(revoke_url(barcode), {"reason": "Again"}, format="json")
    assert again.status_code == 409


def test_revoking_needs_a_reason(paid, admin_of, club_a):
    response = admin_of(club_a).post(revoke_url(Barcode.objects.get()), {}, format="json")
    assert response.status_code == 400


@pytest.mark.parametrize("who", ["captain", "other_admin"])
def test_only_the_clubs_admins_manage_barcodes(who, paid, people, signed_in, admin_of, club_b):
    client = signed_in(people["thandi"]) if who == "captain" else admin_of(club_b)
    barcode = Barcode.objects.get()
    assert client.get(list_url(paid)).status_code == 404
    assert client.post(list_url(paid)).status_code == 404
    response = client.post(revoke_url(barcode), {"reason": "Mine"}, format="json")
    assert response.status_code == 404
    barcode.refresh_from_db()
    assert barcode.revoked_at is None
