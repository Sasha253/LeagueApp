"""Payments API (FR-19 to FR-22).

- A Player in a Team sees its payment options and starts a contribution; only the payer
  sees a Payment. Anyone else gets 404, so a Team's money doesn't show that it exists.
- An Admin of the Team's Club records cash, and sees which of the club's Teams have paid.
- The gateway posts its notifications to the webhook, which takes no login: every
  notification is checked (source, signature, merchant, amount, server-side validation)
  before anything is recorded.
"""

from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import ClubRole, User
from accounts.permissions import IsClubAdmin, IsPlayer
from clubs.models import PaymentProvider
from ledger import services as ledger
from ledger.serializers import LedgerEntrySerializer
from teams.models import Team

from . import services
from .gateways import client_ip
from .models import GatewayNotification, Payment
from .serializers import (
    CashPaymentSerializer,
    GatewayNotificationFieldsSerializer,
    PaymentOptionsSerializer,
    PaymentSerializer,
    StartPaymentSerializer,
    TeamPaymentStatusSerializer,
)


def team_or_404(team_id: int) -> Team:
    return get_object_or_404(Team.objects.select_related("club__settings"), pk=team_id)


def my_team_or_404(team_id: int, user) -> Team:
    """A Team the signed-in Player is in now; 404 for any other."""
    team = team_or_404(team_id)
    if not team.current_memberships().filter(player=user).exists():
        raise NotFound()
    return team


class PaymentOptionsView(APIView):
    """What the Player needs to choose how much to pay towards their Team."""

    permission_classes = [IsPlayer]

    @extend_schema(responses=PaymentOptionsSerializer)
    def get(self, request, team_id: int):
        team = my_team_or_404(team_id, request.user)
        balance = ledger.team_balance(team)
        card_enabled, minimum = services.card_options(team)
        data = {
            "team": team,
            "due": balance.due,
            "outstanding": balance.outstanding,
            "is_paid": balance.is_paid,
            "card_enabled": card_enabled,
            "minimum_card_amount": minimum if card_enabled else None,
            "my_credit": ledger.player_credit(team.club, request.user),
            "team_credit": (
                ledger.team_credit(team) if team.captain_id == request.user.pk else None
            ),
        }
        return Response(PaymentOptionsSerializer(data).data)


class StartPaymentView(APIView):
    """A Player pays towards their Team: credit first if chosen, then card (FR-19)."""

    permission_classes = [IsPlayer]

    @extend_schema(request=StartPaymentSerializer, responses={201: PaymentSerializer})
    def post(self, request, team_id: int):
        team = my_team_or_404(team_id, request.user)
        body = StartPaymentSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        payment = services.start_payment(
            team=team,
            player=request.user,
            amount=body.validated_data["amount"],
            credit=body.validated_data["credit"],
        )
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class MyPaymentListView(APIView):
    """The signed-in Player's payments, newest first."""

    permission_classes = [IsPlayer]

    @extend_schema(responses=PaymentSerializer(many=True))
    def get(self, request):
        payments = Payment.objects.filter(player=request.user).select_related("team", "player")
        return Response(PaymentSerializer(payments, many=True).data)


class PaymentDetailView(APIView):
    """One payment, for the Player who made it (e.g. after returning from the gateway)."""

    permission_classes = [IsPlayer]

    @extend_schema(responses=PaymentSerializer)
    def get(self, request, reference):
        payment = get_object_or_404(
            Payment.objects.select_related("team", "player"),
            reference=reference,
            player=request.user,
        )
        return Response(PaymentSerializer(payment).data)


class CashPaymentView(APIView):
    """An Admin of the Team's Club records cash paid to the club (FR-22)."""

    @extend_schema(request=CashPaymentSerializer, responses={201: LedgerEntrySerializer})
    def post(self, request, team_id: int):
        team = team_or_404(team_id)
        is_admin = request.user.club_roles.filter(
            club_id=team.club_id, role=ClubRole.Role.ADMIN
        ).exists()
        if not is_admin:
            raise NotFound()
        body = CashPaymentSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        player = None
        if body.validated_data.get("player_id") is not None:
            player = User.objects.filter(pk=body.validated_data["player_id"]).first()
            if player is None or not team.current_memberships().filter(player=player).exists():
                raise ValidationError({"player_id": "That Player isn't in this Team."})
        entry = services.record_cash(
            team=team,
            admin=request.user,
            amount=body.validated_data["amount"],
            player=player,
            reason=body.validated_data.get("reason", ""),
        )
        return Response(LedgerEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class ClubTeamPaymentsView(APIView):
    """Which of the club's active Teams have paid (FR-21), unpaid first."""

    permission_classes = [IsClubAdmin]

    @extend_schema(
        parameters=[OpenApiParameter("season", int, description="Only this Season's Teams.")],
        responses=TeamPaymentStatusSerializer(many=True),
    )
    def get(self, request, club_id: int):
        teams = Team.objects.filter(club_id=club_id, status=Team.Status.ACTIVE).select_related(
            "season", "division"
        )
        season = request.query_params.get("season")
        if season:
            if not season.isdigit():
                raise ValidationError({"season": "A Season id."})
            teams = teams.filter(season_id=int(season))
        balances = ledger.team_balances(teams)
        rows = [
            {
                "team": team,
                "season": team.season,
                "division": team.division,
                "due": balances[team.pk].due,
                "paid": balances[team.pk].paid,
                "outstanding": balances[team.pk].outstanding,
                "is_paid": balances[team.pk].is_paid,
            }
            for team in teams
        ]
        rows.sort(key=lambda row: (row["is_paid"], row["team"].name.lower()))
        return Response(TeamPaymentStatusSerializer(rows, many=True).data)


class PayFastNotifyView(APIView):
    """PayFast's ITN webhook. No login: PayFast calls it, and every ITN is checked.

    Answers 200 when the ITN was applied or had already been, so PayFast stops sending
    it, and 400 when a check failed (nothing is recorded).
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [FormParser]

    @extend_schema(
        auth=[],
        request={"application/x-www-form-urlencoded": GatewayNotificationFieldsSerializer},
        responses={200: None, 400: None},
    )
    def post(self, request):
        fields = list(request.data.items())
        source_ip = client_ip(request, settings.PAYFAST_TRUSTED_PROXIES)
        logged = services.handle_notification(PaymentProvider.PAYFAST, fields, source_ip)
        if logged.outcome == GatewayNotification.Outcome.REJECTED:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_200_OK)
