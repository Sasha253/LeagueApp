from django.contrib import admin

from .models import (
    ConfirmationAnswer,
    Fixture,
    FixtureCheckpoint,
    FixtureFallback,
    FixtureTransition,
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
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
