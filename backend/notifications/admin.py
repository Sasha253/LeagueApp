from django.contrib import admin

from .models import DeviceToken, Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Read-only: notifications are sent by the app, and answered only by their recipient."""

    list_display = ["created_at", "club", "kind", "recipient", "title", "answer", "push_status"]
    list_filter = ["kind", "push_status", "club"]
    list_select_related = ["club", "recipient"]
    search_fields = ["recipient__email", "title"]
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    """Shows which accounts have devices; the token itself is not shown."""

    list_display = ["user", "platform", "created_at", "last_seen_at"]
    list_filter = ["platform"]
    fields = ["user", "platform", "created_at", "last_seen_at"]
    readonly_fields = fields
    search_fields = ["user__email"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
