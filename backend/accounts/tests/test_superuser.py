"""A superuser sees every Club and opens each one as its Admin, without holding a ClubRole."""

import pytest
from rest_framework.test import APIClient

from accounts.models import ClubRole
from notifications.targeting import club_admins

CLUBS = "/api/v1/clubs/"
ME = "/api/v1/auth/me/"


def club_url(club, rest=""):
    return f"/api/v1/clubs/{club.pk}/{rest}"


@pytest.fixture
def root(make_user):
    user = make_user("root@example.com", booking=True, is_superuser=True, is_staff=True)
    client = APIClient()
    client.force_authenticate(user)
    client.user = user
    return client


@pytest.mark.django_db
class TestClubList:
    def test_a_superuser_sees_every_club_by_name(self, root, club_a, club_b):
        response = root.get(CLUBS)
        assert response.status_code == 200
        assert response.json() == [
            {"id": club_a.pk, "name": "Club A"},
            {"id": club_b.pk, "name": "Club B"},
        ]

    def test_an_admin_cannot_list_the_clubs(self, admin_of, club_a, club_b):
        assert admin_of(club_a).get(CLUBS).status_code == 403

    def test_signed_out_cannot_list_the_clubs(self, api):
        assert api.get(CLUBS).status_code == 401


@pytest.mark.django_db
class TestClubDetail:
    def test_names_the_club_for_its_admin(self, admin_of, club_a):
        response = admin_of(club_a).get(club_url(club_a))
        assert response.status_code == 200
        assert response.json() == {"id": club_a.pk, "name": "Club A"}

    def test_names_the_club_for_its_referee(self, make_user, give_role, club_a):
        referee = make_user("ref@example.com")
        give_role(referee, club_a, ClubRole.Role.REFEREE)
        client = APIClient()
        client.force_authenticate(referee)
        assert client.get(club_url(club_a)).status_code == 200

    def test_not_for_another_clubs_admin(self, admin_of, club_a, club_b):
        assert admin_of(club_b).get(club_url(club_a)).status_code == 403

    def test_names_any_club_for_a_superuser(self, root, club_b):
        assert root.get(club_url(club_b)).json()["name"] == "Club B"

    def test_unknown_club_is_404_for_a_superuser(self, root):
        assert root.get("/api/v1/clubs/999999/").status_code == 404


@pytest.mark.django_db
class TestOpensEveryClubAsAdmin:
    def test_reads_and_changes_any_clubs_setup(self, root, club_a, club_b):
        assert root.get(club_url(club_b, "settings/")).status_code == 200
        response = root.post(
            club_url(club_a, "seasons/"),
            {"name": "Spring 2027", "starts_on": "2027-01-10", "ends_on": "2027-04-30"},
            "json",
        )
        assert response.status_code == 201

    def test_holds_every_role_at_every_club(self, root, club_a):
        user = root.user
        assert user.is_club_admin(club_a.pk)
        assert user.holds_club_role(club_a.pk, ClubRole.Role.REFEREE)
        assert set(user.club_ids_with_role(ClubRole.Role.ADMIN).values_list("pk", flat=True)) == {
            club_a.pk
        }

    def test_an_admin_still_holds_only_their_club(self, admin_of, club_a, club_b):
        user = admin_of(club_a).user
        assert user.is_club_admin(club_a.pk)
        assert not user.is_club_admin(club_b.pk)
        assert not user.holds_club_role(club_a.pk, ClubRole.Role.REFEREE)

    def test_gets_no_clubs_admin_notifications(self, root, admin_of, club_a):
        admin = admin_of(club_a).user
        assert list(club_admins(club_a)) == [admin]

    def test_is_not_on_the_clubs_people(self, root, admin_of, club_a):
        admin = admin_of(club_a).user
        people = root.get(club_url(club_a, "members/")).json()
        assert [person["user_id"] for person in people] == [admin.pk]


@pytest.mark.django_db
class TestMe:
    def test_says_who_is_a_superuser(self, root, admin_of, club_a):
        assert root.get(ME).json()["is_superuser"] is True
        assert admin_of(club_a).get(ME).json()["is_superuser"] is False

    def test_cannot_make_itself_a_superuser(self, admin_of, club_a):
        client = admin_of(club_a)
        client.patch(ME, {"is_superuser": True}, "json")
        client.user.refresh_from_db()
        assert client.user.is_superuser is False


@pytest.mark.django_db
def test_signing_up_never_makes_a_superuser(api):
    response = api.post(
        "/api/v1/auth/register/",
        {
            "email": "new@example.com",
            "name": "Thandi Mokoena",
            "password": "floodlit-pitch-19",
            "is_booking_user": True,
            "is_superuser": True,
        },
        "json",
    )
    assert response.status_code == 201
    assert response.json()["user"]["is_superuser"] is False
