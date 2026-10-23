from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from clubs.views import NightListView
from core.views import HealthView

api_v1 = [
    path("health/", HealthView.as_view(), name="health"),
    path("auth/", include("accounts.urls")),
    path("nights/", NightListView.as_view(), name="nights"),
    path("clubs/<int:club_id>/", include("clubs.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api-v1:schema"), name="docs"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1, "api-v1"))),
]
