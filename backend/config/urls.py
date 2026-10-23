from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from clubs.views import NightListView
from core.views import HealthView
from fixtures.urls import club_urlpatterns as club_fixture_urls
from teams.urls import club_urlpatterns as club_team_urls

api_v1 = [
    path("health/", HealthView.as_view(), name="health"),
    path("auth/", include("accounts.urls")),
    path("nights/", NightListView.as_view(), name="nights"),
    path("clubs/<int:club_id>/", include("clubs.urls")),
    path("clubs/<int:club_id>/", include(club_team_urls)),
    path("clubs/<int:club_id>/", include(club_fixture_urls)),
    path("", include("ledger.urls")),
    path("", include("notifications.urls")),
    path("", include("fixtures.urls")),
    path("", include("teams.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api-v1:schema"), name="docs"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1, "api-v1"))),
]
