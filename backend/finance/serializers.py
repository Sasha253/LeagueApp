"""Finance tracker responses. Every amount is Decimal rand, computed from the ledger."""

from decimal import Decimal

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


# Planner (FR-47)


class PlannerWeekSerializer(serializers.Serializer):
    week = serializers.IntegerField(read_only=True, help_text="Week of the Season, from 1.")
    starts_on = serializers.DateField(read_only=True)
    ends_on = serializers.DateField(read_only=True)
    is_due = serializers.BooleanField(read_only=True, help_text="The week has started.")
    is_current = serializers.BooleanField(read_only=True, help_text="Today is in this week.")
    matches = serializers.IntegerField(read_only=True, help_text="Fixtures, not cancelled.")
    expected = serializers.DecimalField(
        **MONEY, help_text="League fees spread over the week's Fixtures."
    )
    covered = serializers.DecimalField(
        **MONEY, help_text="How much of `expected` Teams have paid (card, cash, credit)."
    )
    short = serializers.DecimalField(
        **MONEY, help_text="Expected less covered once the week is due; else 0."
    )
    received = serializers.DecimalField(**MONEY, help_text="Card and cash taken that week.")


class PlannerSerializer(serializers.Serializer):
    season = NamedSerializer(read_only=True)
    night = FinanceNightSerializer(read_only=True, allow_null=True)
    division = NamedSerializer(read_only=True, allow_null=True)
    current_week = serializers.IntegerField(
        read_only=True, allow_null=True, help_text="The week today is in; null outside it."
    )
    season_expected = serializers.DecimalField(
        **MONEY, help_text="League fees charged: every week plus unscheduled."
    )
    due_to_date = serializers.DecimalField(**MONEY, help_text="Expected in the weeks due.")
    covered_to_date = serializers.DecimalField(**MONEY, help_text="Covered in the weeks due.")
    behind = serializers.DecimalField(**MONEY, help_text="Due to date less covered to date.")
    unscheduled = serializers.DecimalField(
        **MONEY, help_text="Fees of Teams with no Fixtures yet: in no week."
    )
    received = serializers.DecimalField(**MONEY, help_text="Card and cash, every week.")
    weeks = PlannerWeekSerializer(many=True, read_only=True)


# Outstanding list (FR-48)


class PlayerOwedSerializer(serializers.Serializer):
    player = NamedSerializer(read_only=True)
    team = NamedSerializer(read_only=True)
    share = serializers.DecimalField(**MONEY, help_text="Due over the Team's current Players.")
    paid = serializers.DecimalField(**MONEY, help_text="Paid towards the Team, net.")
    owes = serializers.DecimalField(
        **MONEY, help_text="Share less paid, never more than the Team still owes."
    )
    gets_notifications = serializers.BooleanField(
        read_only=True, help_text="Opted into the Team's Night, so Remind reaches them."
    )


class TeamOwedSerializer(serializers.Serializer):
    team = NamedSerializer(read_only=True)
    division = NamedSerializer(read_only=True, source="team.division")
    night = FinanceNightSerializer(read_only=True, source="team.division.night")
    due = serializers.DecimalField(**MONEY)
    paid = serializers.DecimalField(**MONEY)
    outstanding = serializers.DecimalField(**MONEY)
    short_since_week = serializers.IntegerField(
        read_only=True, allow_null=True, help_text="The first planner week not fully paid."
    )
    unpaid_players = serializers.ListField(
        child=serializers.CharField(), read_only=True, help_text="Players who owe, most first."
    )


class OutstandingSerializer(serializers.Serializer):
    season = NamedSerializer(read_only=True)
    night = FinanceNightSerializer(read_only=True, allow_null=True)
    division = NamedSerializer(read_only=True, allow_null=True)
    total = serializers.DecimalField(**MONEY, help_text="What the listed Teams owe.")
    teams = TeamOwedSerializer(many=True, read_only=True, help_text="Largest first.")
    players = PlayerOwedSerializer(many=True, read_only=True, help_text="Largest first.")


class OutstandingRowSerializer(serializers.Serializer):
    team_id = serializers.IntegerField()
    player_id = serializers.IntegerField(
        required=False, allow_null=True, help_text="A Player's row; empty for the Team's."
    )


class MarkCashPaidSerializer(OutstandingRowSerializer):
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        help_text="What the row showed as owed; refused if it has changed.",
    )


class RemindedSerializer(serializers.Serializer):
    sent_to = NamedSerializer(many=True, read_only=True)
    not_reached = NamedSerializer(
        many=True, read_only=True, help_text="Not opted into the Team's Night, so not told."
    )


class ExportQuerySerializer(serializers.Serializer):
    """The accountant export's period (FR-51): South African days, both inclusive."""

    starts_on = serializers.DateField(help_text="The first day, YYYY-MM-DD.")
    ends_on = serializers.DateField(help_text="The last day, YYYY-MM-DD.")
    file_type = serializers.ChoiceField(choices=["xlsx", "csv"], default="xlsx")

    def validate(self, attrs):
        if attrs["ends_on"] < attrs["starts_on"]:
            raise serializers.ValidationError({"ends_on": "On or after the first day."})
        return attrs
