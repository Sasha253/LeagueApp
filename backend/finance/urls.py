"""Finance tracker, under /api/v1/clubs/{club_id}/."""

from django.urls import path

from . import views

club_urlpatterns = [
    path("finance/summary/", views.SeasonSummaryView.as_view(), name="club-finance-summary"),
    path(
        "finance/comparison/",
        views.IncomeComparisonView.as_view(),
        name="club-finance-comparison",
    ),
    path(
        "finance/teams/<int:team_id>/",
        views.TeamLedgerView.as_view(),
        name="club-finance-team-ledger",
    ),
]
