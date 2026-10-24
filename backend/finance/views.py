"""The finance tracker API (FR-25 to FR-27, FR-47 to FR-49). Admins of the Club only.

The accountant export (FR-51) sends a Club's ledger entries for a period as CSV or Excel.

Read-only except the Outstanding list's actions (FR-48): Remind sends a notification and
Mark cash paid adds a cash ledger entry through payments.services.record_cash.

Every figure is computed from the ledger by finance.services. Another Club's Season,
Night, Division or Team is 404, so its existence doesn't show.
"""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsClubAdmin
from clubs.models import Club, Division, Night, Season
from ledger import services as ledger
from ledger.serializers import LedgerEntrySerializer
from teams.models import Team

from . import export, outstanding, planner, services
from .serializers import (
    ExportQuerySerializer,
    MarkCashPaidSerializer,
    OutstandingRowSerializer,
    OutstandingSerializer,
    PlannerSerializer,
    RemindedSerializer,
    SeasonIncomeSerializer,
    SeasonSummarySerializer,
    TeamLedgerSerializer,
)


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


SCOPE = [
    OpenApiParameter("season", int, required=True, description="The Season."),
    OpenApiParameter("night", int, description="Only this Night."),
    OpenApiParameter("division", int, description="Only this Division."),
]


def scope(request, club_id: int):
    """The Club, and the Season, Night and Division asked for, all of that Club (else 404)."""
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
    return club, season, night, division


class SeasonSummaryView(APIView):
    """A Season's totals per Night and Division, with friendly and booking income as their
    own lines (FR-25, FR-49)."""

    permission_classes = [IsClubAdmin]

    @extend_schema(parameters=SCOPE, responses=SeasonSummarySerializer)
    def get(self, request, club_id: int):
        club, season, night, division = scope(request, club_id)
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


class PlannerView(APIView):
    """Expected league income week by week, from the fixture list, with what Teams have
    paid overlaid (FR-47)."""

    permission_classes = [IsClubAdmin]

    @extend_schema(parameters=SCOPE, responses=PlannerSerializer)
    def get(self, request, club_id: int):
        club, season, night, division = scope(request, club_id)
        plan = planner.planner(club, season, night=night, division=division)
        return Response(PlannerSerializer(plan).data)


class OutstandingView(APIView):
    """Teams and Players who owe, largest first (FR-48)."""

    permission_classes = [IsClubAdmin]

    @extend_schema(parameters=SCOPE, responses=OutstandingSerializer)
    def get(self, request, club_id: int):
        club, season, night, division = scope(request, club_id)
        owed = outstanding.outstanding(club, season, night=night, division=division)
        return Response(OutstandingSerializer(owed).data)


def row(club_id: int, data: dict):
    """The Team (of this Club, else 404) and the Player (a current one, else 400)."""
    team = get_object_or_404(
        Team.objects.select_related("club", "season", "division__night"),
        club_id=club_id,
        pk=data["team_id"],
    )
    player = None
    if data.get("player_id") is not None:
        player = outstanding.is_current_player(team, data["player_id"])
        if player is None:
            raise ValidationError({"player_id": "That Player isn't in this Team."})
    return team, player


class RemindView(APIView):
    """Remind a Team or a Player on the Outstanding list (FR-48): an Update notification,
    only to those opted into the Team's Night."""

    permission_classes = [IsClubAdmin]

    @extend_schema(request=OutstandingRowSerializer, responses=RemindedSerializer)
    def post(self, request, club_id: int):
        body = OutstandingRowSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        team, player = row(club_id, body.validated_data)
        reminded = outstanding.remind(team=team, player=player)
        return Response(RemindedSerializer(reminded).data)


class MarkCashPaidView(APIView):
    """Mark cash paid on the Outstanding list (FR-48, FR-22): what the row owes, as a cash
    ledger entry. Refused (409) if what is owed has changed since it was shown."""

    permission_classes = [IsClubAdmin]

    @extend_schema(request=MarkCashPaidSerializer, responses={201: LedgerEntrySerializer})
    def post(self, request, club_id: int):
        body = MarkCashPaidSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        team, player = row(club_id, body.validated_data)
        entry = outstanding.mark_cash_paid(
            team=team, admin=request.user, amount=body.validated_data["amount"], player=player
        )
        return Response(LedgerEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class LedgerExportView(APIView):
    """Every ledger entry the Club recorded in a period, for its accountant (FR-51): an
    Excel or CSV file, one row per entry, oldest first."""

    permission_classes = [IsClubAdmin]

    @extend_schema(
        summary="Export ledger entries for the club's accountant",
        parameters=[ExportQuerySerializer],
        responses={
            (200, export.XLSX): OpenApiResponse(OpenApiTypes.BINARY),
            (200, "text/csv"): OpenApiResponse(OpenApiTypes.BINARY),
        },
    )
    def get(self, request, club_id: int):
        club = get_object_or_404(Club, pk=club_id)
        query = ExportQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        period = export.Period(query.validated_data["starts_on"], query.validated_data["ends_on"])
        body, content_type, name = export.export(club, period, query.validated_data["file_type"])
        response = HttpResponse(body, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{name}"'
        response["Cache-Control"] = "no-store"
        return response
