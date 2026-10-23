"""Signals other chunks listen to.

`team_paid` (FR-20): a payment (card, cash or credit) took what a Team owes from above zero
to zero or below. Sent inside the payment's transaction with `team`. Chunk 20 issues the
Payment Barcode on it.
"""

from django.dispatch import Signal

team_paid = Signal()
