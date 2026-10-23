"""The ledger: every rand a Team, Player or Booking User owes, pays or holds as credit.

Entries are append-only (FR-50): credits, refunds and corrections are new entries with a
reason, and a wrong entry is undone by a reversal entry, never by editing or deleting it.
Nothing changes or deletes a LedgerEntry: not the ORM (save, delete, queryset update and
delete all refuse), not the API (read-only) and not the Django admin (read-only).

Entries are written only by ledger.services. Balances are computed from the entries.
Amounts are Decimal rand and always above zero; the kind says which way the money goes.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from bookings.models import Booking
from clubs.models import Club
from fixtures.models import Fixture
from teams.models import Team

NEVER_CHANGED = "A LedgerEntry is never changed. Add a reversal entry instead."
NEVER_DELETED = "A LedgerEntry is never deleted. Add a reversal entry instead."


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError(NEVER_CHANGED)

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValueError(NEVER_CHANGED)

    def update_or_create(self, *args, **kwargs):
        raise ValueError(NEVER_CHANGED)

    def delete(self):
        raise ValueError(NEVER_DELETED)

    delete.queryset_only = True


class LedgerEntry(models.Model):
    class Kind(models.TextChoices):
        CHARGE = "charge", "Charge"
        PAYMENT = "payment", "Payment"
        CREDIT = "credit", "Credit"
        REFUND = "refund", "Refund"
        REVERSAL = "reversal", "Reversal"

    class Method(models.TextChoices):
        CARD = "card", "Card"
        CASH = "cash", "Cash"
        CREDIT = "credit", "Credit"

    class Subject(models.TextChoices):
        TEAM = "team", "Team"
        PLAYER = "player", "Player"
        BOOKING_USER = "booking_user", "Booking User"

    class Category(models.TextChoices):
        LEAGUE = "league", "League"
        FRIENDLY = "friendly", "Friendly"
        BOOKING = "booking", "Booking"

    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="ledger_entries")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    method = models.CharField(
        max_length=10,
        choices=Method.choices,
        blank=True,
        help_text="How a payment or refund was made. Empty for charges and credits.",
    )
    category = models.CharField(max_length=10, choices=Category.choices)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    subject = models.CharField(
        max_length=12,
        choices=Subject.choices,
        help_text="Whose money or credit this is: the Team, a Player or a Booking User.",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ledger_entries",
        help_text="The Team whose account this is on. For a Player's payment, the Team paid for.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ledger_entries",
        help_text="The Player or Booking User, when the subject is one.",
    )
    fixture = models.ForeignKey(
        Fixture, on_delete=models.PROTECT, null=True, blank=True, related_name="ledger_entries"
    )
    booking = models.ForeignKey(
        Booking,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ledger_entries",
        help_text="The Booking a payment, credit spent or credit returned was for.",
    )
    reverses = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversed_by",
        help_text="For a reversal: the entry it undoes. An entry is reversed at most once.",
    )
    source = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credits_returned",
        help_text="For a credit, and its reversal: the payment it was returned from (FR-52).",
    )
    reason = models.CharField(max_length=300, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="Who recorded it; empty when the app did.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["created_at", "pk"]
        verbose_name_plural = "ledger entries"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="ledger_amount_above_zero"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(subject="team", team__isnull=False, user__isnull=True)
                    | models.Q(subject__in=["player", "booking_user"], user__isnull=False)
                ),
                name="ledger_subject_named",
            ),
            models.CheckConstraint(
                condition=models.Q(kind="reversal", reverses__isnull=False)
                | (~models.Q(kind="reversal") & models.Q(reverses__isnull=True)),
                name="ledger_reversal_names_its_entry",
            ),
        ]
        indexes = [
            models.Index(fields=["club", "created_at"]),
            models.Index(fields=["team", "kind"]),
            models.Index(fields=["user", "kind"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} R {self.amount} ({self.get_subject_display()})"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError(NEVER_CHANGED)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError(NEVER_DELETED)


LEDGER_KINDS = LedgerEntry.Kind
LEDGER_METHODS = LedgerEntry.Method
LEDGER_SUBJECTS = LedgerEntry.Subject
LEDGER_CATEGORIES = LedgerEntry.Category
