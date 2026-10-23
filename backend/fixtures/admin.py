from django.contrib import admin

from .models import ConfirmationAnswer, Fixture, FixtureCheckpoint, FixtureTransition


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


@admin.register(Fixture)
class FixtureAdmin(admin.ModelAdmin):
    """Read-only: Fixtures change through the app, so every status move is logged."""

    list_display = ["kick_off", "club", "division", "pitch", "home_team", "away_team", "status"]
    list_filter = ["status", "club"]
    inlines = [FixtureTransitionInline, FixtureCheckpointInline, ConfirmationAnswerInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
