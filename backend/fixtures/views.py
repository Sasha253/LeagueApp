"""Fixtures: the club's Admin imports and lists them; Players see their own Teams'.

The Admin's views are under /clubs/{club_id}/ and show only that Club's Fixtures. A Player's
account works at every club (docs/DECISIONS.md), so their views are not under a Club; they
show only Fixtures of Teams the Player is in now.
"""

import datetime as dt
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q, QuerySet
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from accounts.permissions import IsPlayer
from clubs.models import Club
from clubs.views import XLSX, ClubAdminMixin
from core.exceptions import Conflict
from core.tables import TableError, read_workbook
from teams.models import Team, TeamMembership

from . import (
    borrowing,
    confirmations,
    friendlies,
    league_import,
    lifecycle,
    readiness,
    reschedules,
)
from .friendly_serializers import (
    FriendlyCashSerializer,
    FriendlySerializer,
    FriendlyTermsSerializer,
    MyFriendlySerializer,
)
from .models import (
    BorrowedPlayer,
    CaptainRequest,
    Fixture,
    FixtureReschedule,
    FixtureTransition,
    FriendlyFee,
    PlayerRequest,
    PlayerRequestInvite,
    ReplacementOffer,
    TeamReadiness,
)
from .serializers import (
    AdminFixtureDetailSerializer,
    AdminFixtureSerializer,
    CaptainRequestAcceptSerializer,
    CaptainRequestCreateSerializer,
    CaptainRequestDeclineSerializer,
    CaptainRequestSerializer,
    ClubCaptainRequestSerializer,
    FixtureAnswerSerializer,
    FriendlyEligibleSerializer,
    LeagueImportResultSerializer,
    LeagueImportUploadSerializer,
    MatchPlayerRequestsSerializer,
    MatchRequestsSerializer,
    MyFixtureSerializer,
    MyPlayerRequestSerializer,
    PlayerRequestCreateSerializer,
    PlayerRequestPreviewQuerySerializer,
    PlayerRequestPreviewSerializer,
    PlayerRequestSerializer,
    ReadinessDecisionSerializer,
    ReschedulePreviewSerializer,
    RescheduleSerializer,
    SquadSerializer,
    TonightFixtureSerializer,
)

PAST_LIMIT = 50
IMPORT_RACE = "The club's league changed while importing. Upload the file again."


def fixtures() -> QuerySet[Fixture]:
    return Fixture.objects.select_related(
        "club", "season", "division__night", "pitch__referee", "home_team", "away_team"
    )


def int_param(request, name: str) -> int | None:
    value = request.query_params.get(name, "")
    return int(value) if value.isdigit() else None


def my_team_ids(user) -> set[int]:
    """The active Teams the Player is in now."""
    return set(
        TeamMembership.objects.filter(
            player=user, left_at__isnull=True, team__status=Team.Status.ACTIVE
        ).values_list("team_id", flat=True)
    )


# Players and Captains


@extend_schema(
    parameters=[
        OpenApiParameter(
            "when",
            enum=["upcoming", "past"],
            default="upcoming",
            description=f"Upcoming: kick-off still to come, soonest first. Past: the latest "
            f"{PAST_LIMIT}, newest first.",
        )
    ]
)
class MyFixtureListView(generics.ListAPIView):
    """Fixtures of the Teams the signed-in Player is in now, cancelled ones too."""

    serializer_class = MyFixtureSerializer
    permission_classes = [IsPlayer]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Fixture.objects.none()
        teams = self.team_ids
        mine = fixtures().filter(Q(home_team_id__in=teams) | Q(away_team_id__in=teams))
        now = timezone.now()
        if self.request.query_params.get("when") == "past":
            return mine.filter(kick_off__lt=now).order_by("-kick_off")[:PAST_LIMIT]
        return mine.filter(kick_off__gte=now).order_by("kick_off", "pk")

    @property
    def team_ids(self) -> set[int]:
        if not hasattr(self, "_team_ids"):
            self._team_ids = my_team_ids(self.request.user)
        return self._team_ids

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if not getattr(self, "swagger_fake_view", False):
            context["my_team_ids"] = self.team_ids
        return context


class FixtureViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """One Fixture, for a Player in either of its Teams now. Anyone else gets 404."""

    serializer_class = MyFixtureSerializer
    permission_classes = [IsPlayer]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Fixture.objects.none()
        teams = my_team_ids(self.request.user)
        self.team_ids = teams
        return fixtures().filter(Q(home_team_id__in=teams) | Q(away_team_id__in=teams))

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["my_team_ids"] = getattr(self, "team_ids", set())
        return context

    @extend_schema(summary="A Fixture of one of my Teams")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def my_squad(self, fixture: Fixture) -> Response:
        team = next(
            team for team in (fixture.home_team, fixture.away_team) if team.pk in self.team_ids
        )
        squad = confirmations.squad(fixture, team)
        return Response(SquadSerializer(squad, context={"me": self.request.user}).data)

    @extend_schema(
        summary="My Team's replies for a Fixture",
        description="Every Player in my Team now and whether they are playing, against the "
        "Division's minimum (FR-38). Only my own Team's replies.",
        responses=SquadSerializer,
    )
    @action(detail=True, methods=["get"])
    def squad(self, request, *args, **kwargs):
        return self.my_squad(self.get_object())

    @extend_schema(
        summary="Answer a Fixture's Confirmation, or change the answer",
        description="Until the cutoff (T-6h), while the match is confirming (FR-3). 409 "
        "before the Confirmations go out or after the cutoff. Answers with my Team's replies.",
        request=FixtureAnswerSerializer,
        responses=SquadSerializer,
    )
    @action(detail=True, methods=["post"])
    def answer(self, request, *args, **kwargs):
        fixture = self.get_object()
        given = FixtureAnswerSerializer(data=request.data)
        given.is_valid(raise_exception=True)
        confirmations.answer(
            fixture,
            request.user,
            given.validated_data["answer"],
            via=confirmations.Via.FIXTURE,
        )
        return self.my_squad(self.get_object())

    def my_requests(self, fixture: Fixture) -> Response:
        mine = [t for t in (fixture.home_team, fixture.away_team) if t.pk in self.team_ids]
        is_captain = reschedules.captain_team(fixture, self.request.user) is not None
        requests = list(
            CaptainRequest.objects.filter(fixture=fixture, team__in=mine)
            .select_related("team", "requested_by", "decided_by")
            .order_by("-requested_at", "-pk")
        )
        waiting = any(r.status == CaptainRequest.Status.PENDING for r in requests)
        body = {
            "is_captain": is_captain,
            "can_request": is_captain and not waiting and reschedules.can_request(fixture),
            "requests": requests,
        }
        return Response(MatchRequestsSerializer(body).data)

    @extend_schema(
        methods=["GET"],
        summary="My Team's requests to cancel or postpone a Fixture",
        description="Every Player in the Team sees them; only its Captain can send one (FR-18).",
        responses=MatchRequestsSerializer,
    )
    @extend_schema(
        methods=["POST"],
        summary="Ask the Admin to cancel or postpone a Fixture (Captain)",
        description="Only the Captain of a Team in the match (403 otherwise), while the match "
        "is scheduled, confirming or ready and before kick-off, with nothing else waiting "
        "for the Admin from the Team (409 otherwise). Nothing changes until an Admin "
        "accepts it. Answers with the Team's requests.",
        request=CaptainRequestCreateSerializer,
        responses={201: MatchRequestsSerializer},
    )
    @action(detail=True, methods=["get", "post"])
    def requests(self, request, *args, **kwargs):
        fixture = self.get_object()
        if request.method == "POST":
            body = CaptainRequestCreateSerializer(data=request.data)
            body.is_valid(raise_exception=True)
            reschedules.request(
                fixture, request.user, body.validated_data["kind"], body.validated_data["reason"]
            )
            answer = self.my_requests(self.get_object())
            answer.status_code = status.HTTP_201_CREATED
            return answer
        return self.my_requests(fixture)

    # Player and Goalkeeper Requests (FR-35 to FR-37)

    def my_player_requests(self, fixture: Fixture) -> Response:
        mine = [t for t in (fixture.home_team, fixture.away_team) if t.pk in self.team_ids]
        is_captain = borrowing.captain_team(fixture, self.request.user) is not None
        requests = list(
            PlayerRequest.objects.filter(fixture=fixture, team__in=mine)
            .select_related("team", "raised_by", "fixture")
            .prefetch_related(player_requests_joined())
            .order_by("-raised_at", "-pk")
        )
        body = {
            "is_captain": is_captain,
            "can_request": is_captain and borrowing.can_raise(fixture),
            "max_places": borrowing.max_places(fixture),
            "requests": requests,
        }
        return Response(MatchPlayerRequestsSerializer(body).data)

    @extend_schema(
        methods=["GET"],
        summary="My Team's Player and Goalkeeper Requests for a Fixture",
        description="Every Player in the Team sees them and who joined (FR-38); only its "
        "Captain can raise one.",
        responses=MatchPlayerRequestsSerializer,
    )
    @extend_schema(
        methods=["POST"],
        summary="Request borrowed Players or a Goalkeeper for a Fixture (Captain)",
        description="FR-35, FR-36: sent to the Players of that position opted into the Night "
        "who are in neither Team. Only the Captain of a Team in the match (403 otherwise), "
        "while the match is scheduled, confirming or ready and before kick-off, with no "
        "open request of that kind from the Team and someone to ask (409 otherwise). The "
        "first to accept join (FR-37). Answers with the Team's requests.",
        request=PlayerRequestCreateSerializer,
        responses={201: MatchPlayerRequestsSerializer},
    )
    @action(detail=True, methods=["get", "post"], url_path="player-requests")
    def player_requests(self, request, *args, **kwargs):
        fixture = self.get_object()
        if request.method == "POST":
            body = PlayerRequestCreateSerializer(data=request.data)
            body.is_valid(raise_exception=True)
            borrowing.raise_request(
                fixture, request.user, body.validated_data["kind"], body.validated_data["places"]
            )
            answer = self.my_player_requests(self.get_object())
            answer.status_code = status.HTTP_201_CREATED
            return answer
        return self.my_player_requests(fixture)

    @extend_schema(
        summary="Who a Player or Goalkeeper Request would go to (Captain)",
        parameters=[PlayerRequestPreviewQuerySerializer],
        responses=PlayerRequestPreviewSerializer,
    )
    @action(detail=True, methods=["get"], url_path="player-requests/preview")
    def player_requests_preview(self, request, *args, **kwargs):
        fixture = self.get_object()
        query = PlayerRequestPreviewQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        planned = borrowing.preview(fixture, request.user, query.validated_data["kind"])
        return Response(PlayerRequestPreviewSerializer(planned).data)


def player_requests_joined() -> Prefetch:
    return Prefetch("joined", queryset=BorrowedPlayer.objects.select_related("player"))


class PlayerRequestViewSet(viewsets.GenericViewSet):
    """A Captain's own Player and Goalkeeper Requests. Anyone else gets 404."""

    serializer_class = PlayerRequestSerializer
    permission_classes = [IsPlayer]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PlayerRequest.objects.none()
        return (
            PlayerRequest.objects.filter(team__captain=self.request.user)
            .select_related("team", "raised_by", "fixture")
            .prefetch_related(player_requests_joined())
        )

    @extend_schema(
        summary="Withdraw my Player or Goalkeeper Request",
        description="Only while it is open: 409 once filled, withdrawn or no longer applying. "
        "Whoever already joined keeps their place.",
        request=None,
        responses=PlayerRequestSerializer,
    )
    @action(detail=True, methods=["post"])
    def withdraw(self, request, *args, **kwargs):
        withdrawn = borrowing.withdraw(self.get_object(), request.user)
        return Response(PlayerRequestSerializer(self.get_queryset().get(pk=withdrawn.pk)).data)


class MyPlayerRequestListView(generics.ListAPIView):
    """Player and Goalkeeper Requests I was sent for matches still to come (Screens.md
    Player 1 "Games you can join"): ones I can still answer, and ones I joined. Answer with
    POST /api/v1/inbox/{notification_id}/answer/."""

    serializer_class = MyPlayerRequestSerializer
    permission_classes = [IsPlayer]
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PlayerRequestInvite.objects.none()
        now = timezone.now()
        invites = (
            PlayerRequestInvite.objects.filter(
                player=self.request.user, request__fixture__kick_off__gt=now
            )
            .select_related(
                "notification",
                "request__team",
                "request__fixture__club",
                "request__fixture__season",
                "request__fixture__division__night",
                "request__fixture__pitch",
                "request__fixture__home_team",
                "request__fixture__away_team",
            )
            .prefetch_related(
                Prefetch(
                    "request__joined",
                    queryset=BorrowedPlayer.objects.only("request", "player", "team", "kick_off"),
                )
            )
            .order_by("request__fixture__kick_off", "pk")
        )
        joined = Q(request__joined__player=self.request.user)
        still_open = Q(
            request__status=PlayerRequest.Status.OPEN,
            notification__closed_at__isnull=True,
            notification__answer_by__gt=now,
        )
        found = invites.filter(joined | still_open).distinct()
        # Keep only places that still count and requests that still apply: a reschedule or
        # a Team leaving the match ends both without touching these rows.
        serializer = self.get_serializer()
        return [
            invite
            for invite in found
            if serializer.get_joined(invite)
            or serializer.get_status(invite) == PlayerRequest.Status.OPEN
        ]


class CaptainRequestViewSet(viewsets.GenericViewSet):
    """A Captain's own requests to cancel or postpone (FR-18). Anyone else gets 404."""

    serializer_class = CaptainRequestSerializer
    permission_classes = [IsPlayer]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return CaptainRequest.objects.none()
        return CaptainRequest.objects.filter(team__captain=self.request.user).select_related(
            "team", "requested_by", "decided_by"
        )

    @extend_schema(
        summary="Withdraw my request to cancel or postpone",
        description="Only while it waits for the Admin: 409 once decided.",
        request=None,
        responses=CaptainRequestSerializer,
    )
    @action(detail=True, methods=["post"])
    def withdraw(self, request, *args, **kwargs):
        withdrawn = reschedules.withdraw(self.get_object(), request.user)
        return Response(CaptainRequestSerializer(self.get_queryset().get(pk=withdrawn.pk)).data)


# The club's Admin


@extend_schema(
    parameters=[
        OpenApiParameter("season", int, description="Without it, Seasons that haven't ended."),
        OpenApiParameter("night", int),
        OpenApiParameter("division", int),
        OpenApiParameter("status", enum=Fixture.Status.values),
    ]
)
class ClubFixtureViewSet(
    ClubAdminMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """The club's Fixtures, by kick-off. The Admin can mark one friendly-eligible."""

    queryset = fixtures().select_related("friendly_eligible_changed_by")
    http_method_names = ["get", "post", "patch", "options"]

    def get_serializer_class(self):
        return AdminFixtureDetailSerializer if self.action == "retrieve" else AdminFixtureSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "retrieve":
            return queryset.prefetch_related(
                Prefetch("transitions", queryset=FixtureTransition.objects.select_related("actor")),
                Prefetch(
                    "replacements",
                    queryset=ReplacementOffer.objects.select_related(
                        "out_team", "remaining_team", "accepted_team", "accepted_by"
                    ).prefetch_related("candidates__team"),
                ),
                Prefetch(
                    "reschedules",
                    queryset=FixtureReschedule.objects.select_related(
                        "from_pitch", "to_pitch", "by"
                    ),
                ),
                Prefetch(
                    "captain_requests",
                    queryset=CaptainRequest.objects.select_related(
                        "team", "requested_by", "decided_by"
                    ),
                ),
            )
        if self.action != "list":
            return queryset
        for name, lookup in [
            ("season", "season_id"),
            ("night", "division__night_id"),
            ("division", "division_id"),
        ]:
            value = int_param(self.request, name)
            if value is not None:
                queryset = queryset.filter(**{lookup: value})
        if "season" not in self.request.query_params:
            queryset = queryset.filter(season__ends_on__gte=timezone.localdate())
        wanted = self.request.query_params.get("status")
        if wanted:
            queryset = queryset.filter(status=wanted)
        return queryset.order_by("kick_off", "pitch__name", "pk")

    @extend_schema(
        summary="Mark a Fixture friendly-eligible, or not",
        description="Only while the match may still fall through: 409 once it is a "
        "friendly, cancelled or played.",
        request=FriendlyEligibleSerializer,
        responses={200: AdminFixtureDetailSerializer},
    )
    def partial_update(self, request, *args, **kwargs):
        fixture = self.get_object()
        body = FriendlyEligibleSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        eligible = body.validated_data["friendly_eligible"]
        lifecycle.set_friendly_eligible(fixture, eligible, request.user)
        return self.detail_of(fixture)

    @extend_schema(
        methods=["get"],
        summary="A friendly's fee, who pays it and its Captain",
        description="FR-24. 409 when the match never became a friendly.",
        responses=FriendlySerializer,
    )
    @extend_schema(
        methods=["post"],
        summary="Set a friendly's fee, who pays it and its Captain",
        description="FR-24. Only while the match is a friendly for its kick-off and before "
        "kick-off (409). The Team's Players can pay only when a Team is still in (409). The "
        "Captain must play in it: joined it, or a current Player of the remaining Team "
        "(409). The fee and payer are fixed once a payment stands (409). Once the fee is "
        "settled and a Captain is set, the Captain gets the friendly's Payment Barcode; a "
        "new Captain revokes the old one's.",
        request=FriendlyTermsSerializer,
        responses=FriendlySerializer,
    )
    @action(detail=True, methods=["get", "post"])
    def friendly(self, request, *args, **kwargs):
        fixture = self.get_object()
        if request.method == "POST":
            body = FriendlyTermsSerializer(data=request.data)
            body.is_valid(raise_exception=True)
            friendlies.set_terms(fixture, **body.validated_data, by=request.user)
        return Response(FriendlySerializer(friendly_view(fixture)).data)

    @extend_schema(
        summary="Record cash for a friendly",
        description="FR-22, FR-24. Cash paid to the club by one of the friendly's payers "
        "(409 for anyone else), never more than it still owes (409). Recorded in the ledger "
        "as friendly income.",
        request=FriendlyCashSerializer,
        responses={201: FriendlySerializer},
    )
    @action(detail=True, methods=["post"], url_path="friendly/payments")
    def friendly_payments(self, request, *args, **kwargs):
        fixture = self.get_object()
        body = FriendlyCashSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        friendlies.record_cash(
            fixture,
            player=body.validated_data["player"],
            amount=body.validated_data["amount"],
            by=request.user,
            reason=body.validated_data["reason"],
        )
        return Response(
            FriendlySerializer(friendly_view(fixture)).data, status=status.HTTP_201_CREATED
        )

    def detail_of(self, fixture: Fixture) -> Response:
        self.action = "retrieve"
        return Response(AdminFixtureDetailSerializer(self.get_queryset().get(pk=fixture.pk)).data)

    def reschedule_body(self, request) -> dict:
        body = RescheduleSerializer(data=request.data, context={"club": self.club})
        body.is_valid(raise_exception=True)
        return body.validated_data

    @extend_schema(
        summary="Preview a reschedule",
        description="Checks the new kick-off and pitch and says what the reschedule will do: "
        "the status after, whether Confirmations go out now (FR-9) and how many Players and "
        "officials are told (FR-7, FR-8). Writes nothing. 400 or 409 as the reschedule.",
        request=RescheduleSerializer,
        responses=ReschedulePreviewSerializer,
    )
    @action(detail=True, methods=["post"], url_path="reschedule/preview")
    def reschedule_preview(self, request, *args, **kwargs):
        fixture = self.get_object()
        given = self.reschedule_body(request)
        planned = reschedules.plan(fixture, given["kick_off"], given.get("pitch"))
        return Response(ReschedulePreviewSerializer(planned).data)

    @extend_schema(
        summary="Reschedule a Fixture",
        description="Only a scheduled, confirming or ready match before kick-off (409 "
        "otherwise). A new kick-off must be after the T-6h cutoff counted from now, inside "
        "the Season and on the Division's Night (400); the pitch must be free then and "
        "neither Team may have another match that day (409). A new kick-off restarts the "
        "lifecycle and sends Confirmations now when it is within the Confirmation window "
        "(FR-9). Both Teams' Players and only the Night's Admins and the affected pitch's "
        "Referee get an Update (FR-7, FR-8). Answers with the Fixture.",
        request=RescheduleSerializer,
        responses=AdminFixtureDetailSerializer,
    )
    @action(detail=True, methods=["post"])
    def reschedule(self, request, *args, **kwargs):
        fixture = self.get_object()
        given = self.reschedule_body(request)
        reschedules.reschedule(
            fixture,
            given["kick_off"],
            given.get("pitch"),
            admin=request.user,
            note=given.get("note", ""),
        )
        return self.detail_of(fixture)


@extend_schema(
    parameters=[
        OpenApiParameter("status", enum=CaptainRequest.Status.values),
        OpenApiParameter("fixture", int),
    ]
)
class ClubCaptainRequestViewSet(ClubAdminMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Captains' requests to cancel or postpone the club's matches (FR-18), oldest first."""

    queryset = CaptainRequest.objects.select_related(
        "team", "requested_by", "decided_by", "fixture__club", "fixture__season"
    ).select_related(
        "fixture__division__night", "fixture__pitch", "fixture__home_team", "fixture__away_team"
    )
    club_field = "fixture__club"
    serializer_class = ClubCaptainRequestSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            wanted = self.request.query_params.get("status")
            if wanted:
                queryset = queryset.filter(status=wanted)
            fixture = int_param(self.request, "fixture")
            if fixture is not None:
                queryset = queryset.filter(fixture_id=fixture)
        return queryset.order_by("requested_at", "pk")

    def answer(self, captain_request: CaptainRequest) -> Response:
        return Response(self.get_serializer(self.get_queryset().get(pk=captain_request.pk)).data)

    @extend_schema(
        summary="Accept a Captain's request",
        description="A cancellation takes the Captain's Team out of the match and starts the "
        "search for a new opponent (FR-13 to FR-17). A postponement reschedules the match to "
        "`kick_off` (required) and `pitch`, as the reschedule endpoint. Only a pending "
        "request whose match can still change, for its kick-off: 409 otherwise.",
        request=CaptainRequestAcceptSerializer,
        responses=ClubCaptainRequestSerializer,
    )
    @action(detail=True, methods=["post"])
    def accept(self, request, *args, **kwargs):
        captain_request = self.get_object()
        body = CaptainRequestAcceptSerializer(data=request.data, context={"club": self.club})
        body.is_valid(raise_exception=True)
        given = body.validated_data
        reschedules.accept(
            captain_request,
            request.user,
            kick_off=given.get("kick_off"),
            pitch=given.get("pitch"),
            note=given.get("note", ""),
        )
        return self.answer(captain_request)

    @extend_schema(
        summary="Decline a Captain's request",
        description="The match goes ahead as planned; the Captain is told. Only a pending "
        "request: 409 otherwise.",
        request=CaptainRequestDeclineSerializer,
        responses=ClubCaptainRequestSerializer,
    )
    @action(detail=True, methods=["post"])
    def decline(self, request, *args, **kwargs):
        captain_request = self.get_object()
        body = CaptainRequestDeclineSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        reschedules.decline(captain_request, request.user, body.validated_data.get("note", ""))
        return self.answer(captain_request)


class LeagueImportView(ClubAdminMixin, generics.GenericAPIView):
    """Reads the uploaded workbook and runs the league import: Seasons, Nights and Divisions,
    and Fixtures (FR-39, FR-53). Each sheet is checked against what the ones before it add,
    so the import writes as it goes, in a transaction that is rolled back unless it commits."""

    serializer_class = LeagueImportUploadSerializer
    parser_classes = [MultiPartParser]

    def run(self, request, *, commit: bool):
        upload = self.get_serializer(data=request.data)
        upload.is_valid(raise_exception=True)
        try:
            sheets = read_workbook(upload.validated_data["file"], league_import.SHEETS)
        except TableError as error:
            raise ValidationError({"file": [str(error)]}) from error
        try:
            with transaction.atomic():
                # One import per Club at a time.
                Club.objects.select_for_update().get(pk=self.club.pk)
                outcome = league_import.run(self.club, sheets, request.user)
                committed = commit and not outcome.has_errors
                if not committed:
                    transaction.set_rollback(True)
        except IntegrityError as error:
            raise Conflict(IMPORT_RACE) from error
        body = {
            "committed": committed,
            "summary": outcome.summary,
            "seasons": outcome.seasons.rows,
            "divisions": outcome.divisions.rows,
            "fixtures": outcome.fixtures.rows,
        }
        code = status.HTTP_400_BAD_REQUEST if commit and not committed else status.HTTP_200_OK
        return Response(LeagueImportResultSerializer(body).data, status=code)


class LeagueImportPreviewView(LeagueImportView):
    @extend_schema(
        summary="Preview a league import",
        description="Checks every row of every sheet and says what the import would do. "
        "Saves nothing.",
        responses={200: LeagueImportResultSerializer},
    )
    def post(self, request, *args, **kwargs):
        return self.run(request, commit=False)


class LeagueImportCommitView(LeagueImportView):
    @extend_schema(
        summary="Import Seasons, Nights and Divisions, and Fixtures",
        description=(
            "Checks the workbook again and saves every row of every sheet in one transaction. "
            "If any row has an error, nothing is saved and the answer is 400 with the rows "
            "and their errors."
        ),
        responses={200: LeagueImportResultSerializer, 400: LeagueImportResultSerializer},
    )
    def post(self, request, *args, **kwargs):
        return self.run(request, commit=True)


class LeagueImportTemplateView(ClubAdminMixin, generics.GenericAPIView):
    @extend_schema(
        summary="Download the league import template",
        responses={(200, XLSX): OpenApiResponse(OpenApiTypes.BINARY)},
    )
    def get(self, request, *args, **kwargs):
        response = HttpResponse(league_import.template_xlsx(), content_type=XLSX)
        response["Content-Disposition"] = 'attachment; filename="league-import.xlsx"'
        return response


# The T-6h readiness check (FR-5, FR-6): the Admin's Tonight queue


class TonightView(ClubAdminMixin, generics.GenericAPIView):
    serializer_class = TonightFixtureSerializer

    @extend_schema(
        summary="Tonight: today's Fixtures and the T-6h queue",
        description="The club's Fixtures kicking off today (South African date), and any "
        "Fixture with a Team still waiting for the Admin's ruling, by kick-off. Each Team's "
        "confirmed Players against the Division minimum, what it owes, and what the T-6h "
        "check decided (FR-5, FR-6).",
        responses=TonightFixtureSerializer(many=True),
    )
    def get(self, request, *args, **kwargs):
        return Response(TonightFixtureSerializer(readiness.tonight(self.club), many=True).data)


class ReadinessDecisionView(ClubAdminMixin, generics.GenericAPIView):
    """The Admin rules a Team waiting at T-6h in (for example cash at the gate) or out."""

    queryset = TeamReadiness.objects.all()
    club_field = "fixture__club"
    serializer_class = ReadinessDecisionSerializer

    @extend_schema(
        summary="Rule a Team waiting at T-6h in or out",
        description="Only a Team waiting for the Admin (unpaid, or no Confirmations went "
        "out), once, while the match is still confirming: 409 otherwise. Once both Teams "
        "are decided the Fixture moves to ready, one team out or both teams out. Answers "
        "with the Fixture as Tonight shows it.",
        request=ReadinessDecisionSerializer,
        responses=TonightFixtureSerializer,
    )
    def post(self, request, *args, **kwargs):
        row = self.get_object()
        body = self.get_serializer(data=request.data)
        body.is_valid(raise_exception=True)
        readiness.decide(
            row, request.user, body.validated_data["decision"], body.validated_data.get("note", "")
        )
        fixture = fixtures().get(pk=row.fixture_id)
        return Response(TonightFixtureSerializer(readiness.tonight_fixture(fixture)).data)


# Friendlies (FR-24)


def start_of_today() -> dt.datetime:
    return timezone.make_aware(dt.datetime.combine(timezone.localdate(), dt.time()))


def friendly_view(fixture: Fixture) -> dict:
    """Everything the Admin's friendly section shows, decided here."""
    from barcodes import services as barcodes
    from ledger import services as ledger

    fixture = fixtures().get(pk=fixture.pk)
    fallback = friendlies.friendly_fallback(fixture)
    friendly = (
        FriendlyFee.objects.filter(fixture=fixture)
        .select_related("captain", "set_by", "fallback__remaining_team", "fixture")
        .first()
    )
    on = friendlies.is_on(fixture, fallback)
    zero = Decimal("0.00")
    totals = friendlies.totals(friendly) if friendly else None
    payer_choices = [
        value
        for value in FriendlyFee.Payer.values
        if value != FriendlyFee.Payer.TEAM_PLAYERS or fallback.remaining_team_id is not None
    ]
    if friendly is None:
        barcode = {"state": "no_captain", "reason": friendlies.NO_TERMS, "barcode": None}
    else:
        current = barcodes.current_for_friendly(friendly)
        barcode = {
            "state": current.status.state,
            "reason": current.status.reason,
            "barcode": current.barcode,
        }
    return {
        "fixture": fixture,
        "cause": fallback.cause,
        "remaining_team": fallback.remaining_team,
        "is_on": on,
        "can_change": on and timezone.now() < fixture.kick_off,
        "money_fixed": ledger.friendly_paid(fixture) > 0,
        "default_fee": fixture.club.settings.friendly_fee,
        "payer_choices": payer_choices,
        "terms": friendly,
        "due": totals.due if totals else zero,
        "paid": totals.paid if totals else ledger.friendly_paid(fixture),
        "outstanding": totals.outstanding if totals else zero,
        "settled": totals.settled if totals else False,
        "payments": ledger.friendly_payments(fixture).select_related("user", "recorded_by"),
        "payers": friendlies.payers(friendly) if friendly and on else [],
        "captain_candidates": friendlies.captain_candidates(fallback) if on else [],
        "barcode": barcode,
    }


class MyFriendlyListView(generics.ListAPIView):
    """Friendlies the signed-in Player is the Captain of, today (South African date) or
    later, soonest first."""

    serializer_class = MyFriendlySerializer
    permission_classes = [IsPlayer]
    pagination_class = None

    def get_queryset(self):
        return (
            FriendlyFee.objects.filter(
                captain=self.request.user,
                fixture__status=Fixture.Status.FRIENDLY,
                fixture__kick_off__gte=start_of_today(),
            )
            .select_related(
                "fallback",
                "fixture__club",
                "fixture__home_team",
                "fixture__away_team",
                "fixture__pitch",
            )
            .order_by("fixture__kick_off", "pk")
        )

    def list(self, request, *args, **kwargs):
        rows = []
        for friendly in self.get_queryset():
            if not friendlies.is_on(friendly.fixture, friendly.fallback):
                continue
            totals = friendlies.totals(friendly)
            rows.append(
                {
                    "fixture": friendly.fixture,
                    "club": friendly.fixture.club,
                    "settled": totals.settled,
                    "outstanding": totals.outstanding,
                }
            )
        return Response(MyFriendlySerializer(rows, many=True).data)
