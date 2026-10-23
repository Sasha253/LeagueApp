from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from teams.serializers import NamedSerializer

from .models import Payment
from .services import checkout_for

MONEY = {"max_digits": 10, "decimal_places": 2, "read_only": True}


class CheckoutFieldSerializer(serializers.Serializer):
    name = serializers.CharField(read_only=True)
    value = serializers.CharField(read_only=True)


class CheckoutSerializer(serializers.Serializer):
    """The gateway's hosted payment page. Card details are typed there, never in the app."""

    url = serializers.CharField(read_only=True, help_text="Open this link to pay.")
    action = serializers.CharField(
        read_only=True, help_text="Or post `form_fields`, in this order, to this URL."
    )
    form_fields = CheckoutFieldSerializer(many=True, read_only=True)


def checkout_data(checkout) -> dict:
    return CheckoutSerializer(
        {
            "url": checkout.url,
            "action": checkout.action,
            "form_fields": [{"name": name, "value": value} for name, value in checkout.fields],
        }
    ).data


class PaidBookingSerializer(serializers.Serializer):
    """The Booking a payment is for."""

    id = serializers.IntegerField(read_only=True)
    field = NamedSerializer(read_only=True)
    starts_at = serializers.DateTimeField(
        read_only=True, help_text="Stored in UTC; show it in Africa/Johannesburg."
    )
    hours = serializers.IntegerField(read_only=True)


class PaymentSerializer(serializers.ModelSerializer):
    """A contribution towards a Team (a Player) or a Booking (its Booking User): credit
    spent at once, the rest by card at the gateway."""

    team = NamedSerializer(read_only=True, allow_null=True, help_text="Empty for a booking.")
    booking = PaidBookingSerializer(
        read_only=True, allow_null=True, help_text="Empty for a Team's payment."
    )
    amount = serializers.DecimalField(**MONEY)
    credit_amount = serializers.DecimalField(**MONEY)
    card_amount = serializers.DecimalField(**MONEY)
    checkout = serializers.SerializerMethodField(
        help_text="Where to pay the card part; empty unless the payment is pending."
    )

    class Meta:
        model = Payment
        fields = [
            "reference",
            "team",
            "booking",
            "amount",
            "credit_used",
            "credit_amount",
            "card_amount",
            "provider",
            "status",
            "created_at",
            "completed_at",
            "checkout",
        ]
        read_only_fields = fields

    @extend_schema_field(CheckoutSerializer(allow_null=True))
    def get_checkout(self, payment):
        checkout = checkout_for(payment)
        return checkout_data(checkout) if checkout else None


class StartPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        help_text="How much this Player pays towards the Team, in rand (FR-19).",
    )
    credit = serializers.ChoiceField(
        choices=Payment.Credit.choices,
        default=Payment.Credit.NONE,
        help_text="Spend credit first: the Player's own, or the Team's (Captain only).",
    )


class PaymentOptionsSerializer(serializers.Serializer):
    """What a Player needs to choose a contribution. Amounts are decided by the backend."""

    team = NamedSerializer(read_only=True)
    due = serializers.DecimalField(**MONEY)
    outstanding = serializers.DecimalField(**MONEY)
    is_paid = serializers.BooleanField(read_only=True)
    card_enabled = serializers.BooleanField(
        read_only=True, help_text="Whether the club takes card payments now."
    )
    minimum_card_amount = serializers.DecimalField(**MONEY, allow_null=True)
    suggested_amount = serializers.DecimalField(
        **MONEY,
        allow_null=True,
        help_text="Where the amount starts: this Player's share less what they have paid, "
        "up to what is owed. Empty when nothing is owed.",
    )
    my_credit = serializers.DecimalField(**MONEY)
    team_credit = serializers.DecimalField(
        **MONEY, allow_null=True, help_text="The Team's credit; only its Captain sees it."
    )


class CashPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    player_id = serializers.IntegerField(
        required=False, allow_null=True, help_text="The Player who paid; empty for the Team."
    )
    reason = serializers.CharField(required=False, allow_blank=True, max_length=300)


class TeamPaymentStatusSerializer(serializers.Serializer):
    """One Team's payment status, for its club's Admins (FR-21)."""

    team = NamedSerializer(read_only=True)
    season = NamedSerializer(read_only=True)
    division = NamedSerializer(read_only=True)
    due = serializers.DecimalField(**MONEY)
    paid = serializers.DecimalField(**MONEY)
    outstanding = serializers.DecimalField(**MONEY)
    is_paid = serializers.BooleanField(read_only=True)


class PlayerPaidSerializer(serializers.Serializer):
    player_id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    is_captain = serializers.BooleanField(read_only=True)
    in_team = serializers.BooleanField(
        read_only=True, help_text="False for a Player who paid and has since left."
    )
    paid = serializers.DecimalField(**MONEY, help_text="Net of refunds and reversals.")
    has_paid = serializers.BooleanField(read_only=True)


class TeamPaymentSummarySerializer(serializers.Serializer):
    """Who has paid towards a Team (FR-21), for its Captain and its club's Admins."""

    team = NamedSerializer(read_only=True)
    due = serializers.DecimalField(**MONEY)
    paid = serializers.DecimalField(**MONEY)
    outstanding = serializers.DecimalField(**MONEY)
    is_paid = serializers.BooleanField(read_only=True)
    players = PlayerPaidSerializer(many=True, read_only=True)
    paid_for_team = serializers.DecimalField(
        **MONEY, help_text="Paid for the whole Team: Team credit, or cash for the Team."
    )
    team_credit = serializers.DecimalField(
        **MONEY, allow_null=True, help_text="The Team's credit; only its Captain sees it."
    )


class GatewayNotificationFieldsSerializer(serializers.Serializer):
    """The gateway's form fields (PayFast ITN), as it sends them."""

    m_payment_id = serializers.CharField()
    pf_payment_id = serializers.CharField()
    payment_status = serializers.CharField()
    amount_gross = serializers.CharField()
    merchant_id = serializers.CharField()
    signature = serializers.CharField()
