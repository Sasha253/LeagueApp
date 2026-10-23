"""Clubs and their setup: Seasons, Nights, Divisions, Fields and settings (FR-42).

Every club's data belongs to that Club (docs/DECISIONS.md, 2026-10-23). Every value a club
can configure is data (NFR Configurability): a new Club's ClubSettings is copied from the
one SettingsDefaults record, seeded with the PRD defaults by a data migration. No default
lives in code.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

MONEY = {"max_digits": 10, "decimal_places": 2, "validators": [MinValueValidator(Decimal("0"))]}
PERCENT = [MinValueValidator(0), MaxValueValidator(100)]


class Club(models.Model):
    """A venue operator running leagues in the app. Set up by us, not by sign-up."""

    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Season(models.Model):
    """A run of league fixtures, e.g. Spring 2026."""

    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="seasons")
    name = models.CharField(max_length=60)
    starts_on = models.DateField()
    ends_on = models.DateField()

    class Meta:
        ordering = ["club__name", "-starts_on"]
        constraints = [
            models.UniqueConstraint(fields=["club", "name"], name="one_season_name_per_club"),
            models.CheckConstraint(
                condition=models.Q(ends_on__gte=models.F("starts_on")),
                name="season_ends_after_it_starts",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.club}: {self.name}"


class Night(models.Model):
    """A weekday a Club runs league matches on, e.g. a Tuesday Night league.

    Nights and their Divisions carry over from Season to Season, so Players' Night opt-ins
    do too (docs/DECISIONS.md).
    """

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
        constraints = [
            models.UniqueConstraint(fields=["club", "weekday"], name="one_night_per_weekday"),
        ]

    def __str__(self) -> str:
        return f"{self.club}: {self.get_weekday_display()}"


class Division(models.Model):
    """A Division of one Night's league, e.g. Division 2 of the Tuesday Night league."""

    night = models.ForeignKey(Night, on_delete=models.PROTECT, related_name="divisions")
    name = models.CharField(max_length=60)
    min_players = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Fewer confirmed Players at T-6h and the Team is out (FR-5).",
    )
    league_fee = models.DecimalField(
        **MONEY,
        null=True,
        blank=True,
        help_text="Overrides the club's league fee per Team for this Division.",
    )

    class Meta:
        ordering = ["night__club__name", "night__weekday", "name"]
        constraints = [
            models.UniqueConstraint(fields=["night", "name"], name="one_division_name_per_night"),
        ]

    def __str__(self) -> str:
        return f"{self.night}: {self.name}"

    def get_club_id(self) -> int:
        return self.night.club_id

    @property
    def effective_league_fee(self) -> Decimal | None:
        """The fee per Team: this Division's own, else the club's (None while unset)."""
        if self.league_fee is not None:
            return self.league_fee
        return self.night.club.settings.league_fee


class Field(models.Model):
    """A pitch a Club plays league matches on and hires out, with its Referee."""

    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="fields")
    name = models.CharField(max_length=60)
    referee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refereed_fields",
        help_text="Must hold the Referee role at this Club.",
    )

    class Meta:
        ordering = ["club__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["club", "name"], name="one_field_name_per_club"),
        ]

    def __str__(self) -> str:
        return f"{self.club}: {self.name}"


class PaymentMode(models.TextChoices):
    GATEWAY = "gateway", "Card through the payment gateway, and cash"
    CASH_ONLY = "cash_only", "Cash only, confirmed by an Admin"


class PaymentProvider(models.TextChoices):
    PAYFAST = "payfast", "PayFast"


class ConfigurableValues(models.Model):
    """Every value a club configures. No field has a default: values come from data.

    Fees may be empty: an Admin sets them before they are needed (docs/DECISIONS.md).
    """

    league_fee = models.DecimalField(
        **MONEY, null=True, blank=True, help_text="League fee per Team for a Season."
    )
    friendly_fee = models.DecimalField(
        **MONEY, null=True, blank=True, help_text="Default fee for a friendly match (FR-24)."
    )
    booking_hourly_fee = models.DecimalField(
        **MONEY, null=True, blank=True, help_text="Field hire price per hour (FR-33)."
    )
    division_min_players = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Minimum Players a new Division starts with (FR-5).",
    )
    confirmation_hours_before = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Confirmations go out this many hours before kick-off (FR-1).",
    )
    confirmation_resend_after_hours = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Unanswered Confirmations are resent once, this long after the first (FR-2).",
    )
    readiness_hours_before = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Reminder and readiness check, this many hours before kick-off (FR-4, FR-5).",
    )
    booking_payment_cutoff_hours = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Booking payment is taken this many hours before kick-off (FR-34).",
    )
    booking_late_cancel_hours = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Cancelling closer to kick-off than this gives the no-show credit.",
    )
    booking_late_cancel_credit_percent = models.PositiveSmallIntegerField(
        validators=PERCENT,
        help_text="Credit for cancelling between the payment cutoff and the late-cancel time.",
    )
    booking_no_show_credit_percent = models.PositiveSmallIntegerField(
        validators=PERCENT,
        help_text="Credit for cancelling after the late-cancel time, or not showing up.",
    )
    booking_club_cancel_credit_percent = models.PositiveSmallIntegerField(
        validators=PERCENT, help_text="Credit when the club cancels a booking."
    )
    booking_reschedule_window_days = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        help_text="A late reschedule must move to a slot within this many days.",
    )
    booking_reschedules_allowed = models.PositiveSmallIntegerField(
        help_text="How many late reschedules one booking may have."
    )
    payment_mode = models.CharField(max_length=10, choices=PaymentMode.choices)
    payment_provider = models.CharField(max_length=10, choices=PaymentProvider.choices)

    class Meta:
        abstract = True

    @classmethod
    def value_names(cls) -> list[str]:
        return [f.name for f in ConfigurableValues._meta.local_fields]


class SettingsDefaults(ConfigurableValues):
    """The values a new Club starts from. One record, seeded with the PRD defaults."""

    class Meta:
        verbose_name = "settings defaults"
        verbose_name_plural = "settings defaults"

    def __str__(self) -> str:
        return "Settings for new clubs"


class ClubSettings(ConfigurableValues):
    """One Club's configurable values (FR-42). Created with the Club."""

    club = models.OneToOneField(Club, on_delete=models.CASCADE, related_name="settings")
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    REQUIRED_BEFORE_USE = ("league_fee", "friendly_fee", "booking_hourly_fee")

    class Meta:
        verbose_name_plural = "club settings"

    def __str__(self) -> str:
        return f"Settings for {self.club}"

    @classmethod
    def from_defaults(cls, club: Club) -> "ClubSettings":
        defaults = SettingsDefaults.objects.first()
        if defaults is None:
            raise SettingsDefaults.DoesNotExist("Seed SettingsDefaults before creating a Club.")
        values = {name: getattr(defaults, name) for name in cls.value_names()}
        return cls.objects.create(club=club, **values)

    @property
    def missing(self) -> list[str]:
        """Values the Admin still has to set."""
        return [name for name in self.REQUIRED_BEFORE_USE if getattr(self, name) is None]
