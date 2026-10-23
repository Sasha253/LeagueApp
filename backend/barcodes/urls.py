"""Payment Barcodes, under /api/v1/ before the Teams router."""

from django.urls import path

from . import views

urlpatterns = [
    path("teams/<int:team_id>/barcode/", views.CurrentBarcodeView.as_view(), name="team-barcode"),
    path("teams/<int:team_id>/barcodes/", views.TeamBarcodesView.as_view(), name="team-barcodes"),
    path(
        "barcodes/<int:barcode_id>/revoke/",
        views.RevokeBarcodeView.as_view(),
        name="barcode-revoke",
    ),
]
