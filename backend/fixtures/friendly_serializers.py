"""Friendly fees (FR-24): what an Admin sets and sees, and the Captain's friendlies."""

from decimal import Decimal

from rest_framework import serializers

from accounts.models import User
from barcodes.serializers import BarcodeMatchSerializer, CurrentBarcodeSerializer
from ledger.models import LEDGER_KINDS, LEDGER_METHODS
from teams.serializers import NamedSerializer

from .models import FALLBACK_CAUSES, FRIENDLY_PAYERS

MONEY = {"max_digits": 10, "decimal_places": 2}


class FriendlyTermsSerializer(serializers.Serializer):
    """The fee, who pays it and the Captain, as the Admin sets them."""

    fee = serializers.DecimalField(
        **MONEY,
        min_value=Decimal("0"),
        help_text="The friendly's fee for the whole match, in rand. 0 is free.",
    )
    payer = serializers.ChoiceField(choices=FRIENDLY_PAYERS.choices)
    captain = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        allow_null=True,
        required=False,
        default=None,
        help_text="The Player who receives the friendly's Barcode. Empty: none yet.",
    )


class FriendlyCashSerializer(serializers.Serializer):
    """Cash paid to the club towards the friendly's fee (FR-22, FR-24)."""

    player = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), help_text="The payer who paid it."
    )
    amount = serializers.DecimalField(**MONEY, min_value=Decimal("0.01"))
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class FriendlyFeeSerializer(serializers.Serializer):
    fee = serializers.DecimalField(**MONEY, read_only=True)
    payer = serializers.ChoiceField(choices=FRIENDLY_PAYERS.choices, read_only=True)
    captain = NamedSerializer(read_only=True, allow_null=True)
    set_by = NamedSerializer(read_only=True)
    set_at = serializers.DateTimeField(read_only=True)


class FriendlyPaymentSerializer(serializers.Serializer):
    """A payment towards the friendly's fee, or its reversal (ledger, never changed)."""

    id = serializers.IntegerField(read_only=True)
    kind = serializers.ChoiceField(choices=LEDGER_KINDS.choices, read_only=True)
    method = serializers.ChoiceField(choices=LEDGER_METHODS.choices, read_only=True)
    amount = serializers.DecimalField(**MONEY, read_only=True)
    player = NamedSerializer(source="user", read_only=True)
    recorded_by = NamedSerializer(read_only=True, allow_null=True)
    reason = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class FriendlySerializer(serializers.Serializer):
    """A friendly's fee, who pays it, its Captain and what has been paid (FR-24). All
    amounts and who may do what are decided by the backend."""

    fixture = BarcodeMatchSerializer(read_only=True)
    cause = serializers.ChoiceField(choices=FALLBACK_CAUSES.choices, read_only=True)
    remaining_team = NamedSerializer(
        read_only=True, allow_null=True, help_text="The Team still in; empty when both are out."
    )
    is_on = serializers.BooleanField(
        read_only=True, help_text="Still a friendly for this kick-off."
    )
    can_change = serializers.BooleanField(
        read_only=True, help_text="The Admin can still set the terms (on, before kick-off)."
    )
    money_fixed = serializers.BooleanField(
        read_only=True, help_text="A payment stands, so the fee and payer can't change."
    )
    default_fee = serializers.DecimalField(
        **MONEY,
        read_only=True,
        allow_null=True,
        help_text="The club's friendly fee setting, where the form starts.",
    )
    payer_choices = serializers.ListField(
        child=serializers.ChoiceField(choices=FRIENDLY_PAYERS.choices),
        read_only=True,
        help_text="Who can pay for this friendly (no Team's Players with both Teams out).",
    )
    terms = FriendlyFeeSerializer(read_only=True, allow_null=True, help_text="Empty until set.")
    due = serializers.DecimalField(**MONEY, read_only=True)
    paid = serializers.DecimalField(**MONEY, read_only=True)
    outstanding = serializers.DecimalField(**MONEY, read_only=True)
    settled = serializers.BooleanField(
        read_only=True, help_text="Paid, free or paid by the club: its Barcode can be issued."
    )
    payments = FriendlyPaymentSerializer(many=True, read_only=True)
    payers = NamedSerializer(
        many=True, read_only=True, help_text="Who can pay towards the fee now."
    )
    captain_candidates = NamedSerializer(
        many=True, read_only=True, help_text="Who can be the Captain: anyone playing in it."
    )
    barcode = CurrentBarcodeSerializer(read_only=True)


class MyFriendlySerializer(serializers.Serializer):
    """A friendly the signed-in Player captains."""

    fixture = BarcodeMatchSerializer(read_only=True)
    club = NamedSerializer(read_only=True)
    settled = serializers.BooleanField(read_only=True)
    outstanding = serializers.DecimalField(**MONEY, read_only=True)
