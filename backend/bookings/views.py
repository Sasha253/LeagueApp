"""Bookings API (FR-28 to FR-31).

- Booking Users see the clubs taking bookings and their free times, request a Booking,
  and cancel, reschedule and open their own Bookings and their Barcodes. Anyone else's
  Booking is 404.
- Admins of a club see its Bookings and accept or decline them, under
  /clubs/{club_id}/bookings/. Another club's are 404.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsBookingUser
from barcodes import services as barcodes
from clubs.models import Club, ClubSettings
from clubs.views import ClubAdminMixin
from ledger import services as ledger
from ledger.serializers import LedgerEntrySerializer
from payments import services as payments
from payments.serializers import PaymentSerializer

from . import policy, services
from .models import Booking
from .serializers import (
    AvailabilityQuerySerializer,
    AvailabilitySerializer,
    BookingBarcodeSerializer,
    BookingCashSerializer,
    BookingClubSerializer,
    BookingOutcomeSerializer,
    BookingRequestSerializer,
    BookingSerializer,
    ClubBookingSerializer,
    ClubCancelSerializer,
    ClubPolicySerializer,
    DeclineSerializer,
    SlotSerializer,
)

RELATED = ("club", "field", "user", "decided_by")


class BookingClubListView(generics.ListAPIView):
    """Clubs taking bookings: their Admin has set the hourly fee and match length, and they
    have a field. Club names, fees and field names only."""

    permission_classes = [IsBookingUser]
    serializer_class = BookingClubSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            Club.objects.filter(
                settings__booking_hourly_fee__isnull=False,
                settings__match_length_minutes__isnull=False,
                fields__isnull=False,
            )
            .distinct()
            .select_related("settings")
            .prefetch_related("fields")
            .order_by("name", "pk")
        )


class AvailabilityView(APIView):
    """FR-28: each field's free start times on a day for a number of hours, and the price.
    409 when the club isn't taking bookings."""

    permission_classes = [IsBookingUser]

    @extend_schema(
        parameters=[
            OpenApiParameter("club", int, required=True),
            OpenApiParameter("date", str, required=True, description="2026-10-27"),
            OpenApiParameter("hours", int, required=True),
            OpenApiParameter("booking", int, required=False),
        ],
        responses=AvailabilitySerializer,
    )
    def get(self, request):
        query = AvailabilityQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        given = query.validated_data
        club = get_object_or_404(Club, pk=given["club"])
        exclude = None
        if "booking" in given:
            exclude = get_object_or_404(Booking, pk=given["booking"], user=request.user, club=club)
        found = services.availability(club, given["date"], given["hours"], exclude=exclude)
        return Response(AvailabilitySerializer(found).data)


class PolicyView(APIView):
    """FR-45: a club's booking policy, and the user's credit there, before they book."""

    permission_classes = [IsBookingUser]

    @extend_schema(
        parameters=[OpenApiParameter("club", int, required=True)],
        responses=ClubPolicySerializer,
    )
    def get(self, request):
        club_id = request.query_params.get("club", "")
        if not club_id.isdigit():
            raise ValidationError({"club": ["A club id."]})
        club = get_object_or_404(Club, pk=int(club_id))
        club_settings = ClubSettings.objects.get(club=club)
        data = {
            "club": club,
            "payment_cutoff_hours": club_settings.booking_payment_cutoff_hours,
            "rows": policy.rows(club_settings),
            "credit": ledger.booking_credit(club, request.user),
        }
        return Response(ClubPolicySerializer(data).data)


class MyBookingViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """The signed-in user's own Bookings, soonest first."""

    serializer_class = BookingSerializer
    pagination_class = None

    def get_permissions(self):
        if self.action in ("create", "reschedule", "pay"):
            return [IsBookingUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # While the OpenAPI schema is generated.
            return Booking.objects.none()
        return (
            Booking.objects.filter(user=self.request.user)
            .select_related(*RELATED)
            .order_by("starts_at", "pk")
        )

    def _answer(self, booking: Booking, code=status.HTTP_200_OK) -> Response:
        return Response(self.get_serializer(self.get_queryset().get(pk=booking.pk)).data, code)

    @extend_schema(
        summary="Request a booking",
        description="FR-28: waits for an Admin of the club, who is notified (FR-29). 400 for a "
        "time not on the hour, past, or ending after midnight; 409 when the field is taken "
        "or the club isn't taking bookings.",
        request=BookingRequestSerializer,
        responses={201: BookingSerializer},
    )
    def create(self, request):
        body = BookingRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        given = body.validated_data
        booking = services.request(
            user=request.user,
            club=given["club"],
            field=given["field"],
            starts_at=given["starts_at"],
            hours=given["hours"],
        )
        return self._answer(booking, status.HTTP_201_CREATED)

    @extend_schema(
        summary="Cancel a booking",
        description="FR-31: before it starts. Its Barcode no longer counts. 409 otherwise.",
        request=None,
        responses=BookingSerializer,
    )
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        booking = services.cancel(self.get_object(), by=request.user)
        return self._answer(booking)

    @extend_schema(
        summary="Reschedule a booking",
        description="FR-31: another field, time or number of hours at the same club, before "
        "it starts. It waits for an Admin again.",
        request=SlotSerializer,
        responses=BookingSerializer,
    )
    @action(detail=True, methods=["post"])
    def reschedule(self, request, pk=None):
        booking = self.get_object()
        body = SlotSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        given = body.validated_data
        booking = services.reschedule(
            booking,
            by=request.user,
            field=given["field"],
            starts_at=given["starts_at"],
            hours=given["hours"],
        )
        return self._answer(booking)

    @extend_schema(
        summary="What cancelling or moving it now means",
        description="FR-45: the club's policy, the current window, what a cancellation now "
        "returns as credit, and whether (and how far) it can be moved.",
        responses=BookingOutcomeSerializer,
    )
    @action(detail=True, methods=["get"])
    def outcome(self, request, pk=None):
        booking = self.get_object()
        data = {
            "cancel": policy.cancel_outcome(booking),
            "reschedule": policy.reschedule_outcome(booking),
            "rows": policy.rows(ClubSettings.objects.get(club_id=booking.club_id)),
            "credit": ledger.booking_credit(booking.club, booking.user),
        }
        return Response(BookingOutcomeSerializer(data).data)

    @extend_schema(
        summary="Pay for a booking",
        description="FR-34, FR-46: once payment is due, what is left: the user's credit at "
        "the club first, the rest by card on the gateway's page (`checkout`). 409 before "
        "it is due, when nothing is owed, or when the club takes cash only.",
        request=None,
        responses={201: PaymentSerializer},
    )
    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        payment = payments.start_booking_payment(booking=self.get_object(), user=request.user)
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="The booking's Barcode", responses=BookingBarcodeSerializer)
    @action(detail=True, methods=["get"])
    def barcode(self, request, pk=None):
        barcode, found = barcodes.current_for_booking(self.get_object())
        data = {"state": found.state, "reason": found.reason, "barcode": barcode}
        return Response(BookingBarcodeSerializer(data).data)


class ClubBookingViewSet(
    ClubAdminMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """The club's Bookings, soonest first, for its Admins (filter by `status`)."""

    queryset = Booking.objects.select_related(*RELATED)
    serializer_class = ClubBookingSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            wanted = self.request.query_params.get("status")
            if wanted:
                queryset = queryset.filter(status=wanted)
        return queryset.order_by("starts_at", "pk")

    @extend_schema(parameters=[OpenApiParameter("status", str, required=False)])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def _answer(self, booking: Booking) -> Response:
        return Response(self.get_serializer(self.get_queryset().get(pk=booking.pk)).data)

    @extend_schema(
        summary="Accept a booking",
        description="FR-29, FR-30: a waiting Booking still to come that clashes with nothing. "
        "The Booking User gets the Barcode. 409 otherwise.",
        request=None,
        responses=ClubBookingSerializer,
    )
    @action(detail=True, methods=["post"])
    def accept(self, request, *args, **kwargs):
        return self._answer(services.accept(self.get_object(), by=request.user))

    @extend_schema(
        summary="Decline a booking",
        description="FR-29: a waiting Booking. The user is told, with the reason if given.",
        request=DeclineSerializer,
        responses=ClubBookingSerializer,
    )
    @action(detail=True, methods=["post"])
    def decline(self, request, *args, **kwargs):
        booking = self.get_object()
        body = DeclineSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        booking = services.decline(booking, by=request.user, reason=body.validated_data["reason"])
        return self._answer(booking)

    @extend_schema(
        summary="Cancel a booking for the club",
        description="The policy's club row (pitch, weather, operational): before it ends, "
        "with a reason the user is told. The club's percent of what was paid comes back to "
        "the user as credit.",
        request=ClubCancelSerializer,
        responses=ClubBookingSerializer,
    )
    @action(detail=True, methods=["post"])
    def cancel(self, request, *args, **kwargs):
        booking = self.get_object()
        body = ClubCancelSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        booking = services.club_cancel(
            booking, by=request.user, reason=body.validated_data["reason"]
        )
        return self._answer(booking)

    @extend_schema(
        summary="Record cash for a booking",
        description="FR-44: cash paid to the club for an accepted booking, up to what it "
        "still owes. 409 otherwise.",
        request=BookingCashSerializer,
        responses={201: LedgerEntrySerializer},
    )
    @action(detail=True, methods=["post"])
    def cash(self, request, *args, **kwargs):
        booking = self.get_object()
        body = BookingCashSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        entry = services.record_cash(
            booking,
            by=request.user,
            amount=body.validated_data["amount"],
            reason=body.validated_data["reason"],
        )
        return Response(LedgerEntrySerializer(entry).data, status=status.HTTP_201_CREATED)
