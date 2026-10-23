"""Payments. `urlpatterns` go under /api/v1/, before the Teams router;
`club_urlpatterns` under /api/v1/clubs/{club_id}/."""

from django.urls import path

from . import views

urlpatterns = [
    path(
        "teams/<int:team_id>/payments/options/",
        views.PaymentOptionsView.as_view(),
        name="team-payment-options",
    ),
    path(
        "teams/<int:team_id>/payments/summary/",
        views.TeamPaymentSummaryView.as_view(),
        name="team-payment-summary",
    ),
    path("teams/<int:team_id>/payments/", views.StartPaymentView.as_view(), name="team-payments"),
    path(
        "teams/<int:team_id>/cash-payments/",
        views.CashPaymentView.as_view(),
        name="team-cash-payments",
    ),
    path("me/payments/", views.MyPaymentListView.as_view(), name="my-payments"),
    path("payments/payfast/notify/", views.PayFastNotifyView.as_view(), name="payfast-notify"),
    path("payments/<uuid:reference>/", views.PaymentDetailView.as_view(), name="payment"),
]

club_urlpatterns = [
    path("team-payments/", views.ClubTeamPaymentsView.as_view(), name="club-team-payments"),
]
