"""Shared pytest fixtures for every app's tests."""

import pytest
from rest_framework.test import APIClient

from accounts.models import ClubRole, PlayerProfile, User
from clubs.models import Club, Night

PASSWORD = "floodlit-pitch-19"


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def make_user(db):
    def make(email="player@example.com", *, position=None, booking=False, **fields):
        fields.setdefault("name", "Sipho Dlamini")
        user = User.objects.create_user(email, PASSWORD, is_booking_user=booking, **fields)
        if position:
            PlayerProfile.objects.create(user=user, position=position)
        return user

    return make


@pytest.fixture
def club_a(db):
    return Club.objects.create(name="Club A")


@pytest.fixture
def club_b(db):
    return Club.objects.create(name="Club B")


@pytest.fixture
def tuesday(club_a):
    return Night.objects.create(club=club_a, weekday=Night.Weekday.TUESDAY)


@pytest.fixture
def give_role():
    def give(user, club, role):
        return ClubRole.objects.create(user=user, club=club, role=role)

    return give
