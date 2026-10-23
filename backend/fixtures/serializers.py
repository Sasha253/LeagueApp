from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.models import PlayerProfile
from clubs.models import Field, Night, Season
from clubs.serializers import ClubSummarySerializer
from ledger.serializers import MONEY
from ledger.services import fixture_credit_returned
from notifications.models import Answer
from teams.serializers import NamedSerializer

from . import borrowing, fallbacks
from .imports import Action
from .models import (
    CaptainRequest,
    ConfirmationAnswer,
    Fixture,
    FixtureFallback,
    FixtureReschedule,
    FixtureTransition,
    PlayerRequest,
    PlayerRequestInvite,
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


class FriendlyPlayerSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="player.pk", read_only=True)
    name = serializers.CharField(source="player.name", read_only=True)
    position = serializers.ChoiceField(
        source="player.player_profile.position",
        choices=PlayerProfile.Position.choices,
        allow_blank=True,
        read_only=True,
        default="",
    )
    joined_at = serializers.DateTimeField(source="notification.answered_at", read_only=True)


class FixtureFallbackSerializer(serializers.ModelSerializer):
    """What became of a match that couldn't go ahead (FR-10 to FR-12, FR-17, FR-43)."""

    remaining_team = NamedSerializer(
        read_only=True, allow_null=True, help_text="Empty when both Teams were out."
    )
    invited = serializers.SerializerMethodField(help_text="Players invited to the friendly.")
    joined = serializers.SerializerMethodField(
        help_text="Invited Players who joined the friendly, by name."
    )
    credit_returned = serializers.SerializerMethodField(
        help_text="Payments for the match returned as credit, in rand (a cancellation)."
    )
    credits = serializers.SerializerMethodField(help_text="How many credit entries that was.")

    class Meta:
        model = FixtureFallback
        fields = [
            "id",
            "kick_off",
            "cause",
            "outcome",
            "remaining_team",
            "decided_at",
            "invited",
            "joined",
            "credit_returned",
            "credits",
        ]
        read_only_fields = fields

    def get_invited(self, fallback: FixtureFallback) -> int:
        return fallback.invites.count()

    @extend_schema_field(FriendlyPlayerSerializer(many=True))
    def get_joined(self, fallback: FixtureFallback) -> list[dict]:
        return FriendlyPlayerSerializer(fallbacks.joined(fallback), many=True).data

    @extend_schema_field(serializers.DecimalField(**MONEY))
    def get_credit_returned(self, fallback: FixtureFallback) -> str:
        total, _count = fixture_credit_returned(fallback.fixture)
        return f"{total:.2f}"

    def get_credits(self, fallback: FixtureFallback) -> int:
        _total, count = fixture_credit_returned(fallback.fixture)
        return count


# Reschedules (FR-7 to FR-9) and Captain requests (FR-18)


class FixtureRescheduleSerializer(serializers.ModelSerializer):
    """An Admin's reschedule of the match, as the Admin sees it."""

    from_pitch = NamedSerializer(read_only=True)
    to_pitch = NamedSerializer(read_only=True)
    by_name = serializers.CharField(source="by.name", read_only=True, allow_null=True, default=None)
    request_id = serializers.IntegerField(
        read_only=True, allow_null=True, help_text="The Captain's postponement it answered."
    )

    class Meta:
        model = FixtureReschedule
        fields = [
            "id",
            "from_kick_off",
            "to_kick_off",
            "from_pitch",
            "to_pitch",
            "at",
            "by_name",
            "note",
            "request_id",
            "confirmations_sent",
            "notified",
        ]
        read_only_fields = fields


class CaptainRequestSerializer(serializers.ModelSerializer):
    """A Captain's request to cancel or postpone a match (FR-18)."""

    team = NamedSerializer(read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.name", read_only=True)
    decided_by_name = serializers.CharField(
        source="decided_by.name", read_only=True, allow_null=True, default=None
    )

    class Meta:
        model = CaptainRequest
        fields = [
            "id",
            "fixture_id",
            "team",
            "kind",
            "reason",
            "kick_off",
            "requested_by_name",
            "requested_at",
            "status",
            "decided_by_name",
            "decided_at",
            "note",
        ]
        read_only_fields = fields


class ClubCaptainRequestSerializer(CaptainRequestSerializer):
    """A Captain's request as the club's Admin sees it in the requests list."""

    fixture = FixtureSerializer(read_only=True)

    class Meta(CaptainRequestSerializer.Meta):
        fields = [*CaptainRequestSerializer.Meta.fields, "fixture"]
        read_only_fields = fields


class CaptainRequestCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=CaptainRequest.Kind.choices)
    reason = serializers.CharField(max_length=300, help_text="Why; the Admin reads it.")


class MatchRequestsSerializer(serializers.Serializer):
    """My Team's requests to cancel or postpone a match, and whether I can send one."""

    is_captain = serializers.BooleanField(help_text="I'm the Captain of my Team in this match.")
    can_request = serializers.BooleanField(
        help_text="I'm the Captain, the match can still change and nothing is waiting."
    )
    requests = CaptainRequestSerializer(many=True, help_text="Newest first.")


class RescheduleSerializer(serializers.Serializer):
    kick_off = serializers.DateTimeField(
        help_text="The new kick-off, with its offset (South African time is +02:00)."
    )
    pitch = serializers.PrimaryKeyRelatedField(
        queryset=Field.objects.all(),
        required=False,
        allow_null=True,
        help_text="The new pitch; the same pitch when left out.",
    )
    note = serializers.CharField(max_length=300, allow_blank=True, required=False)

    def validate_pitch(self, pitch):
        if pitch is not None and pitch.club_id != self.context["club"].pk:
            raise serializers.ValidationError("The club has no such pitch.")
        return pitch


class CaptainRequestAcceptSerializer(RescheduleSerializer):
    kick_off = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="A postponement's new kick-off (required for one), with its offset.",
    )


class CaptainRequestDeclineSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=300, allow_blank=True, required=False)


class ReschedulePreviewSerializer(serializers.Serializer):
    """What a reschedule will do, before the Admin confirms it."""

    kick_off = serializers.DateTimeField()
    pitch = NamedSerializer()
    kick_off_changed = serializers.BooleanField()
    pitch_changed = serializers.BooleanField()
    status_after = serializers.ChoiceField(choices=Fixture.Status.choices)
    confirmations_now = serializers.BooleanField(
        help_text="Within the Confirmation window: they go out at once (FR-9)."
    )
    answer_by = serializers.DateTimeField(
        allow_null=True, help_text="Replies for the new kick-off close then (T-6h)."
    )
    players = serializers.SerializerMethodField(
        help_text="Players of both Teams told (opted into the Night)."
    )
    officials = serializers.SerializerMethodField(
        help_text="The Night's Admins and the affected pitch's Referee told."
    )

    def get_players(self, planned) -> int:
        return len(planned.players)

    def get_officials(self, planned) -> int:
        return len(planned.officials)


class AdminFixtureDetailSerializer(AdminFixtureSerializer):
    transitions = FixtureTransitionSerializer(many=True, read_only=True)
    replacements = ReplacementOfferSerializer(
        many=True, read_only=True, help_text="Searches for a new opponent, oldest first."
    )
    fallback = serializers.SerializerMethodField(
        help_text="A friendly or a cancellation once the match couldn't go ahead; else empty."
    )
    reschedules = FixtureRescheduleSerializer(
        many=True, read_only=True, help_text="The Admin's reschedules, oldest first."
    )
    captain_requests = CaptainRequestSerializer(
        many=True,
        read_only=True,
        help_text="Captains' requests to cancel or postpone, oldest first.",
    )

    class Meta(AdminFixtureSerializer.Meta):
        fields = [
            *AdminFixtureSerializer.Meta.fields,
            "transitions",
            "replacements",
            "fallback",
            "reschedules",
            "captain_requests",
        ]

    @extend_schema_field(FixtureFallbackSerializer(allow_null=True))
    def get_fallback(self, fixture: Fixture) -> dict | None:
        fallback = (
            FixtureFallback.objects.filter(fixture=fixture)
            .select_related("remaining_team", "fixture")
            .first()
        )
        return FixtureFallbackSerializer(fallback).data if fallback else None


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


class SquadBorrowedSerializer(serializers.Serializer):
    """A Player from outside both Teams playing for the Team in this match (FR-37)."""

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    position = serializers.ChoiceField(
        choices=PlayerProfile.Position.choices, allow_blank=True, read_only=True
    )
    kind = serializers.ChoiceField(
        choices=PlayerRequest.Kind.choices, read_only=True, help_text="The request they answered."
    )
    joined_at = serializers.DateTimeField(read_only=True)


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
    borrowed = SquadBorrowedSerializer(
        many=True,
        read_only=True,
        help_text="Borrowed through a Player or Goalkeeper Request; counted as confirmed.",
    )

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


# Player and Goalkeeper Requests (FR-35 to FR-37)


class BorrowedPlayerSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="player.pk", read_only=True)
    name = serializers.CharField(source="player.name", read_only=True)
    joined_at = serializers.DateTimeField(read_only=True)


def _now(context) -> object:
    return context.setdefault("now", timezone.now())


class PlayerRequestSerializer(serializers.ModelSerializer):
    """A Captain's request for borrowed Players, as the Team's Players see it."""

    team = NamedSerializer(read_only=True)
    raised_by_name = serializers.CharField(source="raised_by.name", read_only=True)
    status = serializers.SerializerMethodField(
        help_text="closed: no longer applies (the match moved, or kick-off passed)."
    )
    filled = serializers.SerializerMethodField(help_text="How many places are taken.")
    joined = BorrowedPlayerSerializer(many=True, read_only=True, help_text="Earliest first.")

    class Meta:
        model = PlayerRequest
        fields = [
            "id",
            "fixture_id",
            "team",
            "kind",
            "places",
            "filled",
            "kick_off",
            "raised_by_name",
            "raised_at",
            "status",
            "ended_at",
            "note",
            "notified",
            "joined",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.ChoiceField(choices=PlayerRequest.Status.choices))
    def get_status(self, player_request: PlayerRequest) -> str:
        return borrowing.status_of(player_request, player_request.fixture, _now(self.context))

    def get_filled(self, player_request: PlayerRequest) -> int:
        return len(player_request.joined.all())


class PlayerRequestCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(
        choices=PlayerRequest.Kind.choices,
        help_text="player: outfield Players; goalkeeper: Goalkeepers.",
    )
    places = serializers.IntegerField(
        min_value=1, default=1, help_text="How many; at most the Division's minimum."
    )


class MatchPlayerRequestsSerializer(serializers.Serializer):
    """My Team's requests for borrowed Players, and whether I can raise one."""

    is_captain = serializers.BooleanField(help_text="I'm the Captain of my Team in this match.")
    can_request = serializers.BooleanField(
        help_text="I'm the Captain and the match still takes requests (before kick-off)."
    )
    max_places = serializers.IntegerField(help_text="The most places one request can ask for.")
    requests = PlayerRequestSerializer(many=True, help_text="Newest first.")


class PlayerRequestPreviewQuerySerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=PlayerRequest.Kind.choices)


class PlayerRequestPreviewSerializer(serializers.Serializer):
    """Who a request would go to (Screens.md Captain 4)."""

    kind = serializers.ChoiceField(choices=PlayerRequest.Kind.choices)
    recipients = serializers.IntegerField(
        help_text="Players of that position opted into the Night, in neither Team."
    )
    night = serializers.CharField(help_text="The match's Night, e.g. Tuesday.")
    max_places = serializers.IntegerField()


class MyPlayerRequestSerializer(serializers.Serializer):
    """A request I was sent: a game I can join, or one I joined (Screens.md Player 1)."""

    id = serializers.IntegerField(source="request.pk", read_only=True)
    notification_id = serializers.IntegerField(read_only=True, help_text="Answer it here.")
    kind = serializers.ChoiceField(
        source="request.kind", choices=PlayerRequest.Kind.choices, read_only=True
    )
    team = NamedSerializer(source="request.team", read_only=True, help_text="Who asks.")
    fixture = FixtureSerializer(source="request.fixture", read_only=True)
    places = serializers.IntegerField(source="request.places", read_only=True)
    places_left = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    my_answer = serializers.ChoiceField(
        source="notification.answer",
        choices=Answer.choices,
        allow_blank=True,
        read_only=True,
    )
    joined = serializers.SerializerMethodField(help_text="I have a place in this match.")
    can_answer = serializers.SerializerMethodField(help_text="Accept or Decline is open now.")
    answer_by = serializers.DateTimeField(source="notification.answer_by", read_only=True)

    def get_places_left(self, invite: PlayerRequestInvite) -> int:
        return max(0, invite.request.places - len(invite.request.joined.all()))

    @extend_schema_field(serializers.ChoiceField(choices=PlayerRequest.Status.choices))
    def get_status(self, invite: PlayerRequestInvite) -> str:
        request = invite.request
        return borrowing.status_of(request, request.fixture, _now(self.context))

    def get_joined(self, invite: PlayerRequestInvite) -> bool:
        fixture = invite.request.fixture
        return any(
            p.player_id == invite.player_id and borrowing.still_playing(p, fixture)
            for p in invite.request.joined.all()
        )

    def get_can_answer(self, invite: PlayerRequestInvite) -> bool:
        now = _now(self.context)
        return (
            invite.notification.is_answerable(now)
            and self.get_status(invite) == PlayerRequest.Status.OPEN
            and not self.get_joined(invite)
        )
