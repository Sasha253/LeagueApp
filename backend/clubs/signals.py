"""A new Club starts from the settings defaults (data, not code)."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Club, ClubSettings


@receiver(post_save, sender=Club)
def give_new_club_its_settings(sender, instance: Club, created: bool, raw: bool, **kwargs):
    if created and not raw:
        ClubSettings.from_defaults(instance)
