"""Payment Barcodes API.

- The Team's Captain sees its Barcode now, or why there is none. The club's Admins can too.
- Admins of the Team's Club see all its Barcodes, issue or reissue one (only for a paid
  Team), and revoke one with a reason.
- Anyone else gets 404, so a Team's Barcodes don't show that they exist.
"""

from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import ClubRole
from teams.models import Team

from . import services
from .models import Barcode
from .serializers import (
    AdminBarcodeSerializer,
    CurrentBarcodeSerializer,
    RevokeBarcodeSerializer,
)


def _is_admin(user, club_id: int) -> bool:
    return user.club_roles.filter(club_id=club_id, role=ClubRole.Role.ADMIN).exists()


def _team(team_id: int) -> Team:
    return get_object_or_404(Team.objects.select_related("club__settings", "season"), pk=team_id)


def _admin_team(request, team_id: int) -> Team:
    team = _team(team_id)
    if not _is_admin(request.user, team.club_id):
        raise NotFound()
    return team


def _barcodes(team: Team):
    return (
        Barcode.objects.filter(team=team)
        .select_related(
            "team",
            "season",
            "fixture__home_team",
            "fixture__away_team",
            "fixture__pitch",
            "issued_by",
            "revoked_by",
        )
        .annotate(scan_count=Count("scans"))
        .order_by("-issued_at", "-pk")  # Meta.ordering isn't applied with GROUP BY.
    )


class CurrentBarcodeView(APIView):
    """The Captain's Payment Barcode for the gate now, or why there is none. Opening it
    issues the Barcode for a paid Team's next match if it has none yet."""

    @extend_schema(responses=CurrentBarcodeSerializer)
    def get(self, request, team_id: int):
        team = _team(team_id)
        is_captain = team.captain_id == request.user.pk
        if not (is_captain or _is_admin(request.user, team.club_id)):
            raise NotFound()
        current = services.current_for(team)
        data = {
            "state": current.status.state,
            "reason": current.status.reason,
            "barcode": current.barcode,
        }
        return Response(CurrentBarcodeSerializer(data).data)


class TeamBarcodesView(APIView):
    """An Admin of the Team's Club: its Barcodes, newest first, and issuing a new one."""

    @extend_schema(responses=AdminBarcodeSerializer(many=True))
    def get(self, request, team_id: int):
        team = _admin_team(request, team_id)
        return Response(AdminBarcodeSerializer(_barcodes(team), many=True).data)

    @extend_schema(request=None, responses={201: AdminBarcodeSerializer})
    def post(self, request, team_id: int):
        team = _admin_team(request, team_id)
        barcode = services.issue(team, by=request.user)
        barcode = _barcodes(team).get(pk=barcode.pk)
        return Response(AdminBarcodeSerializer(barcode).data, status=status.HTTP_201_CREATED)


class RevokeBarcodeView(APIView):
    """An Admin of the Barcode's Club revokes it, with a reason. It never counts again."""

    @extend_schema(request=RevokeBarcodeSerializer, responses=AdminBarcodeSerializer)
    def post(self, request, barcode_id: int):
        barcode = get_object_or_404(Barcode, pk=barcode_id)
        if not _is_admin(request.user, barcode.club_id):
            raise NotFound()
        body = RevokeBarcodeSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        services.revoke(barcode, by=request.user, reason=body.validated_data["reason"])
        barcode = _barcodes(barcode.team).get(pk=barcode.pk)
        return Response(AdminBarcodeSerializer(barcode).data)
