import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from bookings import services
from clubs.models import Field
from fixtures.tests import conftest as fixture_fixtures

pitch = fixture_fixtures.pitch
make_fixture = fixture_fixtures.make_fixture
season = fixture_fixtures.season
division = fixture_fixtures.division
make_team = fixture_fixtures.make_team
lions_and_boys = fixture_fixtures.lions_and_boys
next_tuesday = fixture_fixtures.next_tuesday


def at(date: dt.date, hour: int) -> dt.datetime:
    """`hour`:00 South African time on `date`."""
    return timezone.make_aware(dt.datetime.combine(date, dt.time(hour)))


@pytest.fixture
def takes_bookings(club_a):
    """Club A charges R 600 an hour, and a league match holds its pitch for 60 minutes."""
    club_settings = club_a.settings
    club_settings.booking_hourly_fee = Decimal("600")
    club_settings.match_length_minutes = 60
    club_settings.save()
    return club_settings


@pytest.fixture
def day(next_tuesday):
    """Next Tuesday: the league plays then too, so clashes can be tested."""
    return next_tuesday


@pytest.fixture
def pitch_4(club_a):
    return Field.objects.create(club=club_a, name="Pitch 4")


@pytest.fixture
def booker(make_user):
    """A Booking User, signed in."""
    user = make_user("hirer@example.com", booking=True, name="Hannah Hirer")
    client = APIClient()
    client.force_authenticate(user)
    client.user = user
    return client


@pytest.fixture
def admin(admin_of, club_a):
    return admin_of(club_a)


@pytest.fixture
def book(takes_bookings, pitch, day):
    """A pending Booking by `user` (Pitch 3 next Tuesday at 18:00 for 1 hour by default)."""

    def make(user, *, field=None, hour=18, hours=1, date=None):
        return services.request(
            user=user,
            club=takes_bookings.club,
            field=field or pitch,
            starts_at=at(date or day, hour),
            hours=hours,
        )

    return make
