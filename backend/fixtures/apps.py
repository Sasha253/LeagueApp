from django.apps import AppConfig


class FixturesConfig(AppConfig):
    name = "fixtures"
    verbose_name = "Fixtures"

    def ready(self) -> None:
        from . import (
            borrowing,  # noqa: F401  Connects the Player and Goalkeeper Request receiver.
            confirmations,  # noqa: F401  Connects the Confirmation answer receiver.
            fallbacks,  # noqa: F401  Connects the friendly and cancellation receivers.
            replacements,  # noqa: F401  Connects the replacement receivers.
        )
