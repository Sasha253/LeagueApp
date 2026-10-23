"""Fixtures: the club's Admin imports and lists them; Players see their own Teams'.

The Admin's views are under /clubs/{club_id}/ and show only that Club's Fixtures. A Player's
account works at every club (docs/DECISIONS.md), so their views are not under a Club; they
show only Fixtures of Teams the Player is in now.
"""

from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q, QuerySet
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from accounts.permissions import IsPlayer
from clubs.models import Club
from clubs.views import XLSX, ClubAdminMixin
from core.exceptions import Conflict
from core.tables import TableError, read_table
from teams.models import Team, TeamMembership

from . import imports, lifecycle
from .models import Fixture, FixtureTransition
from .serializers import (
    AdminFixtureDetailSerializer,
    AdminFixtureSerializer,
    FixtureImportResultSerializer,
    FixtureImportUploadSerializer,
    FriendlyEligibleSerializer,
    MyFixtureSerializer,
)

PAST_LIMIT = 50
IMPORT_RACE = "The Fixtures changed while importing. Upload the file again."


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
    http_method_names = ["get", "patch", "options"]

    def get_serializer_class(self):
        return AdminFixtureDetailSerializer if self.action == "retrieve" else AdminFixtureSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "retrieve":
            return queryset.prefetch_related(
                Prefetch("transitions", queryset=FixtureTransition.objects.select_related("actor"))
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
        self.action = "retrieve"
        return Response(AdminFixtureDetailSerializer(self.get_queryset().get(pk=fixture.pk)).data)


class FixtureImportView(ClubAdminMixin, generics.GenericAPIView):
    """Reads the uploaded file and plans the import of a Season's Fixtures (FR-53)."""

    serializer_class = FixtureImportUploadSerializer
    parser_classes = [MultiPartParser]

    def plan(self, request) -> tuple[imports.Plan, object]:
        upload = self.get_serializer(data=request.data)
        upload.is_valid(raise_exception=True)
        season = upload.validated_data["season"]
        try:
            rows = read_table(upload.validated_data["file"], imports.COLUMNS, imports.REQUIRED)
        except TableError as error:
            raise ValidationError({"file": [str(error)]}) from error
        return imports.plan(self.club, season, rows), season

    def answer(self, import_plan: imports.Plan, *, committed: bool, code=status.HTTP_200_OK):
        body = {"committed": committed, "summary": import_plan.summary, "rows": import_plan.rows}
        return Response(FixtureImportResultSerializer(body).data, status=code)


class FixtureImportPreviewView(FixtureImportView):
    @extend_schema(
        summary="Preview an import of a Season's Fixtures",
        description="Checks every row and says what the import would do. Writes nothing.",
        responses={200: FixtureImportResultSerializer},
    )
    def post(self, request, *args, **kwargs):
        import_plan, _season = self.plan(request)
        return self.answer(import_plan, committed=False)


class FixtureImportCommitView(FixtureImportView):
    @extend_schema(
        summary="Import a Season's Fixtures",
        description=(
            "Checks the file again and saves every row in one transaction. If any row has "
            "an error, nothing is saved and the answer is 400 with the rows and their errors."
        ),
        responses={200: FixtureImportResultSerializer, 400: FixtureImportResultSerializer},
    )
    def post(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                # One import per Club at a time; plan again inside, so it sees the latest.
                Club.objects.select_for_update().get(pk=self.club.pk)
                import_plan, season = self.plan(request)
                if import_plan.has_errors:
                    return self.answer(
                        import_plan, committed=False, code=status.HTTP_400_BAD_REQUEST
                    )
                imports.apply(self.club, season, import_plan, request.user)
        except IntegrityError as error:
            raise Conflict(IMPORT_RACE) from error
        return self.answer(import_plan, committed=True)


class FixtureImportTemplateView(ClubAdminMixin, generics.GenericAPIView):
    @extend_schema(
        summary="Download the Fixtures import template",
        parameters=[
            OpenApiParameter("file_type", enum=["xlsx", "csv"], default="xlsx", required=False)
        ],
        responses={
            (200, XLSX): OpenApiResponse(OpenApiTypes.BINARY),
            (200, "text/csv"): OpenApiResponse(OpenApiTypes.BINARY),
        },
    )
    def get(self, request, *args, **kwargs):
        if request.query_params.get("file_type") == "csv":
            body, content_type, name = imports.template_csv(), "text/csv", "csv"
        else:
            body, content_type, name = imports.template_xlsx(), XLSX, "xlsx"
        response = HttpResponse(body, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="fixtures.{name}"'
        return response
