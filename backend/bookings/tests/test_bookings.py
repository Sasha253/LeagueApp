"""Booking a field, deciding, cancelling and rescheduling (FR-28 to FR-31)."""

import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from accounts.models import ClubRole
from barcodes.models import Barcode
from bookings import services
from bookings.models import Booking, BookingEvent
from clubs.models import Field
from fixtures.models import Fixture
from notifications.models import Kind, Notification
from notifications.services import answer

from .conftest import at

pytestmark = pytest.mark.django_db

CLUBS = "/api/v1/bookings/clubs/"
FREE = "/api/v1/bookings/availability/"
MINE = "/api/v1/me/bookings/"


def mine(booking_id, what=""):
    return f"{MINE}{booking_id}/{what + '/' if what else ''}"


def club_bookings(club, booking_id=None, what=""):
    base = f"/api/v1/clubs/{club.pk}/bookings/"
    if booking_id is None:
        return base
    return f"{base}{booking_id}/{what + '/' if what else ''}"


def free(client, club, day, hours, **extra):
    query = {"club": club.pk, "date": day.isoformat(), "hours": hours, **extra}
    return client.get(FREE, query)


def starts_of(body, field):
    slots = next(f for f in body["fields"] if f["field"]["id"] == field.pk)
    return [timezone.localtime(dt.datetime.fromisoformat(s)).hour for s in slots["starts"]]


# Clubs and availability (FR-28)


def test_only_clubs_taking_bookings_are_listed(booker, takes_bookings, pitch, club_b):
    Field.objects.create(club=club_b, name="B1")  # Club B has no fee or match length.

    body = booker.get(CLUBS).json()

    assert [c["name"] for c in body] == ["Club A"]
    assert body[0]["hourly_fee"] == "600.00"
    assert body[0]["fields"] == [{"id": pitch.pk, "name": "Pitch 3"}]


def test_only_booking_users_can_book(make_user, api, takes_bookings, pitch, day):
    player = make_user("player@example.com", position="outfield")
    api.force_authenticate(player)

    assert api.get(CLUBS).status_code == 403
    assert free(api, takes_bookings.club, day, 1).status_code == 403
    body = {"club": takes_bookings.club.pk, "field": pitch.pk, "starts_at": at(day, 18), "hours": 1}
    assert api.post(MINE, body, format="json").status_code == 403


def test_availability_leaves_out_matches_bookings_and_late_endings(
    booker, book, make_user, takes_bookings, pitch, pitch_4, day, make_fixture, lions_and_boys
):
    make_fixture(*lions_and_boys, time="19:40")  # Holds Pitch 3 from 19:40 to 20:40.
    other = make_user("other@example.com", booking=True)
    book(other, hour=15, hours=2)  # Pending: holds 15:00 to 17:00.
    declined = book(other, hour=10)
    declined.status = Booking.Status.DECLINED
    declined.save()

    response = free(booker, takes_bookings.club, day, 2)

    assert response.status_code == 200
    body = response.json()
    assert (body["hourly_fee"], body["price"]) == ("600.00", "1200.00")
    hours = starts_of(body, pitch)
    assert 10 in hours  # Declined: free again.
    assert 14 not in hours and 15 not in hours and 16 not in hours
    assert 13 in hours and 17 in hours
    assert 18 not in hours and 19 not in hours and 20 not in hours  # The match.
    assert 21 in hours and 22 in hours and 23 not in hours  # Ends by midnight.
    assert starts_of(body, pitch_4) == list(range(0, 23))


def test_a_cancelled_match_frees_its_pitch(
    booker, takes_bookings, pitch, day, make_fixture, lions_and_boys
):
    make_fixture(*lions_and_boys, time="19:40", status=Fixture.Status.CANCELLED)

    assert 19 in starts_of(free(booker, takes_bookings.club, day, 1).json(), pitch)


def test_times_already_gone_are_not_offered(booker, takes_bookings, pitch):
    today = timezone.localdate()
    hours = starts_of(free(booker, takes_bookings.club, today, 1).json(), pitch)

    assert all(h > timezone.localtime().hour for h in hours)


def test_no_availability_until_the_club_takes_bookings(booker, club_a, pitch, day):
    response = free(booker, club_a, day, 1)

    assert response.status_code == 409
    assert response.json()["detail"] == services.NOT_TAKING


# Requesting (FR-28, FR-29)


def test_booking_user_requests_a_booking_and_every_admin_is_asked(
    booker, admin, admin_of, takes_bookings, pitch, day, fake_push
):
    second = admin_of(takes_bookings.club, "second-admin@example.com")
    body = {"club": takes_bookings.club.pk, "field": pitch.pk, "starts_at": at(day, 18), "hours": 2}

    response = booker.post(MINE, body, format="json")

    assert response.status_code == 201
    data = response.json()
    assert (data["status"], data["hours"], data["price"]) == ("pending", 2, "1200.00")
    assert data["can_cancel"] and data["can_reschedule"]
    booking = Booking.objects.get(pk=data["id"])
    assert booking.ends_at == at(day, 20)
    asked = Notification.objects.filter(booking=booking, kind=Kind.BOOKING)
    assert {n.recipient_id for n in asked} == {admin.user.pk, second.user.pk}
    assert all(n.answer_by == booking.starts_at for n in asked)
    first = asked.first()
    assert first.title == "Booking request: Pitch 3"
    assert "Hannah Hirer" in first.body and "18:00 to 20:00 (2 hours)" in first.body
    assert "R 1,200" in first.body
    assert BookingEvent.objects.get(booking=booking).kind == BookingEvent.Kind.REQUESTED


@pytest.mark.parametrize(
    ("change", "field", "message"),
    [
        ({"minute": 30}, "starts_at", services.ON_THE_HOUR),
        ({"hours": 3, "hour": 22}, "hours", services.PAST_MIDNIGHT),
        ({"hours": 0}, "hours", None),
        ({"hours": 25}, "hours", None),
    ],
)
def test_slot_rules(booker, takes_bookings, pitch, day, change, field, message):
    starts = at(day, change.get("hour", 18)) + dt.timedelta(minutes=change.get("minute", 0))
    body = {
        "club": takes_bookings.club.pk,
        "field": pitch.pk,
        "starts_at": starts,
        "hours": change.get("hours", 1),
    }

    response = booker.post(MINE, body, format="json")

    assert response.status_code == 400
    if message:
        assert response.json()[field] == [message]


def test_a_time_gone_by_is_refused(booker, takes_bookings, pitch):
    past = at(timezone.localdate() - dt.timedelta(days=1), 18)
    body = {"club": takes_bookings.club.pk, "field": pitch.pk, "starts_at": past, "hours": 1}

    response = booker.post(MINE, body, format="json")

    assert response.status_code == 400
    assert response.json()["starts_at"] == [services.IN_THE_PAST]


def test_another_clubs_field_is_refused(booker, takes_bookings, club_b, day):
    theirs = Field.objects.create(club=club_b, name="B1")
    body = {
        "club": takes_bookings.club.pk,
        "field": theirs.pk,
        "starts_at": at(day, 18),
        "hours": 1,
    }

    assert booker.post(MINE, body, format="json").status_code == 400


def test_a_taken_slot_is_refused(booker, book, make_user, takes_bookings, pitch, day):
    book(make_user("other@example.com", booking=True), hour=17, hours=2)
    body = {"club": takes_bookings.club.pk, "field": pitch.pk, "starts_at": at(day, 18), "hours": 1}

    response = booker.post(MINE, body, format="json")

    assert response.status_code == 409
    assert response.json()["detail"] == services.TAKEN


def test_a_slot_overlapping_a_match_is_refused(
    booker, takes_bookings, pitch, day, make_fixture, lions_and_boys
):
    make_fixture(*lions_and_boys, time="19:40")
    body = {"club": takes_bookings.club.pk, "field": pitch.pk, "starts_at": at(day, 20), "hours": 1}

    response = booker.post(MINE, body, format="json")

    assert response.status_code == 409
    assert response.json()["detail"] == services.CLASHES_WITH_MATCH


def test_the_match_length_is_club_data(
    booker, takes_bookings, pitch, day, make_fixture, lions_and_boys
):
    make_fixture(*lions_and_boys, time="19:40")
    takes_bookings.match_length_minutes = 15  # Over at 19:55.
    takes_bookings.save()
    body = {"club": takes_bookings.club.pk, "field": pitch.pk, "starts_at": at(day, 20), "hours": 1}

    assert booker.post(MINE, body, format="json").status_code == 201


def test_no_booking_until_the_club_takes_them(booker, club_a, pitch, day):
    body = {"club": club_a.pk, "field": pitch.pk, "starts_at": at(day, 18), "hours": 1}

    assert booker.post(MINE, body, format="json").status_code == 409


# Who sees what


def test_a_booking_user_sees_only_their_own(booker, book, make_user, api):
    booking = book(booker.user)
    other = make_user("other@example.com", booking=True)
    api.force_authenticate(other)

    assert [b["id"] for b in booker.get(MINE).json()] == [booking.pk]
    assert api.get(MINE).json() == []
    assert api.get(mine(booking.pk)).status_code == 404
    assert api.post(mine(booking.pk, "cancel")).status_code == 404
    assert api.get(mine(booking.pk, "barcode")).status_code == 404


def test_admins_see_only_their_clubs_bookings(booker, book, admin, admin_of, club_b):
    booking = book(booker.user)
    other_admin = admin_of(club_b)

    listed = admin.get(club_bookings(booking.club)).json()
    assert [b["id"] for b in listed] == [booking.pk]
    assert listed[0]["user"]["name"] == "Hannah Hirer"
    assert listed[0]["can_decide"] is True
    assert other_admin.get(club_bookings(booking.club)).status_code == 403
    assert other_admin.get(club_bookings(club_b, booking.pk)).status_code == 404
    assert other_admin.post(club_bookings(club_b, booking.pk, "accept")).status_code == 404
    assert booker.get(club_bookings(booking.club)).status_code == 403


def test_admins_filter_by_status(booker, book, admin, make_user):
    waiting = book(booker.user)
    done = book(make_user("other@example.com", booking=True), hour=10)
    services.decline(done, by=admin.user)

    listed = admin.get(club_bookings(waiting.club), {"status": "pending"}).json()

    assert [b["id"] for b in listed] == [waiting.pk]


# Accepting and declining (FR-29, FR-30)


def test_admin_accepts_and_the_booking_user_gets_a_barcode(booker, book, admin, fake_push):
    booking = book(booker.user)

    response = admin.post(club_bookings(booking.club, booking.pk, "accept"))

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert response.json()["decided_by"]["id"] == admin.user.pk
    barcode = Barcode.objects.get(booking=booking)
    assert (barcode.mode, barcode.team, barcode.season) == ("booking", None, None)
    told = Notification.objects.get(recipient=booker.user, kind=Kind.UPDATE)
    assert told.title == "Booking accepted: Pitch 3"
    assert told.booking_id == booking.pk
    assert not Notification.objects.filter(
        booking=booking, kind=Kind.BOOKING, closed_at=None
    ).exists()
    assert admin.post(club_bookings(booking.club, booking.pk, "accept")).status_code == 409


def test_accepting_a_booking_that_now_clashes_with_a_match_is_refused(
    booker, book, admin, make_fixture, lions_and_boys
):
    booking = book(booker.user, hour=19)
    make_fixture(*lions_and_boys, time="19:40")  # Imported after the request.

    response = admin.post(club_bookings(booking.club, booking.pk, "accept"))

    assert response.status_code == 409
    assert response.json()["detail"] == services.CLASHES_WITH_MATCH


def test_a_booking_that_has_started_cant_be_decided(booker, book, admin):
    booking = book(booker.user)
    Booking.objects.filter(pk=booking.pk).update(
        starts_at=timezone.now() - dt.timedelta(minutes=5),
        ends_at=timezone.now() + dt.timedelta(minutes=55),
    )

    response = admin.post(club_bookings(booking.club, booking.pk, "accept"))

    assert response.status_code == 409


def test_admin_declines_with_a_reason_and_the_field_is_free_again(booker, book, admin, make_user):
    booking = book(booker.user)

    response = admin.post(
        club_bookings(booking.club, booking.pk, "decline"), {"reason": "Pitch resurfacing."}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "declined"
    assert response.json()["decline_reason"] == "Pitch resurfacing."
    told = Notification.objects.get(recipient=booker.user, kind=Kind.UPDATE)
    assert told.title == "Booking declined: Pitch 3"
    assert told.body.endswith("Pitch resurfacing.")
    assert not Barcode.objects.filter(booking=booking).exists()
    book(make_user("other@example.com", booking=True))  # Same slot: free again.


def test_confirming_the_booking_notification_accepts_it(booker, book, admin):
    booking = book(booker.user)
    notification = Notification.objects.get(booking=booking, recipient=admin.user)

    answer(notification, "confirm")

    booking.refresh_from_db()
    assert booking.status == Booking.Status.ACCEPTED
    assert booking.decided_by == admin.user
    assert Barcode.objects.filter(booking=booking, revoked_at=None).exists()


def test_declining_the_booking_notification_declines_it(booker, book, admin, fake_push):
    booking = book(booker.user)
    notification = Notification.objects.get(booking=booking, recipient=admin.user)

    response = admin.post(f"/api/v1/inbox/{notification.pk}/answer/", {"answer": "decline"})

    assert response.status_code == 200
    booking.refresh_from_db()
    assert booking.status == Booking.Status.DECLINED
    # Decided: no Admin can answer it any more.
    response = admin.post(f"/api/v1/inbox/{notification.pk}/answer/", {"answer": "confirm"})
    assert response.status_code == 409


def test_an_admin_who_lost_the_role_cant_decide_from_the_inbox(booker, book, admin):
    booking = book(booker.user)
    notification = Notification.objects.get(booking=booking, recipient=admin.user)
    ClubRole.objects.filter(user=admin.user).delete()

    response = admin.post(f"/api/v1/inbox/{notification.pk}/answer/", {"answer": "confirm"})

    assert response.status_code == 409
    booking.refresh_from_db()
    assert booking.status == Booking.Status.PENDING
    notification.refresh_from_db()
    assert notification.answer == ""


# Cancelling (FR-31)


def test_booking_user_cancels_an_accepted_booking(booker, book, admin):
    booking = book(booker.user)
    services.accept(booking, by=admin.user)

    response = booker.post(mine(booking.pk, "cancel"))

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["can_cancel"] is False
    barcode = Barcode.objects.get(booking=booking)
    assert barcode.revoked_at is not None
    told = Notification.objects.filter(recipient=admin.user, kind=Kind.UPDATE).get()
    assert told.title == "Booking cancelled: Pitch 3"
    assert booker.post(mine(booking.pk, "cancel")).status_code == 409


def test_cancelling_a_waiting_booking_closes_the_admins_question(booker, book, admin):
    booking = book(booker.user)

    booker.post(mine(booking.pk, "cancel"))

    notification = Notification.objects.get(booking=booking, kind=Kind.BOOKING)
    assert notification.closed_at is not None
    assert not Notification.objects.filter(recipient=admin.user, kind=Kind.UPDATE).exists()


def test_a_started_booking_cant_be_cancelled(booker, book):
    booking = book(booker.user)
    Booking.objects.filter(pk=booking.pk).update(starts_at=timezone.now() - dt.timedelta(hours=1))

    response = booker.post(mine(booking.pk, "cancel"))

    assert response.status_code == 409
    assert response.json()["detail"] == services.STARTED


# Rescheduling (FR-31)


def test_rescheduling_moves_it_and_asks_the_admins_again(
    booker, book, admin, pitch_4, day, takes_bookings
):
    booking = book(booker.user, hours=2)
    services.accept(booking, by=admin.user)
    takes_bookings.booking_hourly_fee = Decimal("700")  # The fee it was booked at stands.
    takes_bookings.save()

    response = booker.post(
        mine(booking.pk, "reschedule"),
        {"field": pitch_4.pk, "starts_at": at(day, 19).isoformat(), "hours": 3},
        format="json",
    )

    assert response.status_code == 200
    data = response.json()
    assert (data["status"], data["field"]["name"], data["hours"]) == ("pending", "Pitch 4", 3)
    assert data["price"] == "1800.00"
    assert Barcode.objects.get(booking=booking).revoked_at is not None
    asked = Notification.objects.filter(booking=booking, kind=Kind.BOOKING).order_by("pk")
    assert [n.closed_at is None for n in asked] == [False, True]
    assert asked.last().title == "Booking moved: Pitch 4"
    kinds = list(BookingEvent.objects.filter(booking=booking).values_list("kind", flat=True))
    assert kinds == ["requested", "accepted", "rescheduled"]


def test_rescheduling_into_its_own_time_is_allowed(booker, book, pitch, day):
    booking = book(booker.user, hour=18, hours=2)

    response = booker.post(
        mine(booking.pk, "reschedule"),
        {"field": pitch.pk, "starts_at": at(day, 19).isoformat(), "hours": 2},
        format="json",
    )

    assert response.status_code == 200
    availability = free(booker, booking.club, day, 2, booking=booking.pk).json()
    assert 18 in starts_of(availability, pitch)


def test_rescheduling_to_the_same_slot_or_a_taken_one_is_refused(
    booker, book, make_user, pitch, day
):
    booking = book(booker.user, hour=18)
    book(make_user("other@example.com", booking=True), hour=20)
    same = {"field": pitch.pk, "starts_at": at(day, 18).isoformat(), "hours": 1}
    taken = {"field": pitch.pk, "starts_at": at(day, 20).isoformat(), "hours": 1}

    assert booker.post(mine(booking.pk, "reschedule"), same, format="json").status_code == 400
    assert booker.post(mine(booking.pk, "reschedule"), taken, format="json").status_code == 409


def test_rescheduling_to_another_clubs_field_is_refused(booker, book, club_b, day):
    booking = book(booker.user)
    theirs = Field.objects.create(club=club_b, name="B1")
    body = {"field": theirs.pk, "starts_at": at(day, 18).isoformat(), "hours": 1}

    assert booker.post(mine(booking.pk, "reschedule"), body, format="json").status_code == 400


def test_availability_for_a_reschedule_is_only_for_ones_own_booking(
    booker, book, make_user, api, day
):
    booking = book(booker.user)
    api.force_authenticate(make_user("other@example.com", booking=True))

    assert free(api, booking.club, day, 1, booking=booking.pk).status_code == 404


# The log


def test_booking_events_are_never_changed_or_deleted(booker, book):
    event = BookingEvent.objects.get(booking=book(booker.user))

    with pytest.raises(ValueError):
        event.save()
    with pytest.raises(ValueError):
        event.delete()
    with pytest.raises(ValueError):
        BookingEvent.objects.all().delete()


def test_pushes_carry_the_booking(booker, book, admin):
    from notifications.services import push_data

    booking = book(booker.user)
    notification = Notification.objects.get(booking=booking, recipient=admin.user)

    assert push_data(notification)["booking_id"] == str(booking.pk)
    listed = admin.get(f"/api/v1/inbox/{notification.pk}/").json()
    assert listed["booking_id"] == booking.pk
