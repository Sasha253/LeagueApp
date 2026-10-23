from django.apps import AppConfig


class ClubsConfig(AppConfig):
    name = "clubs"
    verbose_name = "Clubs"

    def ready(self) -> None:
        from . import signals  # noqa: F401
