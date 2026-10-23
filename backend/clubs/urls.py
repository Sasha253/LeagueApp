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
    path("settings/", views.ClubSettingsView.as_view(), name="club-settings"),
    path(
        "imports/nights-divisions/preview/",
        views.NightDivisionImportPreviewView.as_view(),
        name="club-import-nights-preview",
    ),
    path(
        "imports/nights-divisions/commit/",
        views.NightDivisionImportCommitView.as_view(),
        name="club-import-nights-commit",
    ),
    path(
        "imports/nights-divisions/template/",
        views.NightDivisionImportTemplateView.as_view(),
        name="club-import-nights-template",
    ),
    path("", include(router.urls)),
]
