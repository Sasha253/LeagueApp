"""Ledger. `urlpatterns` go under /api/v1/, before the Teams router."""

from django.urls import path

from . import views

urlpatterns = [
    path("me/credit/", views.MyCreditView.as_view(), name="my-credit"),
    path("teams/<int:team_id>/credit/", views.TeamCreditView.as_view(), name="team-credit"),
    path("teams/<int:team_id>/balance/", views.TeamBalanceView.as_view(), name="team-balance"),
]
