"""Teams: Captains request them, Admins confirm them, Players ask to join them.

A Player's account works at every club (docs/DECISIONS.md), so the Player and Captain views
are not under a Club. The Admin's are, under /clubs/{club_id}/teams/, and show only that
Club's Teams. The rules themselves are in rules.py.
"""

from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q, QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.permissions import IsPlayer, IsTeamCaptain
from clubs.models import Division, Season
from clubs.views import ClubAdminMixin

from . import rules
from .models import JoinRequest, Team, TeamInvite, TeamMembership
from .serializers import (
    AddTeamSerializer,
    AdminTeamSerializer,
    AssignCaptainSerializer,
    DeclineTeamSerializer,
    DivisionOptionSerializer,
    JoinRequestSerializer,
    MemberSerializer,
    MyTeamSerializer,
    SeasonOptionSerializer,
    TeamInviteSerializer,
    TeamRequestSerializer,
    TeamSerializer,
)

SEARCH_LIMIT = 50
NOT_A_MEMBER = "Only Players in this Team can see who is in it."


def teams_with_players() -> QuerySet[Team]:
    return Team.objects.select_related("club", "season", "division__night", "captain").annotate(
        player_count=Count("memberships", filter=Q(memberships__left_at__isnull=True)),
    )


def current_members() -> Prefetch:
    return Prefetch(
        "memberships",
        queryset=TeamMembership.objects.filter(left_at__isnull=True)
        .select_related("team", "player__player_profile")
        .order_by("player__name"),
        to_attr="current_members",
    )


def int_param(request, name: str) -> int | None:
    value = request.query_params.get(name, "")
    return int(value) if value.isdigit() else None


# Choosing a Season and Division for a new Team


@extend_schema(parameters=[OpenApiParameter("club", int, description="Only this club's.")])
class SeasonOptionListView(generics.ListAPIView):
    """Seasons that haven't ended, for a Captain requesting a Team."""

    serializer_class = SeasonOptionSerializer

    def get_queryset(self):
        seasons = Season.objects.select_related("club").filter(ends_on__gte=timezone.localdate())
        club_id = int_param(self.request, "club")
        if club_id is not None:
            seasons = seasons.filter(club_id=club_id)
        return seasons.order_by("club__name", "starts_on")


class DivisionOptionListView(generics.ListAPIView):
    """The Season's club's Divisions, with how many Teams each has this Season."""

    serializer_class = DivisionOptionSerializer
    pagination_class = None

    def get_queryset(self):
        season = get_object_or_404(Season, pk=self.kwargs["season_id"])
        return (
            Division.objects.filter(night__club_id=season.club_id)
            .select_related("night__club__settings")
            .annotate(
                team_count=Count(
                    "teams",
                    filter=Q(teams__season=season, teams__status=Team.Status.ACTIVE),
                )
            )
            .order_by("night__weekday", "name")
        )


# Players and Captains


class TeamViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Search active Teams, request a new one, ask to join or leave one, see its Players."""

    serializer_class = TeamSerializer
    permission_classes = [IsPlayer]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # While the OpenAPI schema is generated.
            return Team.objects.none()
        user = self.request.user
        teams = teams_with_players()
        if self.action == "list":
            return teams.filter(status=Team.Status.ACTIVE)
        # A Player also sees the Teams they are in while those wait for the Admin. A subquery,
        # not a join on memberships, so the `player_count` annotation isn't multiplied.
        mine = Exists(
            TeamMembership.objects.filter(team=OuterRef("pk"), player=user, left_at__isnull=True)
        )
        return teams.filter(Q(status=Team.Status.ACTIVE) | mine)

    def filter_queryset(self, queryset):
        if self.action != "list":
            return queryset
        params = self.request.query_params
        query = params.get("q", "").strip()
        if query:
            queryset = queryset.filter(name__icontains=query)
        for name, lookup in [
            ("club", "club_id"),
            ("season", "season_id"),
            ("division", "division_id"),
            ("night", "division__night_id"),
        ]:
            value = int_param(self.request, name)
            if value is not None:
                queryset = queryset.filter(**{lookup: value})
        if "season" not in params:
            queryset = queryset.filter(season__ends_on__gte=timezone.localdate())
        return queryset.order_by("name", "pk")[:SEARCH_LIMIT]

    @extend_schema(
        summary="Search Teams",
        description=(
            f"Active Teams, by name and by club, Season, Night or Division. Without `season`, "
            f"only Seasons that haven't ended. At most {SEARCH_LIMIT}, by name."
        ),
        parameters=[
            OpenApiParameter("q", str, description="Part of the Team's name."),
            OpenApiParameter("club", int),
            OpenApiParameter("season", int),
            OpenApiParameter("night", int),
            OpenApiParameter("division", int),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Request a new Team",
        description=(
            "The signed-in Player asks the club's Admin for a Team in a Division and Season, "
            "and becomes its Captain. 409 when they are already in a Team in that Division "
            "this Season, or the Division is full."
        ),
        request=TeamRequestSerializer,
        responses={201: TeamSerializer},
    )
    def create(self, request, *args, **kwargs):
        body = TeamRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        team = rules.request_team(request.user, **body.validated_data)
        return Response(self.serialize(team), status=status.HTTP_201_CREATED)

    def serialize(self, team: Team):
        return TeamSerializer(teams_with_players().get(pk=team.pk)).data

    @extend_schema(
        summary="Ask to join a Team", request=None, responses={201: JoinRequestSerializer}
    )
    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        join_request = rules.ask_to_join(self.get_object(), request.user)
        return Response(JoinRequestSerializer(join_request).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Leave a Team",
        description="A Captain can't leave: the Admin assigns another Captain first.",
        request=None,
        responses={200: MyTeamSerializer},
    )
    @action(detail=True, methods=["post"])
    def leave(self, request, pk=None):
        membership = rules.leave_team(self.get_object(), request.user)
        return Response(MyTeamSerializer(membership).data)

    @extend_schema(summary="The Team's Players", responses={200: MemberSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        team = self.get_object()
        memberships = team.current_memberships().select_related("team", "player__player_profile")
        if not memberships.filter(player=request.user).exists():
            raise PermissionDenied(NOT_A_MEMBER)
        return Response(MemberSerializer(memberships.order_by("player__name"), many=True).data)

    @extend_schema(
        summary="Requests to join the Team",
        description="For its Captain. Pending ones unless `status` says otherwise.",
        parameters=[OpenApiParameter("status", enum=JoinRequest.Status.values)],
        responses={200: JoinRequestSerializer(many=True)},
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="join-requests",
        permission_classes=[IsTeamCaptain],
    )
    def join_requests(self, request, pk=None):
        team = self.get_object()
        wanted = request.query_params.get("status", JoinRequest.Status.PENDING)
        join_requests = team.join_requests.filter(status=wanted).select_related(
            "player__player_profile"
        )
        for join_request in join_requests:
            join_request.team = team
        return Response(JoinRequestSerializer(join_requests, many=True).data)


class JoinRequestViewSet(viewsets.GenericViewSet):
    """The Captain accepts or declines a request; the Player who asked can withdraw it."""

    serializer_class = JoinRequestSerializer
    permission_classes = [IsPlayer]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return JoinRequest.objects.none()
        user = self.request.user
        return JoinRequest.objects.select_related("player__player_profile", "team").filter(
            Q(player=user) | Q(team__captain=user)
        )

    def answer(self, join_request: JoinRequest):
        join_request.team = teams_with_players().get(pk=join_request.team_id)
        return Response(JoinRequestSerializer(join_request).data)

    def captains_request(self) -> JoinRequest:
        join_request = self.get_object()
        if not IsTeamCaptain().has_object_permission(self.request, self, join_request):
            raise PermissionDenied()
        return join_request

    @extend_schema(
        summary="Accept a request to join",
        description="The Player joins the Team. 409 when they joined another Team in its "
        "Division this Season first.",
        request=None,
    )
    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        join_request = self.captains_request()
        rules.accept_join(join_request, request.user)
        join_request.refresh_from_db()
        return self.answer(join_request)

    @extend_schema(summary="Decline a request to join", request=None)
    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        return self.answer(rules.decline_join(self.captains_request(), request.user))

    @extend_schema(summary="Withdraw my request to join", request=None)
    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        join_request = self.get_object()
        if join_request.player_id != request.user.pk:
            raise PermissionDenied()
        return self.answer(rules.withdraw_join(join_request))


class MyTeamListView(generics.ListAPIView):
    """The signed-in Player's Teams: current ones first, then past ones, newest first.

    Teams the Admin declined are left out.
    """

    serializer_class = MyTeamSerializer
    permission_classes = [IsPlayer]

    def get_queryset(self):
        teams = teams_with_players()
        return (
            TeamMembership.objects.filter(player=self.request.user)
            .exclude(team__status=Team.Status.DECLINED)
            .prefetch_related(Prefetch("team", queryset=teams))
            .order_by(F("left_at").desc(nulls_first=True), "-joined_at")
        )


class MyJoinRequestListView(generics.ListAPIView):
    """The signed-in Player's requests to join Teams, newest first."""

    serializer_class = JoinRequestSerializer
    permission_classes = [IsPlayer]

    def get_queryset(self):
        teams = teams_with_players()
        return (
            JoinRequest.objects.filter(player=self.request.user)
            .select_related("player__player_profile")
            .prefetch_related(Prefetch("team", queryset=teams))
        )


# The club's Admin


@extend_schema(
    parameters=[
        OpenApiParameter("status", enum=Team.Status.values),
        OpenApiParameter("season", int),
        OpenApiParameter("division", int),
    ]
)
class ClubTeamViewSet(ClubAdminMixin, mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    """The club's Teams and Team requests. Add a Team, confirm or decline a request, assign a
    Captain."""

    queryset = teams_with_players().select_related("requested_by", "decided_by")
    serializer_class = AdminTeamSerializer

    def get_queryset(self):
        teams = super().get_queryset().prefetch_related(current_members())
        if self.action != "list":
            return teams
        for name in ["season", "division"]:
            value = int_param(self.request, name)
            if value is not None:
                teams = teams.filter(**{f"{name}_id": value})
        wanted = self.request.query_params.get("status")
        if wanted:
            teams = teams.filter(status=wanted)
        return teams.order_by("requested_at")

    def answer(self, team: Team, status_code=status.HTTP_200_OK):
        team = self.get_queryset().get(pk=team.pk)
        return Response(AdminTeamSerializer(team).data, status=status_code)

    @extend_schema(
        summary="Add a Team",
        description="Confirmed at once, with its Captain in it: a Player in League App with "
        "`captain_email` (400 if there is none, or they're in another Team of the Division "
        "this Season). Needs the Division's league fee and charges it; 409 when the Division "
        "already has `max_teams` active Teams this Season. The Captain gets an Update if they "
        "opted into the Night.",
        request=AddTeamSerializer,
        responses={201: AdminTeamSerializer},
    )
    def create(self, request, *args, **kwargs):
        body = AddTeamSerializer(data=request.data, context=self.get_serializer_context())
        body.is_valid(raise_exception=True)
        data = body.validated_data
        team = rules.add_team_with_captain(
            data["season"],
            data["division"],
            data["name"].strip(),
            data["captain_email"],
            request.user,
        )
        return self.answer(team, status.HTTP_201_CREATED)

    @extend_schema(
        summary="Confirm a Team request",
        description="409 when the Division already has `max_teams` active Teams this Season.",
        request=None,
    )
    @action(detail=True, methods=["post"])
    def confirm(self, request, *args, **kwargs):
        return self.answer(rules.confirm_team(self.get_object(), request.user))

    @extend_schema(
        summary="Decline a Team request",
        description="Its Players leave it, so they can join or request another Team.",
        request=DeclineTeamSerializer,
    )
    @action(detail=True, methods=["post"])
    def decline(self, request, *args, **kwargs):
        body = DeclineTeamSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        reason = body.validated_data.get("reason", "")
        return self.answer(rules.decline_team(self.get_object(), request.user, reason))

    @extend_schema(
        summary="Assign the Team's Captain",
        description="The new Captain must be a Player in the Team. The old one stays in it.",
        request=AssignCaptainSerializer,
    )
    @action(detail=True, methods=["post"])
    def captain(self, request, *args, **kwargs):
        team = self.get_object()
        body = AssignCaptainSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        membership = (
            team.current_memberships()
            .filter(player_id=body.validated_data["player"])
            .select_related("player")
            .first()
        )
        if membership is None:
            raise ValidationError({"player": [rules.NOT_A_MEMBER]})
        return self.answer(rules.assign_captain(team, membership.player))


class ClubTeamInviteViewSet(
    ClubAdminMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Invites by email to play in one of the club's Teams. Lists and cancels open ones."""

    queryset = TeamInvite.objects.filter(accepted_at__isnull=True).select_related("team")
    serializer_class = TeamInviteSerializer
    club_field = "team__club"

    @extend_schema(
        summary="Invite someone to play in a Team",
        description="A Player with this email joins at once (`accepted` true) and gets an "
        "Update if they opted into the Night; 400 if they're in another Team of the Division "
        "this Season. Anyone else gets an email and joins when they sign up, or start "
        "playing, with it. 409 when the Team isn't active or its Season has ended.",
    )
    def create(self, request, *args, **kwargs):
        body = self.get_serializer(data=request.data)
        body.is_valid(raise_exception=True)
        invite = rules.invite_player(
            body.validated_data["team"], body.validated_data["email"], request.user
        )
        return Response(self.get_serializer(invite).data, status=status.HTTP_201_CREATED)
