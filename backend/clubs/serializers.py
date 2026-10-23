from rest_framework import serializers

from accounts.models import ClubRole, User

from .imports import Action
from .models import Club, ClubSettings, Division, Field, Night, Season

PAST_READINESS = "Must be fewer hours before kick-off than the Confirmations."
RESEND_TOO_LATE = "The resend must go out before the readiness check."
LATE_CANCEL_AFTER_CUTOFF = "Must be fewer hours before kick-off than the payment cutoff."


class ClubSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = ["id", "name"]


class NightSerializer(serializers.ModelSerializer):
    club = ClubSummarySerializer(read_only=True)

    class Meta:
        model = Night
        fields = ["id", "club", "weekday"]


class ClubOwnedSerializer(serializers.ModelSerializer):
    """For a record of the Club in the URL. The view puts that Club in the context."""

    @property
    def club(self) -> Club:
        return self.context["club"]

    def unique_in(self, queryset, message: str, **lookup) -> None:
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.filter(**lookup).exists():
            raise serializers.ValidationError(message)


class SeasonSerializer(ClubOwnedSerializer):
    class Meta:
        model = Season
        fields = ["id", "name", "starts_on", "ends_on"]

    def validate_name(self, value: str) -> str:
        self.unique_in(
            self.club.seasons, "This club already has a Season with this name.", name=value
        )
        return value

    def validate(self, attrs):
        starts_on = attrs.get("starts_on", getattr(self.instance, "starts_on", None))
        ends_on = attrs.get("ends_on", getattr(self.instance, "ends_on", None))
        if starts_on and ends_on and ends_on < starts_on:
            raise serializers.ValidationError({"ends_on": "Must be on or after the start."})
        return attrs


class DivisionSerializer(ClubOwnedSerializer):
    night = serializers.PrimaryKeyRelatedField(queryset=Night.objects.none())
    min_players = serializers.IntegerField(
        min_value=1, required=False, help_text="Leave out to use the club's default."
    )
    effective_league_fee = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
        allow_null=True,
        help_text="This Division's fee per Team, else the club's. Null while neither is set.",
    )

    class Meta:
        model = Division
        fields = [
            "id",
            "night",
            "name",
            "min_players",
            "league_fee",
            "effective_league_fee",
            "max_teams",
        ]
        # Unique names per Night are checked in validate(), with the error on `name`.
        validators = []

    def get_fields(self):
        fields = super().get_fields()
        if "club" in self.context:
            fields["night"].queryset = self.club.nights.all()
        return fields

    def validate(self, attrs):
        night = attrs.get("night", getattr(self.instance, "night", None))
        name = attrs.get("name", getattr(self.instance, "name", None))
        if "night" in attrs or "name" in attrs:
            queryset = Division.objects.filter(night=night)
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.filter(name=name).exists():
                raise serializers.ValidationError(
                    {"name": "This Night already has a Division with this name."}
                )
        if self.instance is None and "min_players" not in attrs:
            attrs["min_players"] = self.club.settings.division_min_players
        return attrs


class ClubNightSerializer(ClubOwnedSerializer):
    """A Night with its Divisions, for the Admin's setup screens."""

    divisions = DivisionSerializer(many=True, read_only=True)

    class Meta:
        model = Night
        fields = ["id", "weekday", "divisions"]

    def validate_weekday(self, value: int) -> int:
        self.unique_in(self.club.nights, "This club already has this Night.", weekday=value)
        return value


class FieldSerializer(ClubOwnedSerializer):
    referee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.none(),
        allow_null=True,
        required=False,
        help_text="A user holding the Referee role at this club.",
    )
    referee_name = serializers.CharField(
        source="referee.name", read_only=True, allow_null=True, default=None
    )

    class Meta:
        model = Field
        fields = ["id", "name", "referee", "referee_name"]

    def get_fields(self):
        fields = super().get_fields()
        if "club" in self.context:
            fields["referee"].queryset = User.objects.filter(
                club_roles__club=self.club, club_roles__role=ClubRole.Role.REFEREE
            )
        return fields

    def validate_name(self, value: str) -> str:
        self.unique_in(
            self.club.fields, "This club already has a Field with this name.", name=value
        )
        return value


class ClubSettingsSerializer(serializers.ModelSerializer):
    missing = serializers.ListField(
        child=serializers.CharField(),
        read_only=True,
        help_text="Values the Admin still has to set.",
    )
    updated_by_name = serializers.CharField(
        source="updated_by.name", read_only=True, allow_null=True, default=None
    )

    class Meta:
        model = ClubSettings
        fields = [*ClubSettings.value_names(), "missing", "updated_at", "updated_by_name"]
        read_only_fields = ["updated_at"]

    def validate(self, attrs):
        def value(name):
            return attrs.get(name, getattr(self.instance, name, None))

        errors = {}
        confirmation = value("confirmation_hours_before")
        readiness = value("readiness_hours_before")
        resend = value("confirmation_resend_after_hours")
        if readiness >= confirmation:
            errors["readiness_hours_before"] = PAST_READINESS
        elif resend >= confirmation - readiness:
            errors["confirmation_resend_after_hours"] = RESEND_TOO_LATE
        if value("booking_late_cancel_hours") >= value("booking_payment_cutoff_hours"):
            errors["booking_late_cancel_hours"] = LATE_CANCEL_AFTER_CUTOFF
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class ImportUploadSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="An .xlsx or .csv file, up to 5 MB and 500 rows.")


class ImportRowSerializer(serializers.Serializer):
    row = serializers.IntegerField(help_text="The spreadsheet's row number; the header is 1.")
    night = serializers.ChoiceField(choices=Night.Weekday.choices, allow_null=True)
    division = serializers.CharField(allow_blank=True)
    min_players = serializers.IntegerField(
        allow_null=True, help_text="What the Division will have after the import."
    )
    league_fee = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        allow_null=True,
        help_text="The Division's own fee after the import. Null: the club's fee applies.",
    )
    action = serializers.ChoiceField(choices=Action.choices)
    new_night = serializers.BooleanField(help_text="The import adds this Night to the club.")
    changes = serializers.ListField(
        child=serializers.ChoiceField(choices=["min_players", "league_fee"]),
        help_text="What an update changes.",
    )
    errors = serializers.ListField(child=serializers.CharField())


class ImportSummarySerializer(serializers.Serializer):
    rows = serializers.IntegerField()
    nights_created = serializers.IntegerField()
    divisions_created = serializers.IntegerField()
    divisions_updated = serializers.IntegerField()
    unchanged = serializers.IntegerField()
    errors = serializers.IntegerField()


class ImportResultSerializer(serializers.Serializer):
    committed = serializers.BooleanField(help_text="True once the import has been saved.")
    summary = ImportSummarySerializer()
    rows = ImportRowSerializer(many=True)
