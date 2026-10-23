"""What a Booking costs, has paid and still owes (FR-33), in rand, Decimal.

The price is on the Booking; what was paid is in the ledger (card, cash, or credit spent,
less what came back as credit). See ledger.services, "Bookings".
"""

from decimal import ROUND_HALF_UP, Decimal

from ledger import services as ledger

from .models import Booking

CENT = Decimal("0.01")


def price(hourly_fee: Decimal, hours: int) -> Decimal:
    """Hourly fee times hours booked (FR-33)."""
    return (hourly_fee * hours).quantize(CENT)


def paid(booking: Booking) -> Decimal:
    """What still stands as paid for the Booking."""
    return ledger.booking_paid(booking)


def outstanding(booking: Booking) -> Decimal:
    """What the Booking still owes; nothing once it is declined or cancelled."""
    return ledger.booking_outstanding(booking)


def percent_of(amount: Decimal, percent: int) -> Decimal:
    """`percent`% of `amount`, to the cent, half a cent up."""
    return (amount * Decimal(percent) / Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)


def rand(amount: Decimal) -> str:
    """Money as the app shows it: "R 350", "R 18,550", "R 12.50"."""
    return f"R {amount:,.0f}" if amount == amount.to_integral_value() else f"R {amount:,.2f}"
