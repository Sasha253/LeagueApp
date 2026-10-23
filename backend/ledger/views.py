"""Read-only ledger views. Nothing in the API writes, changes or deletes an entry.

- A Player sees their own credit, per Club (credit is spent only at the Club that issued it).
- A Team's credit is seen only by its Captain (FR-52).
- A Team's balance is seen by its Captain and by the Admins of its Club.
Anyone else gets 404, so a Team's money doesn't show that the Team exists.
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import ClubRole
from accounts.permissions import IsPlayer
from clubs.models import Club
from teams.models import Team

from . import services
from .models import LedgerEntry
from .serializers import ClubCreditSerializer, TeamBalanceSerializer, TeamCreditSerializer

Subject = LedgerEntry.Subject


def entries_of(queryset):
    return queryset.select_related("user", "team", "recorded_by").order_by("created_at", "pk")


def team_or_404(team_id: int) -> Team:
    return get_object_or_404(Team.objects.select_related("club", "division__night"), pk=team_id)


class MyCreditView(APIView):
    """The signed-in Player's credit at each Club where they have any."""

    permission_classes = [IsPlayer]

    @extend_schema(responses=ClubCreditSerializer(many=True))
    def get(self, request):
        user = request.user
        holder = Q(subject=Subject.PLAYER, user=user)
        club_ids = LedgerEntry.objects.filter(holder).values("club_id").distinct()
        result = []
        for club in Club.objects.filter(pk__in=club_ids).order_by("name"):
            result.append(
                {
                    "club": club,
                    "balance": services.player_credit(club, user),
                    "entries": entries_of(services.credit_entries(holder & Q(club=club))),
                }
            )
        return Response(ClubCreditSerializer(result, many=True).data)


class TeamCreditView(APIView):
    """A Team's own credit. Only its Captain sees it."""

    permission_classes = [IsPlayer]

    @extend_schema(responses=TeamCreditSerializer)
    def get(self, request, team_id: int):
        team = team_or_404(team_id)
        if team.captain_id != request.user.pk:
            raise NotFound()
        holder = Q(subject=Subject.TEAM, team=team)
        data = {
            "team": team,
            "balance": services.team_credit(team),
            "entries": entries_of(services.credit_entries(holder)),
        }
        return Response(TeamCreditSerializer(data).data)


class TeamBalanceView(APIView):
    """What a Team owes, has paid and still owes, with every line on its account."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=TeamBalanceSerializer)
    def get(self, request, team_id: int):
        team = team_or_404(team_id)
        user = request.user
        is_captain = user.is_player and team.captain_id == user.pk
        is_admin = user.club_roles.filter(club_id=team.club_id, role=ClubRole.Role.ADMIN).exists()
        if not (is_captain or is_admin):
            raise NotFound()
        balance = services.team_balance(team)
        data = {
            "team": team,
            "due": balance.due,
            "paid": balance.paid,
            "outstanding": balance.outstanding,
            "paid_by_method": balance.paid_by_method,
            "entries": entries_of(services.account_entries(team)),
        }
        return Response(TeamBalanceSerializer(data).data)
