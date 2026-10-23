"""Payment Barcodes (PRD "Barcode authorisation", NFR Barcode integrity).

A Barcode proves at the gate that its subject has paid. It is tied to one subject: a Team,
a friendly (FR-24: the friendly's fee is paid and its Captain shows the Barcode), or a
Booking (FR-30: issued to the Booking User when an Admin accepts it, valid for that
Booking only, mode `booking`, no Season). How long a Team's is valid depends on the club's
payment mode when it was issued:

- gateway mode: issued automatically when the Team is paid, valid for one match (the
  `fixture`);
- cash-only mode: issued when an Admin confirms the cash, valid for the rest of the
  `season`.

A friendly's Barcode is always valid for that one match (`fixture`), whatever the mode.

Its `code` is signed (barcodes/signing.py): an HMAC of a random nonce and the whole subject,
so it can't be guessed, made without the key, or moved to another Team. A Barcode is never
deleted; the only change it takes is being revoked. Every scan is logged as a BarcodeScan,
which is never changed or deleted.
"""

from django.conf import settings
from django.db import models

from bookings.models import Booking
from clubs.models import Club, Season
from fixtures.models import Fixture, FriendlyFee
from teams.models import Team

NEVER_DELETED = "A Barcode is never deleted. Revoke it instead."
SCAN_NEVER_CHANGED = "A BarcodeScan is never changed."
SCAN_NEVER_DELETED = "A BarcodeScan is never deleted."


class BarcodeQuerySet(models.QuerySet):
    def delete(self):
        raise ValueError(NEVER_DELETED)

    delete.queryset_only = True


class ScanQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError(SCAN_NEVER_CHANGED)

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValueError(SCAN_NEVER_CHANGED)

    def delete(self):
        raise ValueError(SCAN_NEVER_DELETED)

    delete.queryset_only = True


class Barcode(models.Model):
    class Mode(models.TextChoices):
        MATCH = "match", "Valid for one match (payment gateway)"
        SEASON = "season", "Valid for the rest of the Season (cash, confirmed by an Admin)"
        BOOKING = "booking", "Valid for one Booking"

    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="barcodes")
    team = models.ForeignKey(
        Team,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="barcodes",
        help_text="The Team it is for; empty for a friendly's Barcode.",
    )
    friendly = models.ForeignKey(
        FriendlyFee,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="barcodes",
        help_text="The friendly it is for (FR-24); empty for a Team's Barcode.",
    )
    booking = models.ForeignKey(
        Booking,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="barcodes",
        help_text="The Booking it is for (FR-30); empty for a Team's or a friendly's.",
    )
    mode = models.CharField(max_length=8, choices=Mode.choices)
    season = models.ForeignKey(
        Season,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="barcodes",
        help_text="Empty only for a Booking's Barcode.",
    )
    fixture = models.ForeignKey(
        Fixture,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="barcodes",
        help_text="The match a per-match Barcode is valid for.",
    )
    code = models.CharField(
        max_length=10,
        unique=True,
        editable=False,
        help_text="What the barcode encodes and the gate types in: signed, see signing.py.",
    )
    nonce = models.CharField(max_length=32, editable=False)
    issued_at = models.DateTimeField(auto_now_add=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="The Admin who issued it; empty when the app did on payment.",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    revoke_reason = models.CharField(max_length=300, blank=True)

    objects = BarcodeQuerySet.as_manager()

    class Meta:
        ordering = ["-issued_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(mode="match", fixture__isnull=False)
                | models.Q(mode="season", fixture__isnull=True)
                | models.Q(mode="booking", fixture__isnull=True),
                name="barcode_match_names_its_fixture",
            ),
            models.CheckConstraint(
                condition=models.Q(revoked_at__isnull=True) | ~models.Q(revoke_reason=""),
                name="barcode_revoked_with_reason",
            ),
            models.UniqueConstraint(
                fields=["team", "fixture"],
                condition=models.Q(mode="match", revoked_at__isnull=True),
                name="one_live_barcode_per_team_and_match",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    team__isnull=False,
                    friendly__isnull=True,
                    booking__isnull=True,
                    season__isnull=False,
                )
                | models.Q(
                    team__isnull=True,
                    friendly__isnull=False,
                    booking__isnull=True,
                    mode="match",
                    season__isnull=False,
                )
                | models.Q(
                    team__isnull=True,
                    friendly__isnull=True,
                    booking__isnull=False,
                    mode="booking",
                    season__isnull=True,
                ),
                name="barcode_has_one_subject",
            ),
            models.UniqueConstraint(
                fields=["booking"],
                condition=models.Q(revoked_at__isnull=True),
                name="one_live_barcode_per_booking",
            ),
            models.UniqueConstraint(
                fields=["friendly"],
                condition=models.Q(revoked_at__isnull=True),
                name="one_live_barcode_per_friendly",
            ),
            models.UniqueConstraint(
                fields=["team", "season"],
                condition=models.Q(mode="season", revoked_at__isnull=True),
                name="one_live_season_barcode_per_team",
            ),
        ]

    def __str__(self) -> str:
        return f"Barcode {self.code} for {self.holder_name}"

    @property
    def holder_name(self) -> str:
        """Who it lets in: the Team, the friendly ("Friendly: Red Lions vs Old Boys") or the
        Booking ("Booking: Sipho Dlamini")."""
        if self.team_id is not None:
            return self.team.name
        if self.booking_id is not None:
            return f"Booking: {self.booking.user.name}"
        fixture = self.fixture
        return f"Friendly: {fixture.home_team.name} vs {fixture.away_team.name}"

    def delete(self, *args, **kwargs):
        raise ValueError(NEVER_DELETED)


BARCODE_MODES = Barcode.Mode  # One name for each enum in the OpenAPI schema.


class BarcodeScan(models.Model):
    """One scan at the gate, whatever came of it. Never changed or deleted."""

    class Method(models.TextChoices):
        CAMERA = "camera", "Scanned with the camera"
        MANUAL = "manual", "Code typed in"

    class Result(models.TextChoices):
        PAID = "paid", "Paid"
        NOT_PAID = "not_paid", "Not paid"

    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="barcode_scans")
    barcode = models.ForeignKey(
        Barcode,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="scans",
        help_text="Empty when the code matched no Barcode of this club.",
    )
    code = models.CharField(max_length=40, help_text="The code as scanned or typed.")
    method = models.CharField(max_length=6, choices=Method.choices)
    fixture = models.ForeignKey(
        Fixture,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="barcode_scans",
        help_text="The match the scan was checked against.",
    )
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="barcode_scans"
    )
    scanned_at = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=8, choices=Result.choices)
    reason = models.CharField(max_length=300, blank=True)

    objects = ScanQuerySet.as_manager()

    class Meta:
        ordering = ["-scanned_at", "-pk"]
        indexes = [models.Index(fields=["club", "-scanned_at"])]
        constraints = [
            # Single use (NFR Barcode integrity): a Barcode lets its Team in once per match.
            models.UniqueConstraint(
                fields=["barcode", "fixture"],
                condition=models.Q(result="paid"),
                name="one_paid_scan_per_barcode_and_match",
            ),
            # A Booking's Barcode (no match) lets its Booking User in once.
            models.UniqueConstraint(
                fields=["barcode"],
                condition=models.Q(result="paid", fixture__isnull=True),
                name="one_paid_scan_per_barcode_without_match",
            ),
        ]

    def __str__(self) -> str:
        return f"Scan of {self.code}: {self.get_result_display()}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError(SCAN_NEVER_CHANGED)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError(SCAN_NEVER_DELETED)


SCAN_METHODS = BarcodeScan.Method
SCAN_RESULTS = BarcodeScan.Result
