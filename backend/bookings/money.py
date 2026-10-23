"""What a Booking costs and still owes (FR-33), in rand, Decimal.

Payments for Bookings come with chunk 24 (PayFast at the club's payment cutoff, or cash an
Admin confirms). Until then nothing is paid towards a Booking, so it owes its whole price:
the gate never lets a Booking User in for money the club hasn't received.
"""

from decimal import Decimal

from .models import Booking


def price(hourly_fee: Decimal, hours: int) -> Decimal:
    """Hourly fee times hours booked (FR-33)."""
    return (hourly_fee * hours).quantize(Decimal("0.01"))


def paid(booking: Booking) -> Decimal:
    """What has been paid towards the Booking. Chunk 24 records Booking payments."""
    return Decimal("0.00")


def outstanding(booking: Booking) -> Decimal:
    return max(booking.price - paid(booking), Decimal("0.00"))


def rand(amount: Decimal) -> str:
    """Money as the app shows it: "R 350", "R 18,550", "R 12.50"."""
    return f"R {amount:,.0f}" if amount == amount.to_integral_value() else f"R {amount:,.2f}"
