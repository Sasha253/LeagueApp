"""Card payments through a payment gateway (FR-19 to FR-22).

A Payment is one Player's contribution towards what their Team owes: some from credit
(spent at once, a ledger entry) and the rest by card on the gateway's own hosted page, so
card details never reach this app (NFR Security). The card part becomes a ledger entry
only when the gateway confirms it (PayFast's ITN). The ledger is the record of money; a
Payment only tracks the gateway round trip, and is never deleted.

Every notification a gateway sends is kept as a GatewayNotification, accepted or not, and
never changed or deleted.
"""

import uuid

from django.conf import settings
from django.db import models

from clubs.models import Club, PaymentProvider
from ledger.models import LedgerEntry
from teams.models import Team


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for the gateway"
        COMPLETE = "complete", "Paid"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class Credit(models.TextChoices):
        NONE = "none", "No credit"
        PLAYER = "player", "The Player's credit"
        TEAM = "team", "The Team's credit (its Captain)"

    reference = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Our id for the payment at the gateway (PayFast m_payment_id).",
    )
    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="payments")
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="payments")
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payments",
        help_text="The Player who chose this contribution and pays it.",
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="The whole contribution: credit plus card."
    )
    credit_used = models.CharField(max_length=6, choices=Credit.choices)
    credit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    card_amount = models.DecimalField(max_digits=10, decimal_places=2)
    provider = models.CharField(max_length=10, choices=PaymentProvider.choices)
    merchant_id = models.CharField(
        max_length=40,
        blank=True,
        help_text="The gateway merchant account the card part is paid into.",
    )
    status = models.CharField(max_length=10, choices=Status.choices)
    gateway_payment_id = models.CharField(
        max_length=60,
        null=True,
        blank=True,
        unique=True,
        help_text="The gateway's id for the confirmed payment (PayFast pf_payment_id).",
    )
    credit_entry = models.OneToOneField(
        LedgerEntry,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="The ledger entry that spent the credit.",
    )
    card_entry = models.OneToOneField(
        LedgerEntry,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="The ledger entry for the confirmed card payment.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0, credit_amount__gte=0, card_amount__gte=0)
                & models.Q(amount=models.F("credit_amount") + models.F("card_amount")),
                name="payment_amount_is_credit_plus_card",
            ),
            models.CheckConstraint(
                condition=models.Q(credit_used="none", credit_amount=0)
                | (~models.Q(credit_used="none") & models.Q(credit_amount__gt=0)),
                name="payment_credit_named",
            ),
        ]
        indexes = [models.Index(fields=["team", "status"])]

    def __str__(self) -> str:
        return f"R {self.amount} for {self.team} ({self.get_status_display()})"

    def delete(self, *args, **kwargs):
        raise ValueError("A Payment is never deleted.")


PAYMENT_STATUSES = Payment.Status  # One name for each enum in the OpenAPI schema.
PAYMENT_CREDIT_SOURCES = Payment.Credit


class GatewayNotification(models.Model):
    """A notification a gateway sent us (PayFast ITN), kept whatever came of it."""

    class Outcome(models.TextChoices):
        ACCEPTED = "accepted", "Accepted"
        REPEAT = "repeat", "Already handled"
        REJECTED = "rejected", "Rejected"

    provider = models.CharField(max_length=10, choices=PaymentProvider.choices)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="notifications",
    )
    received_at = models.DateTimeField(auto_now_add=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    fields = models.JSONField(help_text="The fields as received. Gateways send no card data.")
    outcome = models.CharField(max_length=10, choices=Outcome.choices)
    detail = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-received_at", "-pk"]

    def __str__(self) -> str:
        return f"{self.get_provider_display()} notification ({self.get_outcome_display()})"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("A GatewayNotification is never changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("A GatewayNotification is never deleted.")
