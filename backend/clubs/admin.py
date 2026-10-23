"""Where we set up a new Club, and the defaults every new Club starts from."""

from django.contrib import admin

from .models import Club, ClubSettings, Division, Field, Night, Season, SettingsDefaults


class ClubSettingsInline(admin.StackedInline):
    model = ClubSettings
    can_delete = False
    readonly_fields = ["updated_at", "updated_by"]


class NightInline(admin.TabularInline):
    model = Night
    extra = 0


class FieldInline(admin.TabularInline):
    model = Field
    extra = 0
    raw_id_fields = ["referee"]


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]
    inlines = [ClubSettingsInline, NightInline, FieldInline]

    def get_inlines(self, request, obj):
        # A new Club gets its settings from the defaults when it is saved.
        return self.inlines if obj else [NightInline, FieldInline]


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ["name", "club", "starts_on", "ends_on"]
    list_filter = ["club"]


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ["name", "night", "min_players", "league_fee"]
    list_filter = ["night__club"]


@admin.register(SettingsDefaults)
class SettingsDefaultsAdmin(admin.ModelAdmin):
    """The one record new Clubs copy their settings from."""

    def has_add_permission(self, request) -> bool:
        return not SettingsDefaults.objects.exists()

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
