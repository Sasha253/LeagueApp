from django.contrib import admin

from .models import JoinRequest, Team, TeamMembership


class TeamMembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 0
    raw_id_fields = ["player"]


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ["name", "club", "season", "division", "captain", "status"]
    list_filter = ["status", "club"]
    search_fields = ["name"]
    raw_id_fields = ["captain", "requested_by", "decided_by"]
    inlines = [TeamMembershipInline]


@admin.register(JoinRequest)
class JoinRequestAdmin(admin.ModelAdmin):
    list_display = ["player", "team", "status", "created_at"]
    list_filter = ["status"]
    raw_id_fields = ["player", "team", "decided_by"]
