from django.contrib import admin

from .models import GatewayNotification, Payment


class ReadOnlyAdmin(admin.ModelAdmin):
    """Payments and gateway notifications are written only by the app."""

    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(ReadOnlyAdmin):
    list_display = ["created_at", "club", "team", "player", "amount", "card_amount", "status"]
    list_filter = ["status", "provider", "club"]
    list_select_related = ["club", "team", "player"]
    search_fields = ["reference", "gateway_payment_id"]


@admin.register(GatewayNotification)
class GatewayNotificationAdmin(ReadOnlyAdmin):
    list_display = ["received_at", "provider", "payment", "outcome", "detail", "source_ip"]
    list_filter = ["outcome", "provider"]
