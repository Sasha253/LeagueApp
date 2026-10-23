"""Club setup (FR-42): the Admin API for a Club's settings, Seasons, Nights, Divisions,
Fields and people. Every URL names the Club, and only that Club's Admins get in.
"""

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from accounts.models import ClubInvite, ClubRole
from accounts.permissions import IsClubAdmin
from accounts.serializers import ClubInviteSerializer, ClubMemberSerializer
from core.exceptions import Conflict
from core.tables import TableError, read_table

from . import imports
from .models import Club, ClubSettings, Division, Field, Night, Season
from .serializers import (
    ClubNightSerializer,
    ClubSettingsSerializer,
    DivisionSerializer,
    FieldSerializer,
    ImportResultSerializer,
    ImportUploadSerializer,
    NightSerializer,
    SeasonSerializer,
)

IN_USE = "This is still in use, so it can't be deleted."
LAST_ADMIN = "A club needs at least one Admin."
IMPORT_HAS_ERRORS = "Nothing was imported. Fix the rows with errors and upload the file again."
IMPORT_RACE = "The Nights or Divisions changed while importing. Upload the file again."
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class NightListView(generics.ListAPIView):
    """Every club's Nights, for a Player choosing which Nights to get notifications for.

    One Player account can play at any club (docs/DECISIONS.md), so this is not limited to
    one Club. Nights are a public schedule: no Club's private data is in them.
    """

    queryset = Night.objects.select_related("club")
    serializer_class = NightSerializer


class ClubAdminMixin:
    """For views under /clubs/{club_id}/: only that Club's Admins, only its records.

    `club_field` is the lookup from the model to its Club.
    """

    permission_classes = [IsClubAdmin]
    club_field = "club"

    @cached_property
    def club(self) -> Club:
        return get_object_or_404(Club, pk=self.kwargs["club_id"])

    def get_queryset(self):
        return super().get_queryset().filter(**{f"{self.club_field}_id": self.kwargs["club_id"]})

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if "club_id" in self.kwargs:  # Not while the OpenAPI schema is generated.
            context["club"] = self.club
        return context


class ClubAdminViewSet(ClubAdminMixin, viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch", "delete", "options"]

    def perform_create(self, serializer):
        serializer.save(club=self.club)

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as error:
            raise Conflict(IN_USE) from error


class ClubSettingsView(ClubAdminMixin, generics.RetrieveUpdateAPIView):
    """The Club's configurable values: fees, cutoffs, booking policy and payment mode."""

    queryset = ClubSettings.objects.select_related("updated_by")
    serializer_class = ClubSettingsSerializer
    http_method_names = ["get", "patch", "options"]

    def get_object(self):
        settings = get_object_or_404(self.get_queryset())
        self.check_object_permissions(self.request, settings)
        return settings

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class SeasonViewSet(ClubAdminViewSet):
    queryset = Season.objects.all()
    serializer_class = SeasonSerializer


class NightViewSet(ClubAdminViewSet):
    """The Club's Nights, each with its Divisions. A Night with Divisions can't be deleted."""

    queryset = Night.objects.prefetch_related("divisions__night__club__settings")
    serializer_class = ClubNightSerializer
    http_method_names = ["get", "post", "delete", "options"]


class DivisionViewSet(ClubAdminViewSet):
    queryset = Division.objects.select_related("night__club__settings")
    serializer_class = DivisionSerializer
    club_field = "night__club"

    def perform_create(self, serializer):
        serializer.save()


class FieldViewSet(ClubAdminViewSet):
    queryset = Field.objects.select_related("referee")
    serializer_class = FieldSerializer


class ClubMemberViewSet(
    ClubAdminMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """The Club's Admins and Referees. Removing a Referee takes them off their Fields."""

    queryset = ClubRole.objects.select_related("user").order_by("role", "user__name")
    serializer_class = ClubMemberSerializer

    @transaction.atomic
    def perform_destroy(self, instance: ClubRole):
        if instance.role == ClubRole.Role.ADMIN:
            admins = ClubRole.objects.select_for_update().filter(
                club_id=instance.club_id, role=ClubRole.Role.ADMIN
            )
            if len(admins) <= 1:
                raise Conflict(LAST_ADMIN)
        else:
            Field.objects.filter(club_id=instance.club_id, referee_id=instance.user_id).update(
                referee=None
            )
        instance.delete()


class ClubInviteViewSet(
    ClubAdminMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Invites by email to be an Admin or Referee. Lists and cancels the open invites."""

    queryset = ClubInvite.objects.filter(accepted_at__isnull=True)
    serializer_class = ClubInviteSerializer

    def perform_create(self, serializer):
        serializer.save(club=self.club, invited_by=self.request.user)


class NightDivisionImportView(ClubAdminMixin, generics.GenericAPIView):
    """Reads the uploaded file and plans the import of its Nights and Divisions (FR-39)."""

    serializer_class = ImportUploadSerializer
    parser_classes = [MultiPartParser]

    def plan(self, request) -> imports.Plan:
        upload = self.get_serializer(data=request.data)
        upload.is_valid(raise_exception=True)
        try:
            rows = read_table(upload.validated_data["file"], imports.COLUMNS, imports.REQUIRED)
        except TableError as error:
            raise ValidationError({"file": [str(error)]}) from error
        return imports.plan(self.club, rows)

    def answer(self, import_plan: imports.Plan, *, committed: bool, code=status.HTTP_200_OK):
        body = {"committed": committed, "summary": import_plan.summary, "rows": import_plan.rows}
        return Response(ImportResultSerializer(body).data, status=code)


class NightDivisionImportPreviewView(NightDivisionImportView):
    @extend_schema(
        summary="Preview an import of Nights and Divisions",
        description="Checks every row and says what the import would do. Writes nothing.",
        responses={200: ImportResultSerializer},
    )
    def post(self, request, *args, **kwargs):
        return self.answer(self.plan(request), committed=False)


class NightDivisionImportCommitView(NightDivisionImportView):
    @extend_schema(
        summary="Import Nights and Divisions",
        description=(
            "Checks the file again and saves every row in one transaction. If any row has "
            "an error, nothing is saved and the answer is 400 with the rows and their errors."
        ),
        responses={200: ImportResultSerializer, 400: ImportResultSerializer},
    )
    def post(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                # One import per Club at a time; plan again inside, so it sees the latest.
                Club.objects.select_for_update().get(pk=self.club.pk)
                import_plan = self.plan(request)
                if import_plan.has_errors:
                    return self.answer(
                        import_plan, committed=False, code=status.HTTP_400_BAD_REQUEST
                    )
                imports.apply(self.club, import_plan)
        except IntegrityError as error:
            raise Conflict(IMPORT_RACE) from error
        return self.answer(import_plan, committed=True)


class NightDivisionImportTemplateView(ClubAdminMixin, generics.GenericAPIView):
    @extend_schema(
        summary="Download the Nights and Divisions import template",
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
        response["Content-Disposition"] = f'attachment; filename="nights-and-divisions.{name}"'
        return response
