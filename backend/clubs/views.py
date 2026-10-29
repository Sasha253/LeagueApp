"""Club setup (FR-42): the Admin API for a Club's settings, Seasons, Nights, Divisions,
Fields and people. Every URL names the Club, and only that Club's Admins get in.
"""

from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from rest_framework import generics, mixins, viewsets

from accounts.models import ClubInvite, ClubRole
from accounts.permissions import IsClubAdmin, IsClubAdminOrReferee, IsSuperuser
from accounts.serializers import ClubInviteSerializer, ClubMemberSerializer
from core.exceptions import Conflict

from .models import Club, ClubSettings, Division, Field, Night, Season
from .serializers import (
    ClubNightSerializer,
    ClubSettingsSerializer,
    ClubSummarySerializer,
    DivisionSerializer,
    FieldSerializer,
    NewClubSerializer,
    NightSerializer,
    SeasonSerializer,
)

IN_USE = "This is still in use, so it can't be deleted."
LAST_ADMIN = "A club needs at least one Admin."
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class NightListView(generics.ListAPIView):
    """Every club's Nights, for a Player choosing which Nights to get notifications for.

    One Player account can play at any club (docs/DECISIONS.md), so this is not limited to
    one Club. Nights are a public schedule: no Club's private data is in them.
    """

    queryset = Night.objects.select_related("club")
    serializer_class = NightSerializer


class ClubListView(generics.ListCreateAPIView):
    """Every Club in the app, for a superuser choosing which Club to open. A superuser also
    adds Clubs here, each with its first Admin (docs/DECISIONS.md)."""

    queryset = Club.objects.all()
    permission_classes = [IsSuperuser]

    def get_serializer_class(self):
        return NewClubSerializer if self.request.method == "POST" else ClubSummarySerializer


class ClubDetailView(generics.RetrieveAPIView):
    """The Club in the URL, for the header of its screens. Its Admins and Referees only."""

    serializer_class = ClubSummarySerializer
    permission_classes = [IsClubAdminOrReferee]

    def get_object(self) -> Club:
        # The permission already checked the Club in the URL.
        return get_object_or_404(Club, pk=self.kwargs["club_id"])


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
