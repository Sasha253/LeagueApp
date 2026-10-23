"""Field bookings (PRD "Bookings", FR-28 to FR-31).

A Booking User hires one of a Club's Fields for whole hours from a start time. An Admin of
the Club accepts or declines it (FR-29); on accept the Booking User gets a Barcode for the
gate (FR-30, barcodes app). The Booking User can cancel or reschedule it (FR-31).

- A Booking belongs to one Club, and only that Club's Admins see or decide it.
- Pending and accepted Bookings hold their Field: nothing else may overlap them, and no
  Booking may overlap a Fixture on that Field (bookings/services.py checks both).
- The price is the hourly fee fixed when the Booking was requested times the hours
  (FR-33), in rand, Decimal. Payment and the cancellation policy come with chunk 24.
- Every change is logged in BookingEvent, which is never changed or deleted.

Times are stored in UTC and shown in South African time (CLAUDE.md).
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from clubs.models import MONEY, Club, Field

MOST_HOURS = 24


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for an Admin"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"

    HOLDS_FIELD = (Status.PENDING, Status.ACCEPTED)

    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="bookings")
    field = models.ForeignKey(Field, on_delete=models.PROTECT, related_name="bookings")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings"
    )
    starts_at = models.DateTimeField()
    hours = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(MOST_HOURS)]
    )
    ends_at = models.DateTimeField(help_text="The start plus the hours; kept for clash checks.")
    hourly_fee = models.DecimalField(
        **MONEY, help_text="The club's hourly fee when the booking was requested."
    )
    price = models.DecimalField(**MONEY, help_text="Hourly fee times hours (FR-33).")
    status = models.CharField(max_length=10, choices=Status.choices, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="The Admin who accepted or declined it.",
    )
    decline_reason = models.CharField(max_length=300, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["starts_at", "pk"]
        indexes = [models.Index(fields=["field", "starts_at"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="booking_ends_after_it_starts",
            ),
            models.CheckConstraint(
                condition=models.Q(hours__gte=1, hours__lte=MOST_HOURS),
                name="booking_hours_in_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.field} for {self.user}, {self.starts_at:%Y-%m-%d %H:%M}"

    @property
    def holds_field(self) -> bool:
        return self.status in self.HOLDS_FIELD


BOOKING_STATUSES = Booking.Status  # One name for the status enum in the OpenAPI schema.


class EventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("A BookingEvent is never changed.")

    def delete(self):
        raise ValueError("A BookingEvent is never deleted.")

    delete.queryset_only = True


class BookingEvent(models.Model):
    """One change to a Booking, with the slot it left the Booking on. Never changed."""

    class Kind(models.TextChoices):
        REQUESTED = "requested", "Requested"
        RESCHEDULED = "rescheduled", "Rescheduled"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"

    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name="events")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    at = models.DateTimeField()
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    field = models.ForeignKey(Field, on_delete=models.PROTECT, related_name="+")
    starts_at = models.DateTimeField()
    hours = models.PositiveSmallIntegerField()
    note = models.CharField(max_length=300, blank=True)

    objects = EventQuerySet.as_manager()

    class Meta:
        ordering = ["at", "pk"]

    def __str__(self) -> str:
        return f"{self.booking}: {self.get_kind_display()}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("A BookingEvent is never changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("A BookingEvent is never deleted.")


BOOKING_EVENT_KINDS = BookingEvent.Kind
