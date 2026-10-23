from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.models import PlayerProfile
from clubs.models import Night, Season
from clubs.serializers import ClubSummarySerializer
from ledger.serializers import MONEY
from teams.serializers import NamedSerializer

from .imports import Action
from .models import (
    ConfirmationAnswer,
    Fixture,
    FixtureTransition,
    ReplacementOffer,
    TeamReadiness,
)
from .readiness import Decision


class FixtureSerializer(serializers.ModelSerializer):
    """A Fixture as a Player in one of its Teams sees it."""

    club = ClubSummarySerializer(read_only=True)
    season = NamedSerializer(read_only=True)
    division = NamedSerializer(read_only=True)
    weekday = serializers.ChoiceField(
        source="division.night.weekday",
        choices=Night.Weekday.choices,
        read_only=True,
        help_text="The Night: 0 is Monday.",
    )
    pitch = NamedSerializer(read_only=True)
    home_team = NamedSerializer(read_only=True)
    away_team = NamedSerializer(read_only=True)
    kick_off = serializers.DateTimeField(
        read_only=True,
        help_text="Stored in UTC; sent with its offset. Show it in Africa/Johannesburg.",
    )

    class Meta:
        model = Fixture
        fields = [
            "id",
            "club",
            "season",
            "division",
            "weekday",
            "pitch",
            "kick_off",
            "home_team",
            "away_team",
            "friendly_eligible",
            "status",
        ]
        read_only_fields = fields


class MyFixtureSerializer(FixtureSerializer):
    my_team_id = serializers.SerializerMethodField(
        help_text="The signed-in Player's Team in this Fixture."
    )

    class Meta(FixtureSerializer.Meta):
        fields = [*FixtureSerializer.Meta.fields, "my_team_id"]
        read_only_fields = fields

    def get_my_team_id(self, fixture: Fixture) -> int | None:
        mine = self.context.get("my_team_ids", set())
        for team_id in (fixture.home_team_id, fixture.away_team_id):
            if team_id in mine:
                return team_id
        return None


class FixtureTransitionSerializer(serializers.ModelSerializer):
    from_status = serializers.ChoiceField(
        choices=Fixture.Status.choices,
        allow_blank=True,
        read_only=True,
        help_text="Empty for the Fixture's creation.",
    )
    actor_name = serializers.CharField(
        source="actor.name", read_only=True, allow_null=True, default=None
    )

    class Meta:
        model = FixtureTransition
        fields = ["id", "from_status", "to_status", "at", "cause", "actor_name", "note"]
        read_only_fields = fields


class AdminFixtureSerializer(FixtureSerializer):
    """A Fixture as the club's Admin sees it. FriendlyEligibleSerializer changes it."""

    referee_name = serializers.CharField(
        source="pitch.referee.name", read_only=True, allow_null=True, default=None
    )
    friendly_eligible_changed_by_name = serializers.CharField(
        source="friendly_eligible_changed_by.name", read_only=True, allow_null=True, default=None
    )

    class Meta(FixtureSerializer.Meta):
        fields = [
            *FixtureSerializer.Meta.fields,
            "referee_name",
            "friendly_eligible_changed_by_name",
            "friendly_eligible_changed_at",
            "created_at",
        ]
        read_only_fields = fields


class ReplacementOfferSerializer(serializers.ModelSerializer):
    """A search for a new opponent once one Team was out (FR-13 to FR-16), as the Admin sees it."""

    out_team = NamedSerializer(read_only=True)
    remaining_team = NamedSerializer(read_only=True)
    accepted_team = NamedSerializer(read_only=True, allow_null=True)
    accepted_by_name = serializers.CharField(
        source="accepted_by.name", read_only=True, allow_null=True, default=None
    )
    offered_to = serializers.SerializerMethodField(help_text="The Teams the slot was offered to.")

    class Meta:
        model = ReplacementOffer
        fields = [
            "id",
            "kick_off",
            "status",
            "slot",
            "out_team",
            "remaining_team",
            "opened_at",
            "closes_at",
            "offered_to",
            "accepted_team",
            "accepted_by_name",
            "accepted_at",
            "ended_at",
        ]
        read_only_fields = fields

    @extend_schema_field(NamedSerializer(many=True))
    def get_offered_to(self, offer: ReplacementOffer) -> list[dict]:
        return NamedSerializer([c.team for c in offer.candidates.all()], many=True).data


class AdminFixtureDetailSerializer(AdminFixtureSerializer):
    transitions = FixtureTransitionSerializer(many=True, read_only=True)
    replacements = ReplacementOfferSerializer(
        many=True, read_only=True, help_text="Searches for a new opponent, oldest first."
    )

    class Meta(AdminFixtureSerializer.Meta):
        fields = [*AdminFixtureSerializer.Meta.fields, "transitions", "replacements"]


class FriendlyEligibleSerializer(serializers.Serializer):
    friendly_eligible = serializers.BooleanField()


class FixtureImportUploadSerializer(serializers.Serializer):
    season = serializers.PrimaryKeyRelatedField(
        queryset=Season.objects.all(), help_text="The Season every row is for."
    )
    file = serializers.FileField(help_text="An .xlsx or .csv file, up to 5 MB and 500 rows.")

    def validate_season(self, season: Season) -> Season:
        if season.club_id != self.context["club"].pk:
            raise serializers.ValidationError("This Season belongs to another club.")
        if season.ends_on < timezone.localdate():
            raise serializers.ValidationError("This Season has ended.")
        return season


class FixtureImportRowSerializer(serializers.Serializer):
    row = serializers.IntegerField(help_text="The spreadsheet's row number; the header is 1.")
    kick_off = serializers.DateTimeField(allow_null=True)
    night = serializers.ChoiceField(choices=Night.Weekday.choices, allow_null=True)
    division = serializers.CharField(allow_blank=True)
    pitch = serializers.CharField(allow_blank=True)
    home = serializers.CharField(allow_blank=True)
    away = serializers.CharField(allow_blank=True)
    friendly_eligible = serializers.BooleanField(
        allow_null=True, help_text="What the Fixture will have after the import."
    )
    action = serializers.ChoiceField(choices=Action.choices)
    changes = serializers.ListField(
        child=serializers.ChoiceField(choices=["friendly_eligible"]),
        help_text="What an update changes.",
    )
    errors = serializers.ListField(child=serializers.CharField())


class FixtureImportSummarySerializer(serializers.Serializer):
    rows = serializers.IntegerField()
    fixtures_created = serializers.IntegerField()
    fixtures_updated = serializers.IntegerField()
    unchanged = serializers.IntegerField()
    errors = serializers.IntegerField()


class FixtureImportResultSerializer(serializers.Serializer):
    committed = serializers.BooleanField(help_text="True once the import has been saved.")
    summary = FixtureImportSummarySerializer()
    rows = FixtureImportRowSerializer(many=True)


class FixtureAnswerSerializer(serializers.Serializer):
    answer = serializers.ChoiceField(
        choices=ConfirmationAnswer.Value.choices, help_text="confirm: playing; decline: not."
    )


class SquadPlayerSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    position = serializers.ChoiceField(
        choices=PlayerProfile.Position.choices, allow_blank=True, read_only=True
    )
    is_captain = serializers.BooleanField(read_only=True)
    is_me = serializers.SerializerMethodField()
    answer = serializers.ChoiceField(
        choices=ConfirmationAnswer.Value.choices,
        allow_blank=True,
        read_only=True,
        help_text="Empty: not answered yet.",
    )
    answered_at = serializers.DateTimeField(read_only=True, allow_null=True)

    def get_is_me(self, player) -> bool:
        return player.id == self.context["me"].pk


class SquadSerializer(serializers.Serializer):
    """The signed-in Player's Team for one Fixture: who is playing (FR-38)."""

    fixture_id = serializers.IntegerField(source="fixture.pk", read_only=True)
    team = NamedSerializer(read_only=True)
    min_players = serializers.IntegerField(read_only=True, help_text="The Division's minimum.")
    confirmed = serializers.IntegerField(read_only=True)
    declined = serializers.IntegerField(read_only=True)
    waiting = serializers.IntegerField(read_only=True, help_text="Not answered yet.")
    below_minimum = serializers.BooleanField(
        read_only=True, help_text="Fewer confirmed than the minimum: out at T-6h if it stays."
    )
    short_by = serializers.IntegerField(read_only=True)
    answer_by = serializers.DateTimeField(
        read_only=True, help_text="The cutoff (T-6h): no answers or changes after it."
    )
    replies_open = serializers.BooleanField(
        read_only=True, help_text="Answers can be given or changed now."
    )
    my_answer = serializers.SerializerMethodField()
    players = SquadPlayerSerializer(many=True, read_only=True)

    @extend_schema_field(
        serializers.ChoiceField(choices=ConfirmationAnswer.Value.choices, allow_blank=True)
    )
    def get_my_answer(self, squad) -> str:
        me = self.context["me"].pk
        return next((p.answer for p in squad.players if p.id == me), "")


# The T-6h readiness check (FR-5, FR-6)


class TeamReadinessSerializer(serializers.ModelSerializer):
    """What the T-6h check decided for a Team, and the Admin's ruling if it waited for one."""

    decided_by_name = serializers.CharField(
        source="decided_by.name", read_only=True, allow_null=True, default=None
    )
    outstanding = serializers.DecimalField(
        **MONEY, help_text="What the Team still owed at the check, in rand."
    )

    class Meta:
        model = TeamReadiness
        fields = [
            "id",
            "outcome",
            "reason",
            "checked_at",
            "confirmed",
            "min_players",
            "outstanding",
            "decided_by_name",
            "decided_at",
            "note",
        ]
        read_only_fields = fields


class TonightTeamSerializer(serializers.Serializer):
    team = NamedSerializer(read_only=True)
    confirmed = serializers.IntegerField(read_only=True, help_text="Players confirmed now.")
    min_players = serializers.IntegerField(read_only=True, help_text="The Division's minimum.")
    below_minimum = serializers.BooleanField(read_only=True)
    due = serializers.DecimalField(**MONEY, help_text="What the Team has been charged.")
    paid = serializers.DecimalField(**MONEY)
    outstanding = serializers.DecimalField(
        **MONEY, help_text="Due less paid, now. Above zero: the Team owes money."
    )
    unpaid = serializers.BooleanField(read_only=True)
    readiness = TeamReadinessSerializer(
        read_only=True, allow_null=True, help_text="Empty until the T-6h check has run."
    )


class TonightFixtureSerializer(serializers.Serializer):
    fixture = AdminFixtureSerializer(read_only=True)
    checked = serializers.BooleanField(
        read_only=True, help_text="The T-6h check has run for this kick-off."
    )
    waiting = serializers.BooleanField(
        read_only=True, help_text="A Team waits for the Admin's ruling."
    )
    at_risk = serializers.BooleanField(
        read_only=True,
        help_text="Needs the Admin: a Team waits for a ruling, or the check is still to "
        "come and a Team is below the minimum or owes money.",
    )
    teams = TonightTeamSerializer(many=True, read_only=True, help_text="Home first.")


class ReadinessDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=Decision.choices)
    note = serializers.CharField(max_length=300, allow_blank=True, required=False)
