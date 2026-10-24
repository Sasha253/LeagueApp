"""Booking payments and the cancellation policy (FR-32 to FR-34, FR-44 to FR-46)."""

import datetime as dt
from decimal import Decimal as D
from urllib.parse import urlencode

import pytest

from barcodes import services as barcodes
from barcodes.models import BarcodeScan
from bookings import policy, services, tasks
from bookings.models import Booking, BookingEvent
from clubs.models import PaymentMode
from ledger import services as ledger
from ledger.models import LedgerEntry
from notifications.models import Kind, Notification
from payments.models import Payment
from payments.tests.conftest import PAYFAST_IP, itn_fields, payfast_server, payfast_settings

from .conftest import at

pytestmark = pytest.mark.django_db

# Autouse fixtures from the payments tests: PayFast's sandbox account and a fake server.
__all__ = ["payfast_server", "payfast_settings"]

MINE = "/api/v1/me/bookings/"
POLICY = "/api/v1/bookings/policy/"
NOTIFY = "/api/v1/payments/payfast/notify/"


def mine(booking_id, what=""):
    return f"{MINE}{booking_id}/{what + '/' if what else ''}"


def club_booking(club, booking_id, what):
    return f"/api/v1/clubs/{club.pk}/bookings/{booking_id}/{what}/"


@pytest.fixture
def clock(time_machine):
    def move(moment):
        time_machine.move_to(moment, tick=False)

    return move


@pytest.fixture
def accepted(book, booker, admin):
    """Hannah's accepted booking: Pitch 3 next Tuesday 18:00 to 19:00, R 600."""

    def make(**kwargs):
        booking = book(booker.user, **kwargs)
        return services.accept(booking, by=admin.user)

    return make


def before(booking, hours):
    return booking.starts_at - dt.timedelta(hours=hours)


def give_credit(booking_or_club, user, amount):
    club = getattr(booking_or_club, "club", booking_or_club)
    return ledger.issue_credit(
        club=club,
        amount=D(amount),
        reason="Goodwill",
        recorded_by=None,
        user=user,
        subject=LedgerEntry.Subject.BOOKING_USER,
        category=LedgerEntry.Category.BOOKING,
    )


def pay_cash(booking, admin, amount="600"):
    return services.record_cash(booking, by=admin.user, amount=D(amount))


def refreshed(booking):
    return Booking.objects.get(pk=booking.pk)


def post_itn(api, fields):
    return api.generic(
        "POST",
        NOTIFY,
        urlencode(fields),
        content_type="application/x-www-form-urlencoded",
        REMOTE_ADDR=PAYFAST_IP,
    )


def user_updates(booking, title_start):
    return Notification.objects.filter(
        booking=booking, kind=Kind.UPDATE, recipient=booking.user, title__startswith=title_start
    )


# The policy shown before booking (FR-45)


def test_the_policy_comes_from_the_club_settings(booker, takes_bookings):
    body = booker.get(POLICY, {"club": takes_bookings.club.pk}).json()

    assert body["payment_cutoff_hours"] == 24
    assert body["credit"] == "0.00"
    assert [(r["window"], r["when"], r["cancel"], r["reschedule"]) for r in body["rows"]] == [
        ("free", "Before payment is taken (24h before)", "Free; nothing charged", "Free"),
        ("late", "24h to 6h before", "50% back as credit", "Free, once, to a slot within 30 days"),
        ("very_late", "Under 6h before, or no-show", "No credit", "Not allowed"),
        (
            "club",
            "The club cancels (pitch, weather, operational)",
            "100% back as credit. Ask the club about a card refund.",
            "Free",
        ),
    ]


def test_a_club_changing_its_policy_changes_what_is_shown(booker, takes_bookings):
    takes_bookings.booking_late_cancel_credit_percent = 25
    takes_bookings.booking_reschedules_allowed = 2
    takes_bookings.save()

    rows = booker.get(POLICY, {"club": takes_bookings.club.pk}).json()["rows"]

    assert rows[1]["cancel"] == "25% back as credit"
    assert rows[1]["reschedule"] == "Free, twice, to a slot within 30 days"


def test_only_booking_users_see_the_policy(make_user, api, takes_bookings):
    api.force_authenticate(make_user("p@example.com", position="outfield"))
    assert api.get(POLICY, {"club": takes_bookings.club.pk}).status_code == 403


# Windows and outcomes (FR-45)


@pytest.mark.parametrize(
    ("hours_before", "window", "credit"),
    [(30, "free", "600.00"), (12, "late", "300.00"), (3, "very_late", "0.00")],
)
def test_the_cancel_outcome_by_window(booker, accepted, admin, clock, hours_before, window, credit):
    booking = accepted()
    pay_cash(booking, admin)  # Paid early in cash, so every window has something paid.
    if window != "free":
        clock(before(booking, 23))
        services.take_payment(booking)
    clock(before(booking, hours_before))

    body = booker.get(mine(booking.pk, "outcome")).json()

    assert body["cancel"]["window"] == window
    assert body["cancel"]["paid"] == "600.00"
    assert body["cancel"]["credit"] == credit
    assert body["cancel"]["allowed"] is True
    assert len(body["rows"]) == 4


def test_nothing_paid_and_free_says_so(booker, accepted, clock):
    booking = accepted()
    body = booker.get(mine(booking.pk, "outcome")).json()
    assert body["cancel"]["summary"] == "Cancelling now is free. Nothing is charged."
    assert body["reschedule"] == {
        "window": "free",
        "allowed": True,
        "reschedules_left": None,
        "latest_start": None,
        "summary": "Moving it now is free.",
    }


def test_someone_elses_outcome_is_404(accepted, make_user, api):
    booking = accepted()
    api.force_authenticate(make_user("other@example.com", booking=True))
    assert api.get(mine(booking.pk, "outcome")).status_code == 404


# Payment at the cutoff (FR-34, FR-46)


def test_payment_is_taken_at_the_cutoff_only_once(booker, accepted, clock, fake_push):
    booking = accepted()
    clock(before(booking, 25))
    assert services.take_due_payments() == 0

    clock(before(booking, 23))
    assert tasks.run_payments() == {"taken": 1, "settled": 0}
    assert services.take_due_payments() == 0

    booking = refreshed(booking)
    assert booking.payment_requested_at is not None
    assert booking.payment_taken_at is not None
    due = user_updates(booking, "Payment due").get()
    assert "Pay R 600 by card in My bookings" in due.body
    assert booking.events.filter(kind=BookingEvent.Kind.PAYMENT_DUE).count() == 1
    body = booker.get(mine(booking.pk)).json()
    assert body["can_pay"] is True
    assert body["outstanding"] == "600.00"
    assert body["payment_requested"] is True


def test_pending_bookings_are_not_charged(booker, book, clock):
    booking = book(booker.user)
    clock(before(booking, 23))
    assert services.take_due_payments() == 0


def test_credit_is_used_first(booker, accepted, clock):
    booking = accepted()
    give_credit(booking, booker.user, "200")
    clock(before(booking, 23))
    services.take_due_payments()

    assert ledger.booking_credit(booking.club, booker.user) == D("0.00")
    assert services.money.paid(booking) == D("200.00")
    due = user_updates(booking, "Payment due").get()
    assert "R 200 came from your credit" in due.body
    assert "Pay R 400 by card" in due.body


def test_credit_covering_it_all_pays_it_and_the_barcode_works(booker, accepted, clock):
    booking = accepted()
    give_credit(booking, booker.user, "1000")
    clock(before(booking, 23))
    services.take_due_payments()

    assert ledger.booking_credit(booking.club, booker.user) == D("400.00")
    assert user_updates(booking, "Booking paid").exists()
    assert barcodes.current_for_booking(booking)[1].state == "valid"


def test_credit_leaves_the_smallest_card_amount(booker, accepted, clock):
    booking = accepted()
    give_credit(booking, booker.user, "598")
    clock(before(booking, 23))
    services.take_due_payments()
    assert services.money.outstanding(booking) == D("5.00")


def test_a_cash_only_club_asks_for_cash(booker, accepted, clock, takes_bookings):
    takes_bookings.payment_mode = PaymentMode.CASH_ONLY
    takes_bookings.save()
    booking = accepted()
    clock(before(booking, 23))
    services.take_due_payments()
    assert (
        "Pay R 600 to the club before you play" in user_updates(booking, "Payment due").get().body
    )
    assert booker.get(mine(booking.pk)).json()["can_pay"] is False  # No Pay button.
    assert booker.post(mine(booking.pk, "pay")).status_code == 409


def test_a_cash_only_club_can_be_paid_from_credit(booker, accepted, clock, takes_bookings):
    takes_bookings.payment_mode = PaymentMode.CASH_ONLY
    takes_bookings.save()
    booking = accepted()
    clock(before(booking, 23))
    services.take_due_payments()
    give_credit(booking, booker.user, "600")

    assert booker.get(mine(booking.pk)).json()["can_pay"] is True
    body = booker.post(mine(booking.pk, "pay")).json()
    assert (body["credit_amount"], body["card_amount"]) == ("600.00", "0.00")


# Paying by card


def test_paying_before_it_is_due_is_refused(booker, accepted):
    booking = accepted()
    answer = booker.post(mine(booking.pk, "pay"))
    assert answer.status_code == 409
    assert "isn't due yet" in answer.json()["detail"]


def test_paying_by_card_then_the_itn_records_it(booker, accepted, clock, api):
    booking = accepted()
    give_credit(booking, booker.user, "100")
    clock(before(booking, 23))
    services.take_due_payments()  # Spends the R 100 credit.

    body = booker.post(mine(booking.pk, "pay")).json()
    assert body["booking"]["id"] == booking.pk
    assert body["team"] is None
    assert body["card_amount"] == "500.00"
    assert "Pitch+3+booking" in body["checkout"]["url"]

    payment = Payment.objects.get(reference=body["reference"])
    assert post_itn(api, itn_fields(payment)).status_code == 200
    assert post_itn(api, itn_fields(payment)).status_code == 200  # Once only.

    assert services.money.paid(booking) == D("600.00")
    assert services.money.outstanding(booking) == D("0.00")
    assert barcodes.current_for_booking(booking)[1].state == "valid"
    assert booker.get(f"/api/v1/payments/{payment.reference}/").status_code == 200
    assert booker.get(mine(booking.pk)).json()["can_pay"] is False


def test_credit_is_spent_first_when_paying(booker, accepted, clock):
    booking = accepted()
    clock(before(booking, 23))
    services.take_due_payments()
    give_credit(booking, booker.user, "50")

    body = booker.post(mine(booking.pk, "pay")).json()

    assert body["credit_used"] == "booking_user"
    assert (body["credit_amount"], body["card_amount"]) == ("50.00", "550.00")


def test_a_new_payment_closes_the_one_not_made(booker, accepted, clock):
    booking = accepted()
    clock(before(booking, 23))
    services.take_due_payments()
    first = booker.post(mine(booking.pk, "pay")).json()["reference"]
    booker.post(mine(booking.pk, "pay"))
    assert Payment.objects.get(reference=first).status == Payment.Status.CANCELLED


def test_a_card_payment_after_a_cancel_comes_back_as_credit(booker, accepted, clock, api):
    booking = accepted()
    clock(before(booking, 23))
    services.take_due_payments()
    payment = Payment.objects.get(
        reference=booker.post(mine(booking.pk, "pay")).json()["reference"]
    )
    booker.post(mine(booking.pk, "cancel"))

    assert post_itn(api, itn_fields(payment)).status_code == 200

    assert ledger.booking_credit(booking.club, booker.user) == D("600.00")
    assert services.money.paid(booking) == D("0.00")


def test_someone_else_cannot_pay_or_see_the_payment(booker, accepted, clock, make_user, api):
    booking = accepted()
    clock(before(booking, 23))
    services.take_due_payments()
    reference = booker.post(mine(booking.pk, "pay")).json()["reference"]
    api.force_authenticate(make_user("other@example.com", booking=True))
    assert api.post(mine(booking.pk, "pay")).status_code == 404
    assert api.get(f"/api/v1/payments/{reference}/").status_code == 404


# Cancelling (the policy)


def test_a_late_cancel_returns_half_as_credit(booker, accepted, admin, clock, fake_push):
    booking = accepted()
    clock(before(booking, 23))
    services.take_due_payments()
    pay_cash(booking, admin)
    clock(before(booking, 12))

    body = booker.post(mine(booking.pk, "cancel")).json()

    assert body["status"] == "cancelled"
    assert ledger.booking_credit(booking.club, booker.user) == D("300.00")
    assert services.money.paid(booking) == D("300.00")  # The club keeps R 300.
    event = booking.events.get(kind=BookingEvent.Kind.CANCELLED)
    assert event.window == "late"
    assert "The club keeps R 300" in user_updates(booking, "Booking cancelled").get().body


def test_a_very_late_cancel_returns_nothing(booker, accepted, admin, clock):
    booking = accepted()
    clock(before(booking, 23))
    services.take_due_payments()
    pay_cash(booking, admin)
    clock(before(booking, 3))
    booker.post(mine(booking.pk, "cancel"))
    assert ledger.booking_credit(booking.club, booker.user) == D("0.00")
    assert services.money.paid(booking) == D("600.00")


def test_a_free_cancel_returns_early_cash_in_full(booker, accepted, admin, clock):
    booking = accepted()
    pay_cash(booking, admin)
    clock(before(booking, 30))
    booker.post(mine(booking.pk, "cancel"))
    assert ledger.booking_credit(booking.club, booker.user) == D("600.00")


def test_cancelling_unpaid_after_the_cutoff_costs_nothing(booker, accepted, clock):
    booking = accepted()
    clock(before(booking, 23))
    services.take_due_payments()
    booker.post(mine(booking.pk, "cancel"))
    assert services.money.outstanding(refreshed(booking)) == D("0.00")
    assert not LedgerEntry.objects.filter(kind=LedgerEntry.Kind.CREDIT).exists()


# Rescheduling (the policy)


def test_a_late_reschedule_is_allowed_once(booker, accepted, admin, clock, day):
    booking = accepted()
    clock(before(booking, 12))
    services.take_due_payments()
    outcome = booker.get(mine(booking.pk, "outcome")).json()["reschedule"]
    assert (outcome["window"], outcome["allowed"], outcome["reschedules_left"]) == (
        "late",
        True,
        1,
    )

    moved = {"field": booking.field_id, "starts_at": at(day, 20), "hours": 1}
    assert booker.post(mine(booking.pk, "reschedule"), moved, format="json").status_code == 200
    assert refreshed(booking).payment_requested_at is None
    assert refreshed(booking).payment_taken_at is not None  # Never free again.

    again = {"field": booking.field_id, "starts_at": at(day, 21), "hours": 1}
    answer = booker.post(mine(booking.pk, "reschedule"), again, format="json")
    assert answer.status_code == 409
    assert answer.json()["detail"] == "It has been moved as often as the club allows."


def test_a_late_reschedule_must_stay_within_the_window(booker, accepted, clock, day):
    booking = accepted()
    clock(before(booking, 12))
    far = {"field": booking.field_id, "starts_at": at(day + dt.timedelta(days=31), 18), "hours": 1}
    answer = booker.post(mine(booking.pk, "reschedule"), far, format="json")
    assert answer.status_code == 400
    assert "A late move must start by" in answer.json()["starts_at"][0]


def test_a_very_late_reschedule_is_refused(booker, accepted, clock, day):
    booking = accepted()
    clock(before(booking, 3))
    moved = {"field": booking.field_id, "starts_at": at(day, 20), "hours": 1}
    answer = booker.post(mine(booking.pk, "reschedule"), moved, format="json")
    assert answer.status_code == 409
    assert "less than 6 hours" in answer.json()["detail"]


def test_free_reschedules_have_no_limit(booker, accepted, clock, day):
    booking = accepted()
    for hour in (19, 20, 21):
        moved = {"field": booking.field_id, "starts_at": at(day, hour), "hours": 1}
        assert booker.post(mine(booking.pk, "reschedule"), moved, format="json").status_code == 200


def test_moving_to_fewer_hours_returns_the_difference(booker, accepted, admin, clock, day):
    booking = accepted(hours=2)
    pay_cash(booking, admin, "1200")
    moved = {"field": booking.field_id, "starts_at": at(day, 18), "hours": 1}
    booker.post(mine(booking.pk, "reschedule"), moved, format="json")
    assert services.money.paid(booking) == D("600.00")
    assert ledger.booking_credit(booking.club, booker.user) == D("600.00")


def test_declining_a_paid_move_returns_the_club_percent(booker, accepted, admin, day):
    booking = accepted()
    pay_cash(booking, admin)
    moved = {"field": booking.field_id, "starts_at": at(day, 20), "hours": 1}
    booker.post(mine(booking.pk, "reschedule"), moved, format="json")
    services.decline(refreshed(booking), by=admin.user, reason="Pitch closed")
    assert ledger.booking_credit(booking.club, booker.user) == D("600.00")


# The club cancels


def test_the_club_cancels_with_a_reason_and_full_credit(booker, accepted, admin, clock):
    booking = accepted()
    pay_cash(booking, admin)
    clock(before(booking, 2))
    path = club_booking(booking.club, booking.pk, "cancel")

    assert admin.post(path, {"reason": ""}, format="json").status_code == 400
    shown = admin.get(f"/api/v1/clubs/{booking.club.pk}/bookings/{booking.pk}/").json()
    assert shown["club_cancel_summary"] == "You get all R 600 you paid back as credit."
    body = admin.post(path, {"reason": "Floodlights are down"}, format="json").json()

    assert body["status"] == "cancelled"
    assert body["cancelled_by_club"] is True
    assert ledger.booking_credit(booking.club, booker.user) == D("600.00")
    told = user_updates(booking, "The club cancelled").get()
    assert "Floodlights are down." in told.body
    assert "R 600 is back as credit." in told.body
    assert barcodes.current_for_booking(booking)[1].state != "valid"


def test_another_clubs_admin_cannot_cancel_or_record_cash(accepted, admin_of, club_b):
    booking = accepted()
    other = admin_of(club_b)
    path = f"/api/v1/clubs/{booking.club.pk}/bookings/{booking.pk}/"
    assert other.post(f"{path}cancel/", {"reason": "x"}, format="json").status_code == 403
    assert other.post(f"{path}cash/", {"amount": "10"}, format="json").status_code == 403
    theirs = f"/api/v1/clubs/{club_b.pk}/bookings/{booking.pk}/"
    assert other.post(f"{theirs}cancel/", {"reason": "x"}, format="json").status_code == 404


def test_the_booking_user_cannot_use_the_admin_actions(booker, accepted):
    booking = accepted()
    path = club_booking(booking.club, booking.pk, "cash")
    assert booker.post(path, {"amount": "10"}, format="json").status_code == 403


# Cash (FR-44)


def test_an_admin_records_cash_up_to_what_is_owed(booker, accepted, admin):
    booking = accepted()
    path = club_booking(booking.club, booking.pk, "cash")

    assert admin.post(path, {"amount": "700"}, format="json").status_code == 409
    answer = admin.post(path, {"amount": "600"}, format="json")

    assert answer.status_code == 201
    assert answer.json()["method"] == "cash"
    assert barcodes.current_for_booking(booking)[1].state == "valid"
    assert admin.post(path, {"amount": "1"}, format="json").status_code == 409


def test_no_cash_for_a_pending_booking(book, booker, admin):
    booking = book(booker.user)
    path = club_booking(booking.club, booking.pk, "cash")
    assert admin.post(path, {"amount": "100"}, format="json").status_code == 409


# No-shows


def test_a_no_show_gets_the_no_show_percent_once(booker, accepted, admin, clock, takes_bookings):
    takes_bookings.booking_no_show_credit_percent = 20
    takes_bookings.save()
    booking = accepted()
    pay_cash(booking, admin)
    clock(booking.ends_at + dt.timedelta(minutes=1))

    assert services.settle_ended() == 1
    assert services.settle_ended() == 0

    assert ledger.booking_credit(booking.club, booker.user) == D("120.00")
    assert booking.events.filter(kind=BookingEvent.Kind.NO_SHOW).count() == 1


def test_someone_who_came_is_not_a_no_show(booker, accepted, admin, clock, takes_bookings):
    takes_bookings.booking_no_show_credit_percent = 20
    takes_bookings.save()
    booking = accepted()
    pay_cash(booking, admin)
    barcode, _ = barcodes.current_for_booking(booking)
    BarcodeScan.objects.create(
        club=booking.club,
        barcode=barcode,
        code=barcode.code,
        method=BarcodeScan.Method.MANUAL,
        scanned_by=admin.user,
        result=BarcodeScan.Result.PAID,
    )
    clock(booking.ends_at + dt.timedelta(minutes=1))

    assert services.settle_ended() == 1
    assert ledger.booking_credit(booking.club, booker.user) == D("0.00")
    assert not booking.events.filter(kind=BookingEvent.Kind.NO_SHOW).exists()


# The engine


def test_late_cancel_hours_past_the_cutoff_leave_no_late_window(accepted, takes_bookings, clock):
    takes_bookings.booking_late_cancel_hours = 30
    takes_bookings.save()
    booking = accepted()
    clock(before(booking, 23))
    assert policy.window(booking) == policy.Window.VERY_LATE
    assert [row.window for row in policy.rows(takes_bookings)] == ["free", "very_late", "club"]
