"""Teams. `urlpatterns` go under /api/v1/; `club_urlpatterns` under /api/v1/clubs/{club_id}/."""

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("teams", views.TeamViewSet, basename="teams")
router.register("join-requests", views.JoinRequestViewSet, basename="join-requests")

urlpatterns = [
    path("seasons/", views.SeasonOptionListView.as_view(), name="seasons"),
    path(
        "seasons/<int:season_id>/divisions/",
        views.DivisionOptionListView.as_view(),
        name="season-divisions",
    ),
    path("me/teams/", views.MyTeamListView.as_view(), name="my-teams"),
    path("me/join-requests/", views.MyJoinRequestListView.as_view(), name="my-join-requests"),
    path("", include(router.urls)),
]

club_router = SimpleRouter()
club_router.register("teams", views.ClubTeamViewSet, basename="club-teams")

club_urlpatterns = club_router.urls
