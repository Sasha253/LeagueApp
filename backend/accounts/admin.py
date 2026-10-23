"""Where we set up a new Club's first Admin and its Referees (docs/DECISIONS.md)."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import ClubInvite, ClubRole, PlayerProfile, User


class PlayerProfileInline(admin.StackedInline):
    model = PlayerProfile
    can_delete = True
    filter_horizontal = ["nights"]


class ClubRoleInline(admin.TabularInline):
    model = ClubRole
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "name", "phone", "is_booking_user", "is_staff"]
    search_fields = ["email", "name", "phone"]
    list_filter = ["is_booking_user", "is_staff", "is_active", "club_roles__role"]
    inlines = [PlayerProfileInline, ClubRoleInline]
    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Profile", {"fields": ["name", "phone", "is_booking_user"]}),
        ("Django admin", {"fields": ["is_active", "is_staff", "is_superuser"]}),
    ]
    add_fieldsets = [
        (None, {"classes": ["wide"], "fields": ["email", "name", "password1", "password2"]}),
    ]
    filter_horizontal = []


@admin.register(ClubRole)
class ClubRoleAdmin(admin.ModelAdmin):
    list_display = ["user", "club", "role"]
    list_filter = ["role", "club"]
    search_fields = ["user__email", "user__name"]


@admin.register(ClubInvite)
class ClubInviteAdmin(admin.ModelAdmin):
    list_display = ["email", "club", "role", "created_at", "accepted_at"]
    list_filter = ["role", "club"]
    search_fields = ["email"]
    readonly_fields = ["accepted_at"]
