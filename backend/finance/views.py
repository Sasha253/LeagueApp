"""The finance tracker API (FR-25 to FR-27, FR-49). Admins of the Club only; read-only.

Every figure is computed from the ledger by finance.services. Another Club's Season,
Night, Division or Team is 404, so its existence doesn't show.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsClubAdmin
from clubs.models import Club, Division, Night, Season
from ledger import services as ledger
from teams.models import Team

from . import services
from .serializers import SeasonIncomeSerializer, SeasonSummarySerializer, TeamLedgerSerializer


def _is_id(value: str) -> bool:
    """ASCII digits only: str.isdigit() also accepts "²", which int() refuses."""
    return value.isascii() and value.isdigit()


def _id(request, name: str, *, required: bool = False) -> int | None:
    value = request.query_params.get(name, "")
    if not value:
        if required:
            raise ValidationError({name: "Required."})
        return None
    if not _is_id(value):
        raise ValidationError({name: "An id."})
    return int(value)


class SeasonSummaryView(APIView):
    """A Season's totals per Night and Division, with friendly and booking income as their
    own lines (FR-25, FR-49)."""

    permission_classes = [IsClubAdmin]

    @extend_schema(
        parameters=[
            OpenApiParameter("season", int, required=True, description="The Season."),
            OpenApiParameter("night", int, description="Only this Night."),
            OpenApiParameter("division", int, description="Only this Division."),
        ],
        responses=SeasonSummarySerializer,
    )
    def get(self, request, club_id: int):
        club = get_object_or_404(Club, pk=club_id)
        season = get_object_or_404(Season, club=club, pk=_id(request, "season", required=True))
        night_id = _id(request, "night")
        division_id = _id(request, "division")
        night = get_object_or_404(Night, club=club, pk=night_id) if night_id else None
        division = (
            get_object_or_404(Division, night__club=club, pk=division_id) if division_id else None
        )
        if night and division and division.night_id != night.pk:
            raise ValidationError({"division": "That Division isn't on this Night."})
        summary = services.season_summary(club, season, night=night, division=division)
        return Response(SeasonSummarySerializer(summary).data)


class IncomeComparisonView(APIView):
    """Income per Season and Night, side by side (FR-27). Oldest Season first."""

    permission_classes = [IsClubAdmin]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "seasons",
                str,
                description="Comma-separated Season ids. Empty: every Season of the Club.",
            ),
        ],
        responses=SeasonIncomeSerializer(many=True),
    )
    def get(self, request, club_id: int):
        club = get_object_or_404(Club, pk=club_id)
        seasons = Season.objects.filter(club=club).order_by("starts_on", "pk")
        wanted = request.query_params.get("seasons", "").strip()
        if wanted:
            ids = [part.strip() for part in wanted.split(",")]
            if not all(_is_id(part) for part in ids):
                raise ValidationError({"seasons": "Comma-separated Season ids."})
            ids = {int(part) for part in ids}
            seasons = seasons.filter(pk__in=ids)
            if len(seasons) != len(ids):
                raise ValidationError({"seasons": "A Season of this Club is not found."})
        summaries = services.comparison(club, list(seasons))
        return Response(SeasonIncomeSerializer(summaries, many=True).data)


class TeamLedgerView(APIView):
    """A Team's ledger for its Club's Admins (FR-26): what it owes, has paid and still
    owes, and every line on its account, newest first."""

    permission_classes = [IsClubAdmin]

    @extend_schema(responses=TeamLedgerSerializer)
    def get(self, request, club_id: int, team_id: int):
        team = get_object_or_404(
            Team.objects.select_related("season", "division__night"), club_id=club_id, pk=team_id
        )
        balance = ledger.team_balance(team)
        entries = (
            ledger.account_entries(team)
            .select_related("user", "team", "recorded_by")
            .order_by("-created_at", "-pk")
        )
        data = {
            "team": team,
            "season": team.season,
            "division": team.division,
            "night": team.division.night,
            "due": balance.due,
            "paid": balance.paid,
            "outstanding": balance.outstanding,
            "paid_by_method": balance.paid_by_method,
            "is_paid": balance.is_paid,
            "team_credit_held": ledger.team_credit(team),
            "entries": entries,
        }
        return Response(TeamLedgerSerializer(data).data)
