from django.utils import timezone
from rest_framework import serializers

from barcodes.serializers import BarcodeSerializer
from barcodes.services import State
from clubs.models import Club, Field
from clubs.serializers import ClubSummarySerializer
from teams.serializers import NamedSerializer

from .models import BOOKING_STATUSES, MOST_HOURS, Booking

UTC_NOTE = "Stored in UTC; sent with its offset. Show it in Africa/Johannesburg."
MONEY = {"max_digits": 10, "decimal_places": 2, "read_only": True}


class BookingClubSerializer(serializers.ModelSerializer):
    """A club taking bookings, for a Booking User choosing where to play."""

    hourly_fee = serializers.DecimalField(
        source="settings.booking_hourly_fee", help_text="Rand per hour (FR-33).", **MONEY
    )
    fields = NamedSerializer(many=True, read_only=True)

    class Meta:
        model = Club
        fields = ["id", "name", "hourly_fee", "fields"]


class AvailabilityQuerySerializer(serializers.Serializer):
    club = serializers.IntegerField()
    date = serializers.DateField(help_text="A South African date: 2026-10-27.")
    hours = serializers.IntegerField(min_value=1, max_value=MOST_HOURS)
    booking = serializers.IntegerField(
        required=False, help_text="The caller's Booking being rescheduled: its slot counts as free."
    )


class FieldSlotsSerializer(serializers.Serializer):
    field = NamedSerializer(read_only=True)
    starts = serializers.ListField(
        child=serializers.DateTimeField(),
        read_only=True,
        help_text="Free start times for the hours asked. " + UTC_NOTE,
    )


class AvailabilitySerializer(serializers.Serializer):
    date = serializers.DateField(read_only=True)
    hours = serializers.IntegerField(read_only=True)
    hourly_fee = serializers.DecimalField(**MONEY)
    price = serializers.DecimalField(help_text="Hourly fee times hours (FR-33).", **MONEY)
    fields = FieldSlotsSerializer(many=True, read_only=True)


class SlotSerializer(serializers.Serializer):
    field = serializers.PrimaryKeyRelatedField(queryset=Field.objects.all())
    starts_at = serializers.DateTimeField(help_text="On the hour, South African time.")
    hours = serializers.IntegerField(min_value=1, max_value=MOST_HOURS)


class BookingRequestSerializer(SlotSerializer):
    club = serializers.PrimaryKeyRelatedField(queryset=Club.objects.all())


class BookingSerializer(serializers.ModelSerializer):
    """A Booking as its Booking User sees it. What may be done now is decided here."""

    club = ClubSummarySerializer(read_only=True)
    field = NamedSerializer(read_only=True)
    starts_at = serializers.DateTimeField(read_only=True, help_text=UTC_NOTE)
    ends_at = serializers.DateTimeField(read_only=True, help_text=UTC_NOTE)
    status = serializers.ChoiceField(choices=BOOKING_STATUSES.choices, read_only=True)
    is_over = serializers.SerializerMethodField(help_text="It has ended.")
    can_cancel = serializers.SerializerMethodField(help_text="It can be cancelled now.")
    can_reschedule = serializers.SerializerMethodField(help_text="It can be rescheduled now.")

    class Meta:
        model = Booking
        fields = [
            "id",
            "club",
            "field",
            "starts_at",
            "ends_at",
            "hours",
            "hourly_fee",
            "price",
            "status",
            "created_at",
            "decided_at",
            "decline_reason",
            "cancelled_at",
            "is_over",
            "can_cancel",
            "can_reschedule",
        ]
        read_only_fields = fields

    def get_is_over(self, booking: Booking) -> bool:
        return booking.ends_at <= timezone.now()

    def _open(self, booking: Booking) -> bool:
        return booking.holds_field and booking.starts_at > timezone.now()

    def get_can_cancel(self, booking: Booking) -> bool:
        return self._open(booking)

    def get_can_reschedule(self, booking: Booking) -> bool:
        return self._open(booking)


class BookingUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    phone = serializers.CharField(read_only=True)


class ClubBookingSerializer(BookingSerializer):
    """A Booking as an Admin of its club sees it."""

    user = BookingUserSerializer(read_only=True)
    decided_by = NamedSerializer(read_only=True, allow_null=True)
    can_decide = serializers.SerializerMethodField(
        help_text="It is waiting for an Admin and still to come."
    )

    class Meta(BookingSerializer.Meta):
        fields = [
            f
            for f in [*BookingSerializer.Meta.fields, "user", "decided_by", "can_decide"]
            if f not in ("can_cancel", "can_reschedule")
        ]
        read_only_fields = fields

    def get_can_decide(self, booking: Booking) -> bool:
        return booking.status == Booking.Status.PENDING and booking.starts_at > timezone.now()


class DeclineSerializer(serializers.Serializer):
    reason = serializers.CharField(
        max_length=300, required=False, allow_blank=True, default="", help_text="Told to the user."
    )


class BookingBarcodeSerializer(serializers.Serializer):
    """The Booking's Barcode (FR-30), and whether it counts at the gate now and why not."""

    state = serializers.ChoiceField(choices=State.choices, read_only=True)
    reason = serializers.CharField(read_only=True, help_text="Why it doesn't count now.")
    barcode = BarcodeSerializer(
        read_only=True, allow_null=True, help_text="Empty until an Admin accepts the Booking."
    )
