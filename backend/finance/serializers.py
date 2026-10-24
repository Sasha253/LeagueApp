"""Finance tracker responses. Every amount is Decimal rand, computed from the ledger."""

from rest_framework import serializers

from clubs.models import Night
from ledger.serializers import LedgerEntrySerializer, PaidByMethodSerializer
from teams.serializers import NamedSerializer

MONEY = {"max_digits": 12, "decimal_places": 2, "read_only": True}


class FinanceNightSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    weekday = serializers.ChoiceField(choices=Night.Weekday.choices, read_only=True)


class IncomeLineSerializer(serializers.Serializer):
    card = serializers.DecimalField(**MONEY, help_text="Card taken, less refunds and reversals.")
    cash = serializers.DecimalField(**MONEY, help_text="Cash taken, less refunds and reversals.")
    received = serializers.DecimalField(**MONEY, help_text="Card plus cash: money taken in.")
    credit_spent = serializers.DecimalField(
        **MONEY, help_text="Paid from credit. Not new money, so not in `received`."
    )
    returned_as_credit = serializers.DecimalField(
        **MONEY, help_text="Given back as credit from these payments, less reversals."
    )


class LeagueFiguresSerializer(serializers.Serializer):
    teams = serializers.IntegerField(read_only=True, help_text="Active Teams.")
    expected = serializers.DecimalField(
        **MONEY, help_text="League fees charged (Teams x fee), less reversals."
    )
    outstanding = serializers.DecimalField(
        **MONEY, help_text="What Teams still owe; a Team that paid more owes nothing."
    )
    team_credit_held = serializers.DecimalField(**MONEY, help_text="Unspent Team credit.")
    league = IncomeLineSerializer(read_only=True)
    friendly = IncomeLineSerializer(read_only=True)


class DivisionFiguresSerializer(LeagueFiguresSerializer):
    division = NamedSerializer(read_only=True)


class NightFiguresSerializer(LeagueFiguresSerializer):
    night = FinanceNightSerializer(read_only=True)
    divisions = DivisionFiguresSerializer(many=True, read_only=True)


class CreditHeldSerializer(serializers.Serializer):
    team = serializers.DecimalField(**MONEY, help_text="Unspent credit of the Teams in scope.")
    player = serializers.DecimalField(
        **MONEY, allow_null=True, help_text="All Players' credit at the Club. Null if filtered."
    )
    booking_user = serializers.DecimalField(
        **MONEY,
        allow_null=True,
        help_text="All Booking Users' credit at the Club. Null if filtered.",
    )


class SeasonSummarySerializer(serializers.Serializer):
    season = NamedSerializer(read_only=True)
    night = FinanceNightSerializer(read_only=True, allow_null=True)
    division = NamedSerializer(read_only=True, allow_null=True)
    received = serializers.DecimalField(
        **MONEY, help_text="League, friendly and (unfiltered) booking money taken in."
    )
    totals = LeagueFiguresSerializer(read_only=True)
    booking = IncomeLineSerializer(
        read_only=True,
        allow_null=True,
        help_text="Bookings starting in the Season's dates. Null with a Night or Division filter.",
    )
    credit_held = CreditHeldSerializer(read_only=True)
    nights = NightFiguresSerializer(many=True, read_only=True)


class NightIncomeSerializer(serializers.Serializer):
    night = FinanceNightSerializer(read_only=True)
    league = IncomeLineSerializer(read_only=True)
    friendly = IncomeLineSerializer(read_only=True)


class SeasonIncomeSerializer(serializers.Serializer):
    season = NamedSerializer(read_only=True)
    received = serializers.DecimalField(**MONEY, help_text="All money taken in this Season.")
    league = IncomeLineSerializer(read_only=True, source="totals.league")
    friendly = IncomeLineSerializer(read_only=True, source="totals.friendly")
    booking = IncomeLineSerializer(read_only=True)
    nights = NightIncomeSerializer(many=True, read_only=True)


class TeamLedgerSerializer(serializers.Serializer):
    team = NamedSerializer(read_only=True)
    season = NamedSerializer(read_only=True)
    division = NamedSerializer(read_only=True)
    night = FinanceNightSerializer(read_only=True)
    due = serializers.DecimalField(**MONEY, help_text="Charges, less their reversals.")
    paid = serializers.DecimalField(**MONEY, help_text="Card, cash and credit paid, net.")
    outstanding = serializers.DecimalField(
        **MONEY, help_text="Due less paid. Below zero when the Team has paid more."
    )
    paid_by_method = PaidByMethodSerializer(read_only=True)
    is_paid = serializers.BooleanField(read_only=True)
    team_credit_held = serializers.DecimalField(**MONEY)
    entries = LedgerEntrySerializer(
        many=True, read_only=True, help_text="Every line on the Team's account, newest first."
    )
