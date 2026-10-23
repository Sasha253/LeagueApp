from django.apps import AppConfig


class BarcodesConfig(AppConfig):
    name = "barcodes"
    verbose_name = "Payment Barcodes"

    def ready(self) -> None:
        from . import receivers  # noqa: F401  Issues a Barcode when a Team is paid.
