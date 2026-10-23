"""Only a Club's own Admins read or change its setup (CLAUDE.md: every club's data is its own)."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import ClubInvite, ClubRole
from clubs.models import Division, Field, Night, Season

COLLECTIONS = ["seasons", "nights", "divisions", "fields", "members", "invites"]


@pytest.fixture
def club_a_records(club_a, admin_of, make_user):
    admin = admin_of(club_a).user
    night = Night.objects.create(club=club_a, weekday=Night.Weekday.TUESDAY)
    return {
        "seasons": Season.objects.create(
            club=club_a, name="Spring", starts_on="2026-08-04", ends_on="2026-11-24"
        ),
        "nights": night,
        "divisions": Division.objects.create(night=night, name="Division 1", min_players=5),
        "fields": Field.objects.create(club=club_a, name="Pitch 1"),
        "members": ClubRole.objects.get(user=admin, club=club_a),
        "invites": ClubInvite.objects.create(club=club_a, email="new@example.com", role="referee"),
    }


def outsiders(club_a, club_b, admin_of, make_user, give_role):
    other_admin = admin_of(club_b)
    referee = make_user("ref@example.com")
    give_role(referee, club_a, ClubRole.Role.REFEREE)
    player = make_user("player@example.com", position="outfield")
    clients = {"other club's Admin": other_admin, "anonymous": APIClient()}
    for name, user in {"club_a Referee": referee, "Player": player}.items():
        clients[name] = APIClient()
        clients[name].force_authenticate(user)
    return clients


@pytest.mark.django_db
def test_nobody_but_the_clubs_admins_gets_in(
    club_a, club_b, club_a_records, admin_of, make_user, give_role
):
    settings_url = reverse("api-v1:club-settings", kwargs={"club_id": club_a.pk})
    for who, client in outsiders(club_a, club_b, admin_of, make_user, give_role).items():
        denied = {401, 403}
        assert client.get(settings_url).status_code in denied, who
        assert client.patch(settings_url, {"league_fee": "1"}).status_code in denied, who
        for name, record in club_a_records.items():
            kwargs = {"club_id": club_a.pk}
            list_url = reverse(f"api-v1:club-{name}-list", kwargs=kwargs)
            detail_url = reverse(f"api-v1:club-{name}-detail", kwargs={**kwargs, "pk": record.pk})
            assert client.get(list_url).status_code in denied, (who, name)
            assert client.post(list_url, {}).status_code in denied, (who, name)
            assert client.delete(detail_url).status_code in denied, (who, name)

    club_a.settings.refresh_from_db()
    assert club_a.settings.league_fee is None
    for record in club_a_records.values():
        assert type(record).objects.filter(pk=record.pk).exists()


@pytest.mark.django_db
def test_an_admin_cant_reach_another_clubs_records_through_their_own_club(
    club_a, club_b, club_a_records, admin_of
):
    client = admin_of(club_b)
    for name in ["seasons", "nights", "divisions", "fields", "members", "invites"]:
        record = club_a_records[name]
        url = reverse(f"api-v1:club-{name}-detail", kwargs={"club_id": club_b.pk, "pk": record.pk})
        assert client.delete(url).status_code == 404, name
        if name not in ("members", "invites"):
            assert client.get(url).status_code == 404, name
            assert client.patch(url, {"name": "Taken"}, format="json").status_code in (404, 405)
        list_url = reverse(f"api-v1:club-{name}-list", kwargs={"club_id": club_b.pk})
        assert record.pk not in [row["id"] for row in client.get(list_url).json()], name

    for record in club_a_records.values():
        assert type(record).objects.filter(pk=record.pk).exists()


@pytest.mark.django_db
def test_lists_show_only_the_clubs_own_records(club_a, club_b, admin_of):
    Season.objects.create(
        club=club_b, name="B season", starts_on="2026-01-01", ends_on="2026-02-01"
    )
    Field.objects.create(club=club_b, name="B pitch")
    Night.objects.create(club=club_b, weekday=Night.Weekday.MONDAY)
    client = admin_of(club_a)

    for name in COLLECTIONS:
        url = reverse(f"api-v1:club-{name}-list", kwargs={"club_id": club_a.pk})
        rows = client.get(url).json()
        assert all("B " not in str(row) for row in rows), name
