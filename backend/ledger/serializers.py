from rest_framework import serializers

from clubs.serializers import ClubSummarySerializer
from teams.serializers import NamedSerializer

from .models import LedgerEntry

MONEY = {"max_digits": 10, "decimal_places": 2, "read_only": True}


class LedgerEntrySerializer(serializers.ModelSerializer):
    """One ledger line. Amounts are rand, above zero; `kind` says which way it goes."""

    amount = serializers.DecimalField(**MONEY)
    method = serializers.ChoiceField(
        choices=LedgerEntry.Method.choices,
        allow_blank=True,
        read_only=True,
        help_text="Card, cash or credit for payments and refunds; empty otherwise.",
    )
    player = NamedSerializer(
        source="user", read_only=True, allow_null=True, help_text="The Player or Booking User."
    )
    team = NamedSerializer(read_only=True, allow_null=True)
    recorded_by_name = serializers.CharField(
        source="recorded_by.name",
        read_only=True,
        allow_null=True,
        default=None,
        help_text="Empty when the app recorded it.",
    )
    reverses_id = serializers.IntegerField(read_only=True, allow_null=True)
    fixture_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = LedgerEntry
        fields = [
            "id",
            "created_at",
            "kind",
            "method",
            "category",
            "amount",
            "subject",
            "team",
            "player",
            "fixture_id",
            "reverses_id",
            "reason",
            "recorded_by_name",
        ]
        read_only_fields = fields


class PaidByMethodSerializer(serializers.Serializer):
    card = serializers.DecimalField(**MONEY)
    cash = serializers.DecimalField(**MONEY)
    credit = serializers.DecimalField(**MONEY)


class TeamBalanceSerializer(serializers.Serializer):
    team = NamedSerializer(read_only=True)
    due = serializers.DecimalField(**MONEY, help_text="Charges, less their reversals.")
    paid = serializers.DecimalField(**MONEY, help_text="Payments, less refunds and reversals.")
    outstanding = serializers.DecimalField(
        **MONEY, help_text="Due less paid. Below zero when the Team has paid more."
    )
    paid_by_method = PaidByMethodSerializer(read_only=True)
    entries = LedgerEntrySerializer(many=True, read_only=True)


class CreditSerializer(serializers.Serializer):
    balance = serializers.DecimalField(**MONEY)
    entries = LedgerEntrySerializer(
        many=True, read_only=True, help_text="Credits, credit spent, and their reversals."
    )


class TeamCreditSerializer(CreditSerializer):
    team = NamedSerializer(read_only=True)


class ClubCreditSerializer(CreditSerializer):
    club = ClubSummarySerializer(read_only=True)
