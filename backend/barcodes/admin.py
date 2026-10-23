from django.contrib import admin

from .models import Barcode, BarcodeScan


class ReadOnlyAdmin(admin.ModelAdmin):
    """Barcodes are issued and revoked in the app, and scans logged by it."""

    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Barcode)
class BarcodeAdmin(ReadOnlyAdmin):
    list_display = ["issued_at", "club", "team", "mode", "fixture", "revoked_at"]
    list_filter = ["mode", "club"]
    list_select_related = ["club", "team", "fixture"]
    exclude = ["code", "nonce"]


@admin.register(BarcodeScan)
class BarcodeScanAdmin(ReadOnlyAdmin):
    list_display = ["scanned_at", "club", "barcode", "method", "result", "reason", "scanned_by"]
    list_filter = ["result", "method", "club"]
    list_select_related = ["club", "barcode", "scanned_by"]
