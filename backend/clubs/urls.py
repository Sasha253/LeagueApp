"""Club setup, under /api/v1/clubs/{club_id}/."""

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("seasons", views.SeasonViewSet, basename="club-seasons")
router.register("nights", views.NightViewSet, basename="club-nights")
router.register("divisions", views.DivisionViewSet, basename="club-divisions")
router.register("fields", views.FieldViewSet, basename="club-fields")
router.register("members", views.ClubMemberViewSet, basename="club-members")
router.register("invites", views.ClubInviteViewSet, basename="club-invites")

urlpatterns = [
    path("", views.ClubDetailView.as_view(), name="club-detail"),
    path("settings/", views.ClubSettingsView.as_view(), name="club-settings"),
    path("", include(router.urls)),
]
