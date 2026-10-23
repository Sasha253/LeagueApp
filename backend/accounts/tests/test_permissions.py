"""The role permission classes every later chunk reuses, tested on stand-in views."""

import pytest
from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from accounts.models import ClubRole
from accounts.permissions import (
    ClubScopedQuerysetMixin,
    IsBookingUser,
    IsClubAdmin,
    IsClubAdminOrReferee,
    IsClubReferee,
    IsPlayer,
)
from clubs.models import Night

ADMIN = ClubRole.Role.ADMIN
REFEREE = ClubRole.Role.REFEREE
factory = APIRequestFactory()


def view_with(permission):
    class View(APIView):
        permission_classes = [permission]

        def get(self, request, **kwargs):
            return Response({"ok": True})

    return View.as_view()


def call(view, user, **kwargs):
    request = factory.get("/")
    if user:
        force_authenticate(request, user)
    return view(request, **kwargs).status_code


class NightSerializer(serializers.ModelSerializer):
    class Meta:
        model = Night
        fields = ["id", "weekday"]


class ClubNightsView(ClubScopedQuerysetMixin, generics.ListAPIView):
    queryset = Night.objects.all()
    serializer_class = NightSerializer
    permission_classes = [IsClubAdmin]


class ClubNightView(ClubScopedQuerysetMixin, generics.RetrieveUpdateAPIView):
    queryset = Night.objects.all()
    serializer_class = NightSerializer
    permission_classes = [IsClubAdmin]


@pytest.mark.django_db
class TestClubRoles:
    @pytest.mark.parametrize(
        ("permission", "role", "allowed"),
        [
            (IsClubAdmin, ADMIN, True),
            (IsClubAdmin, REFEREE, False),
            (IsClubReferee, REFEREE, True),
            (IsClubReferee, ADMIN, False),
            (IsClubAdminOrReferee, ADMIN, True),
            (IsClubAdminOrReferee, REFEREE, True),
        ],
    )
    def test_role_at_the_club_in_the_url(
        self, make_user, give_role, club_a, permission, role, allowed
    ):
        user = make_user()
        give_role(user, club_a, role)

        assert call(view_with(permission), user, club_id=club_a.id) == (200 if allowed else 403)

    @pytest.mark.parametrize("permission", [IsClubAdmin, IsClubReferee, IsClubAdminOrReferee])
    def test_a_role_at_one_club_gives_nothing_at_another(
        self, make_user, give_role, club_a, club_b, permission
    ):
        user = make_user()
        give_role(user, club_a, ADMIN)
        give_role(user, club_a, REFEREE)

        assert call(view_with(permission), user, club_id=club_b.id) == 403

    def test_without_a_club_in_the_url_needs_the_role_somewhere(self, make_user, give_role, club_a):
        admin, player = make_user("admin@example.com"), make_user("player@example.com")
        give_role(admin, club_a, ADMIN)

        assert call(view_with(IsClubAdmin), admin) == 200
        assert call(view_with(IsClubAdmin), player) == 403

    def test_signed_out_is_refused(self, club_a):
        assert call(view_with(IsClubAdmin), None, club_id=club_a.id) == 401


@pytest.mark.django_db
class TestAdminSeesOnlyTheirClub:
    @pytest.fixture
    def admin_a(self, make_user, give_role, club_a):
        admin = make_user("admin-a@example.com")
        give_role(admin, club_a, ADMIN)
        return admin

    @pytest.fixture
    def night_b(self, club_b):
        return Night.objects.create(club=club_b, weekday=Night.Weekday.FRIDAY)

    def test_list_shows_only_their_clubs_records(self, admin_a, tuesday, night_b):
        request = factory.get("/")
        force_authenticate(request, admin_a)

        response = ClubNightsView.as_view()(request)

        assert [row["id"] for row in response.data] == [tuesday.id]

    def test_cannot_read_another_clubs_record(self, admin_a, night_b):
        request = factory.get("/")
        force_authenticate(request, admin_a)

        assert ClubNightView.as_view()(request, pk=night_b.id).status_code == 404

    def test_cannot_change_another_clubs_record(self, admin_a, night_b):
        request = factory.patch("/", {"weekday": 0}, format="json")
        force_authenticate(request, admin_a)

        assert ClubNightView.as_view()(request, pk=night_b.id).status_code == 404
        night_b.refresh_from_db()
        assert night_b.weekday == Night.Weekday.FRIDAY

    def test_can_change_their_own_clubs_record(self, admin_a, tuesday):
        request = factory.patch("/", {"weekday": 0}, format="json")
        force_authenticate(request, admin_a)

        assert ClubNightView.as_view()(request, pk=tuesday.id).status_code == 200

    def test_object_check_refuses_another_clubs_record_without_scoping(self, admin_a, night_b):
        # Defence in depth: even a view that forgot to scope its queryset is refused.
        class UnscopedView(generics.RetrieveAPIView):
            queryset = Night.objects.all()
            serializer_class = NightSerializer
            permission_classes = [IsClubAdmin]

        request = factory.get("/")
        force_authenticate(request, admin_a)

        assert UnscopedView.as_view()(request, pk=night_b.id).status_code == 403


@pytest.mark.django_db
class TestAppWideRoles:
    def test_is_player(self, make_user):
        assert call(view_with(IsPlayer), make_user("p@example.com", position="both")) == 200
        assert call(view_with(IsPlayer), make_user("b@example.com", booking=True)) == 403

    def test_is_booking_user(self, make_user):
        assert call(view_with(IsBookingUser), make_user("b@example.com", booking=True)) == 200
        assert call(view_with(IsBookingUser), make_user("p@example.com", position="both")) == 403
