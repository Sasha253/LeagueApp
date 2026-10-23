"""A Booking's Barcode (FR-30) and the gate."""

import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from accounts.models import ClubRole
from barcodes import services as barcodes
from barcodes import signing
from barcodes.models import Barcode
from bookings import services
from bookings.models import Booking

pytestmark = pytest.mark.django_db


def scan(client, club, code, **extra):
    return client.post(
        f"/api/v1/clubs/{club.pk}/scans/",
        {"code": code, "method": "manual", **extra},
        format="json",
    )


@pytest.fixture
def free_hire(takes_bookings):
    """The club lets its fields for R 0, so a Booking owes nothing."""
    takes_bookings.booking_hourly_fee = Decimal("0")
    takes_bookings.save()
    return takes_bookings


@pytest.fixture
def now_on(booker, admin, pitch, takes_bookings):
    """An accepted Booking on Pitch 3 that is on now (started this hour, today)."""

    def make(price="0"):
        start = timezone.localtime().replace(minute=0, second=0, microsecond=0)
        booking = Booking.objects.create(
            club=takes_bookings.club,
            field=pitch,
            user=booker.user,
            starts_at=start,
            hours=1,
            ends_at=start + dt.timedelta(hours=1),
            hourly_fee=Decimal(price),
            price=Decimal(price),
            status=Booking.Status.ACCEPTED,
        )
        barcodes.issue_for_booking(booking)
        return booking

    return make


def test_the_booking_user_sees_the_barcode_once_accepted(booker, book, admin):
    booking = book(booker.user)
    url = f"/api/v1/me/bookings/{booking.pk}/barcode/"

    waiting = booker.get(url).json()
    assert (waiting["state"], waiting["barcode"]) == ("not_accepted", None)

    services.accept(booking, by=admin.user)
    body = booker.get(url).json()

    assert body["barcode"]["holder"] == "Booking: Hannah Hirer"
    assert body["barcode"]["mode"] == "booking"
    assert body["barcode"]["season"] is None
    assert body["barcode"]["booking"]["field"]["name"] == "Pitch 3"
    # R 600 still owed: chunk 24 takes the payment.
    assert body["state"] == "unpaid"
    assert body["reason"] == "The booking still owes R 600."


def test_a_free_booking_is_valid(booker, book, admin, free_hire):
    booking = book(booker.user)
    services.accept(booking, by=admin.user)

    body = booker.get(f"/api/v1/me/bookings/{booking.pk}/barcode/").json()

    assert body["state"] == "valid"


def test_the_code_is_signed_over_the_booking(booker, book, admin, make_user):
    booking = book(booker.user)
    services.accept(booking, by=admin.user)
    other = book(make_user("other@example.com", booking=True), hour=10)
    barcode = Barcode.objects.get(booking=booking)

    assert signing.is_signed(barcode)
    barcode.booking_id = other.pk
    assert not signing.is_signed(barcode)


def test_an_admin_scans_a_paid_booking_in_once(admin, now_on, takes_bookings):
    booking = now_on()
    code = Barcode.objects.get(booking=booking).code

    first = scan(admin, takes_bookings.club, code)
    again = scan(admin, takes_bookings.club, code)

    assert first.status_code == 201
    body = first.json()
    assert (body["paid"], body["state"], body["holder"]) == (True, "valid", "Booking: Hannah Hirer")
    assert body["booking"]["id"] == booking.pk
    assert body["fixture"] is None
    assert again.json()["state"] == "used"


def test_an_unpaid_booking_is_not_let_in(admin, now_on, takes_bookings):
    booking = now_on(price="600")

    body = scan(admin, takes_bookings.club, Barcode.objects.get(booking=booking).code).json()

    assert (body["paid"], body["state"]) == (False, "unpaid")


def test_a_referee_cant_check_a_booking(make_user, give_role, api, now_on, takes_bookings):
    referee = make_user("ref2@example.com")
    give_role(referee, takes_bookings.club, ClubRole.Role.REFEREE)
    api.force_authenticate(referee)

    body = scan(api, takes_bookings.club, Barcode.objects.get(booking=now_on()).code).json()

    assert (body["paid"], body["state"]) == (False, "admins_only")


def test_a_booking_barcode_counts_only_on_its_day(booker, book, admin, free_hire):
    booking = book(booker.user)  # Next Tuesday.
    services.accept(booking, by=admin.user)

    body = scan(admin, free_hire.club, Barcode.objects.get(booking=booking).code).json()

    assert body["state"] == "not_today"


def test_a_cancelled_booking_is_not_let_in(booker, book, admin, free_hire):
    booking = book(booker.user)
    services.accept(booking, by=admin.user)
    services.cancel(booking, by=booker.user)

    body = scan(admin, free_hire.club, Barcode.objects.get(booking=booking).code).json()

    assert (body["paid"], body["state"]) == (False, "revoked")
    shown = booker.get(f"/api/v1/me/bookings/{booking.pk}/barcode/").json()
    assert (shown["state"], shown["barcode"]) == ("not_accepted", None)


def test_another_clubs_admin_finds_no_such_barcode(admin_of, club_b, now_on):
    code = Barcode.objects.get(booking=now_on()).code

    body = scan(admin_of(club_b), club_b, code).json()

    assert body["state"] == "not_found"
