from django.utils import timezone
from rest_framework import serializers

from clubs.models import Night, Season
from clubs.serializers import ClubSummarySerializer
from teams.serializers import NamedSerializer

from .imports import Action
from .models import Fixture, FixtureTransition


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


class AdminFixtureDetailSerializer(AdminFixtureSerializer):
    transitions = FixtureTransitionSerializer(many=True, read_only=True)

    class Meta(AdminFixtureSerializer.Meta):
        fields = [*AdminFixtureSerializer.Meta.fields, "transitions"]


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
