import pytest
from django.urls import reverse

from accounts.models import ClubRole
from clubs.models import Night

ME = reverse("api-v1:me")


@pytest.fixture
def player(make_user):
    return make_user(position="outfield")


@pytest.fixture
def signed_in(api, player):
    api.force_authenticate(player)
    return api


@pytest.mark.django_db
class TestMe:
    def test_shows_roles_held_at_each_club(self, signed_in, player, club_a, club_b, give_role):
        give_role(player, club_a, ClubRole.Role.ADMIN)
        give_role(player, club_b, ClubRole.Role.REFEREE)

        body = signed_in.get(ME).json()

        assert body["club_roles"] == [
            {"club_id": club_a.id, "club_name": "Club A", "role": "admin"},
            {"club_id": club_b.id, "club_name": "Club B", "role": "referee"},
        ]

    def test_updates_position_and_nights_at_any_club(self, signed_in, player, tuesday, club_b):
        friday_b = Night.objects.create(club=club_b, weekday=Night.Weekday.FRIDAY)

        response = signed_in.patch(
            ME, {"player": {"position": "both", "nights": [tuesday.id, friday_b.id]}}, "json"
        )

        assert response.status_code == 200
        player.player_profile.refresh_from_db()
        assert player.player_profile.position == "both"
        assert set(player.player_profile.nights.all()) == {tuesday, friday_b}

    def test_rejects_an_unknown_night(self, signed_in):
        response = signed_in.patch(ME, {"player": {"position": "both", "nights": [999]}}, "json")

        assert response.status_code == 400

    def test_updates_name_and_phone_but_not_email(self, signed_in, player):
        signed_in.patch(ME, {"name": "S. Dlamini", "phone": "0821234567", "email": "x@y.za"})

        player.refresh_from_db()
        assert (player.name, player.phone, player.email) == (
            "S. Dlamini",
            "0821234567",
            "player@example.com",
        )

    def test_cannot_grant_itself_a_club_role(self, signed_in, player, club_a):
        signed_in.patch(ME, {"club_roles": [{"club_id": club_a.id, "role": "admin"}]}, "json")

        assert not player.club_roles.exists()

    def test_a_booking_user_can_become_a_player(self, api, make_user):
        user = make_user("hirer@example.com", booking=True)
        api.force_authenticate(user)

        response = api.patch(ME, {"player": {"position": "goalkeeper"}}, "json")

        assert response.status_code == 200
        assert response.json()["player"] == {"position": "goalkeeper", "nights": []}

    def test_a_player_who_books_can_stop_being_a_player(self, signed_in, player):
        response = signed_in.patch(ME, {"is_booking_user": True, "player": None}, "json")

        assert response.status_code == 200
        assert response.json()["player"] is None

    def test_cannot_drop_every_role(self, signed_in, player):
        response = signed_in.patch(ME, {"player": None}, "json")

        assert response.status_code == 400
        assert player.is_player

    def test_no_delete_or_put(self, signed_in):
        assert signed_in.delete(ME).status_code == 405
        assert signed_in.put(ME, {}).status_code == 405
