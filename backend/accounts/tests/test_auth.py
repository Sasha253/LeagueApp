import pytest
from django.urls import reverse

from accounts.models import User
from conftest import PASSWORD

REGISTER = reverse("api-v1:register")
LOGIN = reverse("api-v1:login")
REFRESH = reverse("api-v1:refresh")
LOGOUT = reverse("api-v1:logout")
ME = reverse("api-v1:me")


def sign_up(api, **overrides):
    body = {
        "email": "Thandi@Example.com",
        "password": PASSWORD,
        "name": "Thandi Mokoena",
        "phone": "+27 82 123 4567",
        "is_booking_user": False,
        "player": {"position": "goalkeeper"},
        **overrides,
    }
    return api.post(REGISTER, body, format="json")


@pytest.mark.django_db
class TestRegister:
    def test_creates_a_player_and_signs_them_in(self, api):
        response = sign_up(api)

        assert response.status_code == 201
        body = response.json()
        assert body["user"]["email"] == "thandi@example.com"
        assert body["user"]["player"] == {"position": "goalkeeper", "nights": []}
        assert body["user"]["club_roles"] == []
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {body['access']}")
        assert api.get(ME).json()["name"] == "Thandi Mokoena"

    def test_a_booking_user_need_not_be_a_player(self, api):
        response = sign_up(api, player=None, is_booking_user=True)

        assert response.status_code == 201
        user = User.objects.get()
        assert user.is_booking_user and not user.is_player

    def test_needs_at_least_one_role(self, api):
        response = sign_up(api, player=None, is_booking_user=False)

        assert response.status_code == 400
        assert User.objects.count() == 0

    def test_email_is_unique_in_any_case(self, api, make_user):
        make_user("thandi@example.com")

        response = sign_up(api)

        assert response.status_code == 400
        assert "email" in response.json()

    def test_rejects_a_weak_password(self, api):
        response = sign_up(api, password="12345678")

        assert response.status_code == 400
        assert "password" in response.json()

    def test_cannot_give_itself_a_club_role(self, api, club_a):
        response = sign_up(api, club_roles=[{"club_id": club_a.id, "role": "admin"}])

        assert response.status_code == 201
        assert response.json()["user"]["club_roles"] == []

    def test_never_returns_the_password(self, api):
        assert "password" not in sign_up(api).json()["user"]


@pytest.mark.django_db
class TestLogin:
    def test_signs_in_with_email_in_any_case(self, api, make_user):
        make_user("player@example.com")

        response = api.post(LOGIN, {"email": "PLAYER@example.com", "password": PASSWORD})

        assert response.status_code == 200
        assert set(response.json()) == {"access", "refresh"}

    def test_rejects_a_wrong_password(self, api, make_user):
        make_user()

        response = api.post(LOGIN, {"email": "player@example.com", "password": "nope"})

        assert response.status_code == 401

    def test_rejects_an_inactive_account(self, api, make_user):
        make_user(is_active=False)

        response = api.post(LOGIN, {"email": "player@example.com", "password": PASSWORD})

        assert response.status_code == 401


@pytest.fixture
def tokens(api, make_user):
    make_user()
    return api.post(LOGIN, {"email": "player@example.com", "password": PASSWORD}).json()


@pytest.mark.django_db
class TestRefreshAndLogout:
    def test_refresh_gives_a_new_pair_and_retires_the_old_refresh_token(self, api, tokens):
        response = api.post(REFRESH, {"refresh": tokens["refresh"]})

        assert response.status_code == 200
        assert response.json()["refresh"] != tokens["refresh"]
        assert api.post(REFRESH, {"refresh": tokens["refresh"]}).status_code == 401

    def test_logout_stops_the_refresh_token_working(self, api, tokens):
        assert api.post(LOGOUT, {"refresh": tokens["refresh"]}).status_code == 200

        assert api.post(REFRESH, {"refresh": tokens["refresh"]}).status_code == 401

    def test_api_needs_a_token(self, api):
        assert api.get(ME).status_code == 401

    def test_api_rejects_a_bad_token(self, api):
        api.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")

        assert api.get(ME).status_code == 401

    def test_api_ignores_session_cookies(self, api, make_user):
        api.force_login(make_user())

        assert api.get(ME).status_code == 401
