from django.contrib import admin

from .models import LedgerEntry


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    """Read-only (FR-50): entries are added through the app, never edited or deleted."""

    list_display = ["created_at", "club", "kind", "method", "category", "amount", "subject"]
    list_filter = ["kind", "method", "category", "club"]
    list_select_related = ["club"]
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
