"""Fixtures. `urlpatterns` go under /api/v1/; `club_urlpatterns` under /api/v1/clubs/{club_id}/."""

from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("fixtures", views.FixtureViewSet, basename="fixtures")
router.register("captain-requests", views.CaptainRequestViewSet, basename="captain-requests")

urlpatterns = [
    path("me/fixtures/", views.MyFixtureListView.as_view(), name="my-fixtures"),
    *router.urls,
]

club_router = SimpleRouter()
club_router.register("fixtures", views.ClubFixtureViewSet, basename="club-fixtures")
club_router.register(
    "captain-requests", views.ClubCaptainRequestViewSet, basename="club-captain-requests"
)

club_urlpatterns = [
    path(
        "imports/fixtures/preview/",
        views.FixtureImportPreviewView.as_view(),
        name="club-import-fixtures-preview",
    ),
    path(
        "imports/fixtures/commit/",
        views.FixtureImportCommitView.as_view(),
        name="club-import-fixtures-commit",
    ),
    path(
        "imports/fixtures/template/",
        views.FixtureImportTemplateView.as_view(),
        name="club-import-fixtures-template",
    ),
    path("tonight/", views.TonightView.as_view(), name="club-tonight"),
    path(
        "readiness/<int:pk>/decide/",
        views.ReadinessDecisionView.as_view(),
        name="club-readiness-decide",
    ),
    *club_router.urls,
]
