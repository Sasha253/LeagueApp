from decimal import Decimal

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from barcodes.serializers import BarcodeSerializer
from barcodes.services import State
from clubs.models import Club, Field
from clubs.serializers import ClubSummarySerializer
from teams.serializers import NamedSerializer

from . import money, policy
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
    paid = serializers.SerializerMethodField(help_text="What still stands as paid for it.")
    outstanding = serializers.SerializerMethodField(help_text="What it still owes.")
    payment_due_at = serializers.SerializerMethodField(
        help_text="When payment is taken for it (FR-34). " + UTC_NOTE
    )
    payment_requested = serializers.SerializerMethodField(
        help_text="Payment has been taken for its current time: what is left is due now."
    )
    can_pay = serializers.SerializerMethodField(
        help_text="The Booking User can pay what is left now (credit first, then card)."
    )

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
            "cancelled_by_club",
            "paid",
            "outstanding",
            "payment_due_at",
            "payment_requested",
            "can_pay",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.DecimalField(**MONEY))
    def get_paid(self, booking: Booking):
        return serializers.DecimalField(**MONEY).to_representation(money.paid(booking))

    @extend_schema_field(serializers.DecimalField(**MONEY))
    def get_outstanding(self, booking: Booking):
        return serializers.DecimalField(**MONEY).to_representation(money.outstanding(booking))

    @extend_schema_field(serializers.DateTimeField())
    def get_payment_due_at(self, booking: Booking):
        return serializers.DateTimeField().to_representation(policy.payment_due_at(booking))

    def get_payment_requested(self, booking: Booking) -> bool:
        return booking.payment_requested_at is not None

    def get_can_pay(self, booking: Booking) -> bool:
        return (
            booking.status == Booking.Status.ACCEPTED
            and booking.payment_requested_at is not None
            and booking.ends_at > timezone.now()
            and money.outstanding(booking) > 0
        )

    def get_is_over(self, booking: Booking) -> bool:
        return booking.ends_at <= timezone.now()

    def _open(self, booking: Booking) -> bool:
        return booking.holds_field and booking.starts_at > timezone.now()

    def get_can_cancel(self, booking: Booking) -> bool:
        return self._open(booking)

    def get_can_reschedule(self, booking: Booking) -> bool:
        """Open, and the club's policy allows a move now."""
        return self._open(booking) and policy.reschedule_outcome(booking).allowed


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
    can_club_cancel = serializers.SerializerMethodField(
        help_text="An Admin can cancel it for the club now (before it ends)."
    )
    club_cancel_summary = serializers.SerializerMethodField(
        help_text="What cancelling it for the club would return as credit (the policy)."
    )
    can_record_cash = serializers.SerializerMethodField(
        help_text="It is accepted and still owes money: an Admin can record cash (FR-44)."
    )

    class Meta(BookingSerializer.Meta):
        fields = [
            f
            for f in [
                *BookingSerializer.Meta.fields,
                "user",
                "decided_by",
                "can_decide",
                "can_club_cancel",
                "club_cancel_summary",
                "can_record_cash",
            ]
            if f not in ("can_cancel", "can_reschedule", "can_pay")
        ]
        read_only_fields = fields

    def get_can_decide(self, booking: Booking) -> bool:
        return booking.status == Booking.Status.PENDING and booking.starts_at > timezone.now()

    def get_can_club_cancel(self, booking: Booking) -> bool:
        return booking.holds_field and booking.ends_at > timezone.now()

    def get_club_cancel_summary(self, booking: Booking) -> str:
        if not self.get_can_club_cancel(booking):
            return ""
        return policy.cancel_outcome(booking, by_club=True).summary

    def get_can_record_cash(self, booking: Booking) -> bool:
        return booking.status == Booking.Status.ACCEPTED and money.outstanding(booking) > 0


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


class ClubCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(
        max_length=300, help_text="Why the club cancels (pitch, weather, ...). Told to the user."
    )


class BookingCashSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    reason = serializers.CharField(required=False, allow_blank=True, max_length=300, default="")


class PolicyRowSerializer(serializers.Serializer):
    """One row of the club's cancellation and refund policy (FR-45)."""

    window = serializers.ChoiceField(choices=policy.POLICY_WINDOWS.choices, read_only=True)
    when = serializers.CharField(read_only=True)
    cancel = serializers.CharField(read_only=True, help_text="If the Booking User cancels.")
    reschedule = serializers.CharField(read_only=True, help_text="If the Booking User reschedules.")


class ClubPolicySerializer(serializers.Serializer):
    """A club's booking policy, shown before a booking is requested (FR-45)."""

    club = ClubSummarySerializer(read_only=True)
    payment_cutoff_hours = serializers.IntegerField(
        read_only=True, help_text="Payment is taken this many hours before it starts (FR-34)."
    )
    rows = PolicyRowSerializer(many=True, read_only=True)
    credit = serializers.DecimalField(
        help_text="The Booking User's credit at this club, used before card (FR-46).", **MONEY
    )


class CancelOutcomeSerializer(serializers.Serializer):
    window = serializers.ChoiceField(choices=policy.POLICY_WINDOWS.choices, read_only=True)
    allowed = serializers.BooleanField(read_only=True)
    paid = serializers.DecimalField(**MONEY)
    credit_percent = serializers.IntegerField(read_only=True)
    credit = serializers.DecimalField(help_text="Back as credit, never cash.", **MONEY)
    kept = serializers.DecimalField(help_text="What the club keeps.", **MONEY)
    summary = serializers.CharField(read_only=True)


class RescheduleOutcomeSerializer(serializers.Serializer):
    window = serializers.ChoiceField(choices=policy.POLICY_WINDOWS.choices, read_only=True)
    allowed = serializers.BooleanField(read_only=True)
    reschedules_left = serializers.IntegerField(
        read_only=True, allow_null=True, help_text="Late moves left; empty when unlimited."
    )
    latest_start = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
        help_text="A late move must start by then; empty when any time. " + UTC_NOTE,
    )
    summary = serializers.CharField(read_only=True)


class BookingOutcomeSerializer(serializers.Serializer):
    """What cancelling or moving the Booking now would mean (FR-45), decided here."""

    cancel = CancelOutcomeSerializer(read_only=True)
    reschedule = RescheduleOutcomeSerializer(read_only=True)
    rows = PolicyRowSerializer(many=True, read_only=True)
    credit = serializers.DecimalField(
        help_text="The Booking User's credit at this club, used before card (FR-46).", **MONEY
    )
