from django.contrib import admin

from .models import Booking, BookingEvent


class BookingEventInline(admin.TabularInline):
    """The log is append-only: shown, never added to, changed or deleted here."""

    model = BookingEvent
    extra = 0
    can_delete = False
    readonly_fields = ["kind", "window", "at", "actor", "field", "starts_at", "hours", "note"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """Read-only: Bookings change only through the app, so every change is logged."""

    list_display = ["field", "user", "starts_at", "hours", "price", "status"]
    list_filter = ["club", "status"]
    inlines = [BookingEventInline]

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in Booking._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
