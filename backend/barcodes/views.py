"""Payment Barcodes API.

- The Team's Captain sees its Barcode now, or why there is none. The club's Admins can too.
- Admins of the Team's Club see all its Barcodes, issue or reissue one (only for a paid
  Team), and revoke one with a reason.
- Anyone else gets 404, so a Team's Barcodes don't show that they exist.
- At the gate (FR-23) the club's Admins and Referees scan or type a code: the answer is
  Paid or Not paid with the reason, and every scan is logged. Only that club's Barcodes
  are found.
"""

from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.permissions import IsClubAdminOrReferee
from bookings import money as booking_money
from clubs.models import Club
from fixtures.models import FriendlyFee
from ledger import services as ledger
from teams.models import Team

from . import services, signing
from .models import Barcode
from .serializers import (
    AdminBarcodeSerializer,
    CurrentBarcodeSerializer,
    RevokeBarcodeSerializer,
    ScanRequestSerializer,
    ScanResultSerializer,
)


def _is_admin(user, club_id: int) -> bool:
    return user.is_club_admin(club_id)


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
            "booking__user",
            "booking__field",
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


def _scan_answer(result: services.ScanResult) -> dict:
    barcode = result.barcode
    answer = {
        "id": result.scan.pk,
        "paid": result.paid,
        "state": result.status.state,
        "reason": result.status.reason,
        "scanned_at": result.scan.scanned_at,
        "code": result.scan.code,
        "display_code": None,
        "team": None,
        "holder": None,
        "fixture": result.match,
        "booking": None,
        "mode": None,
        "valid_until": None,
        "paid_amount": None,
        "paid_methods": [],
    }
    if barcode is not None:
        answer["display_code"] = signing.display(barcode.code)
        answer["team"] = barcode.team
        answer["holder"] = barcode.holder_name
        answer["mode"] = barcode.mode
        answer["booking"] = barcode.booking
        if barcode.booking is not None:
            answer["valid_until"] = timezone.localdate(barcode.booking.starts_at)
        elif barcode.fixture is not None:
            answer["valid_until"] = timezone.localdate(barcode.fixture.kick_off)
        else:
            answer["valid_until"] = barcode.season.ends_on
    if result.paid and barcode.booking_id is not None:
        answer["paid_amount"] = booking_money.paid(barcode.booking)
    elif result.paid and barcode.friendly_id is not None:
        answer["paid_amount"] = ledger.friendly_paid(barcode.fixture)
        answer["paid_methods"] = sorted(
            {
                entry.method
                for entry in ledger.friendly_payments(barcode.fixture).filter(
                    kind="payment", reversed_by__isnull=True
                )
            }
        )
    elif result.paid:
        balance = ledger.team_balance(barcode.team)
        answer["paid_amount"] = balance.paid
        answer["paid_methods"] = [
            method for method, amount in balance.paid_by_method.items() if amount > 0
        ]
    return answer


class ScanView(APIView):
    """The gate (FR-23): an Admin or Referee of the club scans a Payment Barcode with the
    camera, or types its code. The answer says Paid or Not paid, for which Team and match,
    and why not. Every scan is logged."""

    permission_classes = [IsClubAdminOrReferee]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "barcode_scan"

    @extend_schema(request=ScanRequestSerializer, responses={201: ScanResultSerializer})
    def post(self, request, club_id: int):
        club = get_object_or_404(Club, pk=club_id)
        body = ScanRequestSerializer(data=request.data, club_id=club.pk)
        body.is_valid(raise_exception=True)
        result = services.scan(
            body.validated_data["code"],
            club=club,
            by=request.user,
            method=body.validated_data["method"],
            fixture=body.validated_data.get("fixture"),
        )
        return Response(
            ScanResultSerializer(_scan_answer(result)).data, status=status.HTTP_201_CREATED
        )


class FriendlyBarcodeView(APIView):
    """The friendly's Payment Barcode (FR-24) for its Captain, or why there is none.
    Admins of the club can see it too; anyone else 404."""

    @extend_schema(responses=CurrentBarcodeSerializer)
    def get(self, request, fixture_id: int):
        friendly = get_object_or_404(
            FriendlyFee.objects.select_related("fixture", "fallback"), fixture_id=fixture_id
        )
        is_captain = friendly.captain_id == request.user.pk
        if not (is_captain or _is_admin(request.user, friendly.fixture.club_id)):
            raise NotFound()
        current = services.current_for_friendly(friendly)
        data = {
            "state": current.status.state,
            "reason": current.status.reason,
            "barcode": current.barcode,
        }
        return Response(CurrentBarcodeSerializer(data).data)
