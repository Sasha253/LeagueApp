"""Test users: one per role at a Club, with no password; only a superuser signs in as them."""

import pytest
from django.core.management import CommandError, call_command
from rest_framework.test import APIClient

from accounts.models import ClubRole, User
from accounts.testers import make_test_users
from clubs.models import Night

LOGIN = "/api/v1/auth/login/"
ME = "/api/v1/auth/me/"
TESTERS = "/api/v1/auth/test-users/"


def login_url(user):
    return f"{TESTERS}{user.pk}/login/"


@pytest.fixture
def root(make_user):
    user = make_user("root@example.com", booking=True, is_superuser=True, is_staff=True)
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def testers(club_a, tuesday):
    return {user.email.split(".")[0]: user for user in make_test_users(club_a)}


@pytest.mark.django_db
class TestMakeTestUsers:
    def test_one_user_per_role_at_the_club(self, club_a, testers):
        assert set(testers) == {"admin", "referee", "player", "keeper", "booker"}
        assert all(user.is_test_account for user in testers.values())
        assert testers["admin"].is_club_admin(club_a.pk)
        assert testers["referee"].holds_club_role(club_a.pk, ClubRole.Role.REFEREE)
        assert not testers["referee"].is_club_admin(club_a.pk)
        assert testers["player"].player_profile.plays_outfield
        assert not testers["player"].player_profile.plays_goalkeeper
        assert testers["keeper"].player_profile.plays_goalkeeper
        assert testers["booker"].is_booking_user and not testers["booker"].is_player

    def test_the_players_opt_into_the_clubs_nights(self, testers, tuesday):
        assert list(testers["player"].player_profile.nights.all()) == [tuesday]
        assert list(testers["keeper"].player_profile.nights.all()) == [tuesday]

    def test_no_usable_password(self, testers):
        assert not any(user.has_usable_password() for user in testers.values())

    def test_running_again_adds_no_users_and_opts_into_new_nights(self, club_a, testers):
        friday = Night.objects.create(club=club_a, weekday=Night.Weekday.FRIDAY)
        make_test_users(club_a)
        assert User.objects.filter(is_test_account=True).count() == 5
        assert friday in testers["player"].player_profile.nights.all()
        assert ClubRole.objects.filter(user=testers["admin"]).count() == 1

    def test_each_club_has_its_own(self, club_a, club_b):
        make_test_users(club_a)
        make_test_users(club_b)
        assert User.objects.filter(is_test_account=True).count() == 10
        admin_b = User.objects.get(email=f"admin.club{club_b.pk}@test.invalid")
        assert admin_b.is_club_admin(club_b.pk)
        assert not admin_b.is_club_admin(club_a.pk)

    def test_the_command_names_existing_clubs(self, club_a, capsys):
        call_command("make_test_users", "Club A")
        assert f"admin.club{club_a.pk}@test.invalid" in capsys.readouterr().out
        assert User.objects.filter(is_test_account=True).count() == 5

    def test_the_command_refuses_a_missing_club(self, club_a):
        with pytest.raises(CommandError, match="No club named: Nowhere FC"):
            call_command("make_test_users", "Club A", "Nowhere FC")
        assert not User.objects.filter(is_test_account=True).exists()


@pytest.mark.django_db
class TestNoPasswordLogin:
    def test_the_login_form_refuses_a_test_user(self, api, testers):
        response = api.post(LOGIN, {"email": testers["admin"].email, "password": ""})
        assert response.status_code in (400, 401)
        assert "access" not in response.json()


@pytest.mark.django_db
class TestList:
    def test_a_superuser_sees_the_test_users_and_their_roles(self, root, testers, make_user):
        make_user("real@example.com", position="outfield")
        response = root.get(TESTERS)
        assert response.status_code == 200
        by_email = {row["email"]: row for row in response.json()}
        assert set(by_email) == {user.email for user in testers.values()}
        assert by_email[testers["admin"].email] == {
            "id": testers["admin"].pk,
            "name": "Test Admin (Club A)",
            "email": testers["admin"].email,
            "roles": ["Admin at Club A"],
        }
        assert by_email[testers["keeper"].email]["roles"] == ["Player (goalkeeper)"]
        assert by_email[testers["booker"].email]["roles"] == ["Booking User"]

    def test_not_an_admin(self, admin_of, club_a, testers):
        assert admin_of(club_a).get(TESTERS).status_code == 403

    def test_not_a_test_user(self, testers):
        client = APIClient()
        client.force_authenticate(testers["admin"])
        assert client.get(TESTERS).status_code == 403


@pytest.mark.django_db
class TestLoginAs:
    def test_a_superuser_gets_the_test_users_tokens(self, root, testers):
        response = root.post(login_url(testers["referee"]))
        assert response.status_code == 200
        body = response.json()
        assert body["user"]["email"] == testers["referee"].email
        assert body["user"]["is_test_account"] is True

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {body['access']}")
        me = client.get(ME).json()
        assert me["email"] == testers["referee"].email
        assert me["club_roles"] == [
            {
                "club_id": testers["referee"].club_roles.get().club_id,
                "club_name": "Club A",
                "role": "referee",
            }
        ]
        assert client.post("/api/v1/auth/refresh/", {"refresh": body["refresh"]}).status_code == 200

    def test_not_a_real_user(self, root, make_user):
        real = make_user("real@example.com", position="outfield")
        assert root.post(login_url(real)).status_code == 404

    def test_not_a_superuser_even_if_marked_test(self, root, make_user):
        other = make_user("other-root@example.com", is_superuser=True, is_test_account=True)
        assert root.post(login_url(other)).status_code == 404

    def test_not_an_inactive_test_user(self, root, testers):
        testers["player"].is_active = False
        testers["player"].save()
        assert root.post(login_url(testers["player"])).status_code == 404

    def test_not_for_an_admin(self, admin_of, club_a, testers):
        assert admin_of(club_a).post(login_url(testers["player"])).status_code == 403

    def test_signed_out(self, api, testers):
        assert api.post(login_url(testers["player"])).status_code == 401

    def test_me_is_not_a_test_account_for_real_users(self, admin_of, club_a):
        assert admin_of(club_a).get(ME).json()["is_test_account"] is False
