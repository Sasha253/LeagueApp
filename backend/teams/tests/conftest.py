import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from clubs.models import Division, Night, Season
from teams.models import Team, TeamMembership


@pytest.fixture
def season(club_a):
    today = timezone.localdate()
    return Season.objects.create(
        club=club_a,
        name="Spring",
        starts_on=today - dt.timedelta(days=30),
        ends_on=today + dt.timedelta(days=60),
    )


@pytest.fixture
def division(tuesday):
    settings = tuesday.club.settings
    settings.league_fee = Decimal("350")
    settings.save()
    return Division.objects.create(night=tuesday, name="Division 2", min_players=5)


@pytest.fixture
def player(make_user):
    """A Player signed in on a fresh API client: `player("sipho")`."""

    def make(name, position="outfield"):
        user = make_user(f"{name}@example.com", position=position, name=name.title())
        client = APIClient()
        client.force_authenticate(user)
        client.user = user
        return client

    return make


@pytest.fixture
def make_team(season, division):
    """An active Team, captained by `captain`, with `players` in it."""

    def make(name, captain, *players, status=Team.Status.ACTIVE, **where):
        where.setdefault("season", season)
        where.setdefault("division", division)
        team = Team.objects.create(
            club=where["season"].club, name=name, captain=captain, status=status, **where
        )
        for user in (captain, *players):
            TeamMembership.objects.create(team=team, player=user, joined_at=timezone.now())
        return team

    return make


@pytest.fixture
def friday_division(club_a):
    friday = Night.objects.create(club=club_a, weekday=Night.Weekday.FRIDAY)
    return Division.objects.create(night=friday, name="Division 1", min_players=5)
