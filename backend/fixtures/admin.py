from django.contrib import admin

from .models import (
    BorrowedPlayer,
    CaptainRequest,
    ConfirmationAnswer,
    Fixture,
    FixtureCheckpoint,
    FixtureFallback,
    FixtureReschedule,
    FixtureTransition,
    FriendlyFee,
    PlayerRequest,
    ReplacementOffer,
    TeamReadiness,
)


class FixtureTransitionInline(admin.TabularInline):
    """The log is append-only: shown, never added to, changed or deleted here."""

    model = FixtureTransition
    extra = 0
    can_delete = False
    readonly_fields = ["from_status", "to_status", "at", "actor", "cause", "note"]

    def has_add_permission(self, request, obj=None):
        return False


class FixtureCheckpointInline(admin.TabularInline):
    """The timed checkpoints that have run: shown, never added to, changed or deleted here."""

    model = FixtureCheckpoint
    extra = 0
    can_delete = False
    readonly_fields = ["kind", "kick_off", "ran_at", "notified"]

    def has_add_permission(self, request, obj=None):
        return False


class ConfirmationAnswerInline(admin.TabularInline):
    """Players' answers: given in the app (FR-3), only shown here."""

    model = ConfirmationAnswer
    extra = 0
    can_delete = False
    readonly_fields = ["player", "team", "answer", "kick_off", "answered_at", "via"]

    def has_add_permission(self, request, obj=None):
        return False


class TeamReadinessInline(admin.TabularInline):
    """The T-6h check and the Admin's rulings: made in the app (FR-5, FR-6), only shown here."""

    model = TeamReadiness
    extra = 0
    can_delete = False
    readonly_fields = [
        "team",
        "kick_off",
        "checked_at",
        "confirmed",
        "min_players",
        "outstanding",
        "outcome",
        "reason",
        "decided_by",
        "decided_at",
        "note",
    ]

    def has_add_permission(self, request, obj=None):
        return False


class ReplacementOfferInline(admin.TabularInline):
    """Searches for a new opponent: made in the app (FR-13 to FR-16), only shown here."""

    model = ReplacementOffer
    extra = 0
    can_delete = False
    readonly_fields = [
        "kick_off",
        "out_team",
        "remaining_team",
        "slot",
        "opened_at",
        "closes_at",
        "status",
        "accepted_team",
        "accepted_by",
        "accepted_at",
        "ended_at",
    ]

    def has_add_permission(self, request, obj=None):
        return False


class FixtureFallbackInline(admin.TabularInline):
    """A friendly or a cancellation: decided in the app (FR-10 to FR-12, FR-17), only shown."""

    model = FixtureFallback
    extra = 0
    can_delete = False
    readonly_fields = ["kick_off", "cause", "remaining_team", "outcome", "decided_at"]

    def has_add_permission(self, request, obj=None):
        return False


class FixtureRescheduleInline(admin.TabularInline):
    """The Admin's reschedules: made in the app (FR-7 to FR-9), only shown here."""

    model = FixtureReschedule
    extra = 0
    can_delete = False
    fk_name = "fixture"
    readonly_fields = [
        "from_kick_off",
        "to_kick_off",
        "from_pitch",
        "to_pitch",
        "at",
        "by",
        "note",
        "request",
        "confirmations_sent",
        "notified",
    ]

    def has_add_permission(self, request, obj=None):
        return False


class CaptainRequestInline(admin.TabularInline):
    """Captains' requests to cancel or postpone: made and decided in the app (FR-18)."""

    model = CaptainRequest
    extra = 0
    can_delete = False
    readonly_fields = [
        "team",
        "kind",
        "reason",
        "kick_off",
        "requested_by",
        "requested_at",
        "status",
        "decided_by",
        "decided_at",
        "note",
    ]

    def has_add_permission(self, request, obj=None):
        return False


class PlayerRequestInline(admin.TabularInline):
    """Captains' Player and Goalkeeper Requests: raised and filled in the app (FR-35 to FR-37)."""

    model = PlayerRequest
    extra = 0
    can_delete = False
    readonly_fields = [
        "team",
        "kind",
        "places",
        "kick_off",
        "raised_by",
        "raised_at",
        "status",
        "ended_at",
        "note",
        "notified",
    ]

    def has_add_permission(self, request, obj=None):
        return False


class BorrowedPlayerInline(admin.TabularInline):
    """Players who joined through a Player or Goalkeeper Request (FR-37)."""

    model = BorrowedPlayer
    extra = 0
    can_delete = False
    readonly_fields = ["request", "team", "kick_off", "player", "joined_at"]

    def has_add_permission(self, request, obj=None):
        return False


class FriendlyFeeInline(admin.TabularInline):
    """A friendly's fee, who pays it and its Captain: set by an Admin in the app (FR-24)."""

    model = FriendlyFee
    extra = 0
    can_delete = False
    readonly_fields = ["fee", "payer", "captain", "set_by", "set_at"]
    exclude = ["fallback"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Fixture)
class FixtureAdmin(admin.ModelAdmin):
    """Read-only: Fixtures change through the app, so every status move is logged."""

    list_display = ["kick_off", "club", "division", "pitch", "home_team", "away_team", "status"]
    list_filter = ["status", "club"]
    inlines = [
        FixtureTransitionInline,
        FixtureCheckpointInline,
        ConfirmationAnswerInline,
        TeamReadinessInline,
        ReplacementOfferInline,
        FixtureFallbackInline,
        FixtureRescheduleInline,
        CaptainRequestInline,
        PlayerRequestInline,
        BorrowedPlayerInline,
        FriendlyFeeInline,
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
