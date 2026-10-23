from django.apps import AppConfig


class BookingsConfig(AppConfig):
    name = "bookings"
    verbose_name = "Bookings"

    def ready(self) -> None:
        from . import services  # noqa: F401  Connects the Booking Notification receiver.
