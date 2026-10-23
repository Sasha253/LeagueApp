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


class PaymentSerializer(serializers.ModelSerializer):
    """A Player's contribution: credit spent at once, the rest by card at the gateway."""

    team = NamedSerializer(read_only=True)
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


class GatewayNotificationFieldsSerializer(serializers.Serializer):
    """The gateway's form fields (PayFast ITN), as it sends them."""

    m_payment_id = serializers.CharField()
    pf_payment_id = serializers.CharField()
    payment_status = serializers.CharField()
    amount_gross = serializers.CharField()
    merchant_id = serializers.CharField()
    signature = serializers.CharField()
