"""Clubs and their Nights.

Every club's data belongs to that Club (docs/DECISIONS.md, 2026-10-23). This chunk only
needs enough of Club and Night for roles and Night opt-ins; chunk 3 adds Seasons,
Divisions, Fields and the club settings.
"""

from django.db import models


class Club(models.Model):
    """A venue operator running leagues in the app. Set up by us, not by sign-up."""

    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Night(models.Model):
    """A weekday a Club runs league matches on, e.g. a Tuesday Night league."""

    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="nights")
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)

    class Meta:
        ordering = ["club__name", "weekday"]

    def __str__(self) -> str:
        return f"{self.club}: {self.get_weekday_display()}"
