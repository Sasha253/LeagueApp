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
    path("finance/planner/", views.PlannerView.as_view(), name="club-finance-planner"),
    path("finance/outstanding/", views.OutstandingView.as_view(), name="club-finance-outstanding"),
    path(
        "finance/outstanding/remind/",
        views.RemindView.as_view(),
        name="club-finance-outstanding-remind",
    ),
    path(
        "finance/outstanding/cash/",
        views.MarkCashPaidView.as_view(),
        name="club-finance-outstanding-cash",
    ),
    path("finance/export/", views.LedgerExportView.as_view(), name="club-finance-export"),
]
