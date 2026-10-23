"""A Captain requests a Team; the club's Admin confirms or declines it and assigns Captains."""

import datetime as dt

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import ClubRole
from clubs.models import Division, Season
from teams.models import Team, TeamMembership

TEAMS = reverse("api-v1:teams-list")


def club_teams(club):
    return reverse("api-v1:club-teams-list", kwargs={"club_id": club.pk})


def club_team(club, team, action=None):
    name = f"api-v1:club-teams-{action}" if action else "api-v1:club-teams-detail"
    return reverse(name, kwargs={"club_id": club.pk, "pk": team.pk})


def ask(client, season, division, name="Red Lions"):
    return client.post(
        TEAMS, {"season": season.pk, "division": division.pk, "name": name}, format="json"
    )


# Requesting a Team


@pytest.mark.django_db
def test_a_player_requests_a_team_and_becomes_its_captain(player, season, division):
    sipho = player("sipho")

    answer = ask(sipho, season, division, "  Red Lions ")

    assert answer.status_code == 201
    body = answer.json()
    assert body["name"] == "Red Lions"
    assert body["status"] == "requested"
    assert body["captain_id"] == sipho.user.pk
    assert body["players"] == 1
    assert body["weekday"] == 1
    team = Team.objects.get(pk=body["id"])
    assert team.requested_by == sipho.user
    assert team.current_memberships().get().player == sipho.user
    me = sipho.get(reverse("api-v1:me")).json()
    assert me["captain_of"] == [team.pk]


@pytest.mark.django_db
def test_only_players_request_teams(make_user, api, season, division):
    hirer = make_user("hirer@example.com", booking=True)
    api.force_authenticate(hirer)

    assert ask(api, season, division).status_code == 403


@pytest.mark.django_db
def test_no_team_until_the_league_fee_is_set(player, season, division):
    settings = division.night.club.settings
    settings.league_fee = None
    settings.save()

    answer = ask(player("sipho"), season, division)

    assert answer.status_code == 400
    assert "league fee" in answer.json()["division"][0]


@pytest.mark.django_db
def test_a_divisions_own_fee_is_enough(player, season, division):
    settings = division.night.club.settings
    settings.league_fee = None
    settings.save()
    division.league_fee = 400
    division.save()

    assert ask(player("sipho"), season, division).status_code == 201


@pytest.mark.django_db
def test_no_team_in_an_ended_season_or_another_clubs_division(player, club_b, season, division):
    sipho = player("sipho")
    today = timezone.localdate()
    ended = Season.objects.create(
        club=season.club,
        name="Autumn",
        starts_on=today - dt.timedelta(days=90),
        ends_on=today - dt.timedelta(days=1),
    )
    other = Season.objects.create(club=club_b, name="Spring", starts_on=today, ends_on=today)

    assert "season" in ask(sipho, ended, division).json()
    assert "division" in ask(sipho, other, division).json()


@pytest.mark.django_db
def test_team_names_are_unique_per_division_and_season(
    player, make_team, season, division, friday_division
):
    make_team("Red Lions", player("thabo").user)

    same = ask(player("sipho"), season, division, "red lions")
    other_division = ask(player("lerato"), season, friday_division, "Red Lions")

    assert same.status_code == 400 and "name" in same.json()
    assert other_division.status_code == 201


@pytest.mark.django_db
def test_a_declined_teams_name_can_be_used_again(player, make_team, season, division):
    make_team("Red Lions", player("thabo").user, status=Team.Status.DECLINED)

    assert ask(player("sipho"), season, division).status_code == 201


@pytest.mark.django_db
def test_one_team_per_division_and_season(player, make_team, season, division, friday_division):
    sipho = player("sipho")
    make_team("Old Boys", player("thabo").user, sipho.user)

    same_division = ask(sipho, season, division)
    other_division = ask(sipho, season, friday_division)

    assert same_division.status_code == 409
    assert other_division.status_code == 201


@pytest.mark.django_db
def test_a_full_division_takes_no_more_requests(player, make_team, season, division):
    division.max_teams = 1
    division.save()
    make_team("Old Boys", player("thabo").user)

    assert ask(player("sipho"), season, division).status_code == 409


# Choosing a Season and Division


@pytest.mark.django_db
def test_lists_seasons_that_have_not_ended(player, season, club_b):
    today = timezone.localdate()
    Season.objects.create(
        club=season.club,
        name="Autumn",
        starts_on=today - dt.timedelta(days=90),
        ends_on=today - dt.timedelta(days=1),
    )
    Season.objects.create(club=club_b, name="B Spring", starts_on=today, ends_on=today)
    sipho = player("sipho")

    every_club = sipho.get(reverse("api-v1:seasons")).json()
    one_club = sipho.get(reverse("api-v1:seasons"), {"club": season.club_id}).json()

    assert [s["name"] for s in every_club] == ["Spring", "B Spring"]
    assert [s["name"] for s in one_club] == ["Spring"]


@pytest.mark.django_db
def test_lists_divisions_with_their_teams_this_season(
    player, make_team, season, division, friday_division
):
    division.max_teams = 1
    division.save()
    make_team("Old Boys", player("thabo").user)
    make_team("Red Lions", player("sipho").user, status=Team.Status.REQUESTED)
    url = reverse("api-v1:season-divisions", kwargs={"season_id": season.pk})

    body = player("lerato").get(url).json()

    tuesday, friday = body
    assert tuesday["name"] == "Division 2"
    assert (tuesday["teams"], tuesday["max_teams"], tuesday["is_open"]) == (1, 1, False)
    assert tuesday["effective_league_fee"] == "350.00"
    assert (friday["teams"], friday["is_open"]) == (0, True)


@pytest.mark.django_db
def test_a_division_without_a_fee_is_not_open(player, season, division):
    settings = division.night.club.settings
    settings.league_fee = None
    settings.save()
    url = reverse("api-v1:season-divisions", kwargs={"season_id": season.pk})

    assert player("sipho").get(url).json()[0]["is_open"] is False


# The Admin's queue


@pytest.mark.django_db
def test_admin_sees_only_their_clubs_teams(admin_of, club_a, club_b, player, make_team):
    team = make_team("Red Lions", player("sipho").user, status=Team.Status.REQUESTED)
    make_team("Old Boys", player("thabo").user)
    client = admin_of(club_a)

    waiting = client.get(club_teams(club_a), {"status": "requested"}).json()
    other_admin = admin_of(club_b)

    assert [t["name"] for t in waiting] == ["Red Lions"]
    assert waiting[0]["requested_by_name"] is None
    assert waiting[0]["members"][0]["is_captain"] is True
    assert other_admin.get(club_teams(club_a)).status_code == 403
    assert other_admin.get(club_team(club_a, team)).status_code == 403
    assert other_admin.get(club_teams(club_b)).json() == []


@pytest.mark.django_db
def test_a_referee_cannot_decide_team_requests(
    make_user, give_role, api, club_a, player, make_team
):
    team = make_team("Red Lions", player("sipho").user, status=Team.Status.REQUESTED)
    referee = make_user("ref@example.com")
    give_role(referee, club_a, ClubRole.Role.REFEREE)
    api.force_authenticate(referee)

    assert api.post(club_team(club_a, team, "confirm")).status_code == 403


@pytest.mark.django_db
def test_admin_confirms_a_team_request_once(admin_of, club_a, player, season, division):
    sipho = player("sipho")
    team = Team.objects.get(pk=ask(sipho, season, division).json()["id"])
    client = admin_of(club_a)

    confirmed = client.post(club_team(club_a, team, "confirm"))
    again = client.post(club_team(club_a, team, "confirm"))

    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "active"
    assert confirmed.json()["decided_by_name"] == client.user.name
    assert again.status_code == 409


@pytest.mark.django_db
def test_admin_cannot_confirm_past_the_divisions_max(admin_of, club_a, player, make_team, division):
    team = make_team("Red Lions", player("sipho").user, status=Team.Status.REQUESTED)
    make_team("Old Boys", player("thabo").user)
    division.max_teams = 1
    division.save()

    answer = admin_of(club_a).post(club_team(club_a, team, "confirm"))

    assert answer.status_code == 409
    team.refresh_from_db()
    assert team.status == Team.Status.REQUESTED


@pytest.mark.django_db
def test_declining_a_team_frees_its_players(admin_of, club_a, player, season, division):
    sipho = player("sipho")
    team = Team.objects.get(pk=ask(sipho, season, division).json()["id"])

    declined = admin_of(club_a).post(
        club_team(club_a, team, "decline"), {"reason": "Division is full"}, format="json"
    )

    assert declined.status_code == 200
    assert declined.json()["status"] == "declined"
    assert declined.json()["decline_reason"] == "Division is full"
    assert declined.json()["members"] == []
    assert sipho.get(reverse("api-v1:me")).json()["captain_of"] == []
    assert sipho.get(reverse("api-v1:my-teams")).json() == []
    assert ask(sipho, season, division).status_code == 201


@pytest.mark.django_db
def test_an_active_team_cannot_be_declined(admin_of, club_a, player, make_team):
    team = make_team("Red Lions", player("sipho").user)

    assert admin_of(club_a).post(club_team(club_a, team, "decline")).status_code == 409


# Assigning a Captain


@pytest.mark.django_db
def test_admin_assigns_a_player_of_the_team_as_captain(admin_of, club_a, player, make_team):
    sipho, thabo = player("sipho"), player("thabo")
    team = make_team("Red Lions", sipho.user, thabo.user)
    client = admin_of(club_a)

    answer = client.post(
        club_team(club_a, team, "captain"), {"player": thabo.user.pk}, format="json"
    )

    assert answer.status_code == 200
    assert answer.json()["captain_id"] == thabo.user.pk
    assert sorted(m["name"] for m in answer.json()["members"]) == ["Sipho", "Thabo"]
    requests_url = reverse("api-v1:teams-join-requests", kwargs={"pk": team.pk})
    assert thabo.get(requests_url).status_code == 200
    assert sipho.get(requests_url).status_code == 403
    assert sipho.get(reverse("api-v1:me")).json()["captain_of"] == []


@pytest.mark.django_db
def test_the_captain_must_be_in_the_team(admin_of, club_a, player, make_team):
    team = make_team("Red Lions", player("sipho").user)
    lerato = player("lerato")
    former = player("former")
    TeamMembership.objects.create(
        team=team, player=former.user, joined_at=timezone.now(), left_at=timezone.now()
    )
    client = admin_of(club_a)

    for user in (lerato.user, former.user):
        answer = client.post(club_team(club_a, team, "captain"), {"player": user.pk}, format="json")
        assert answer.status_code == 400 and "player" in answer.json()


@pytest.mark.django_db
def test_no_captain_for_a_declined_team(admin_of, club_a, player, make_team):
    thabo = player("thabo")
    team = make_team("Red Lions", player("sipho").user, thabo.user, status=Team.Status.DECLINED)

    answer = admin_of(club_a).post(
        club_team(club_a, team, "captain"), {"player": thabo.user.pk}, format="json"
    )

    assert answer.status_code == 409


@pytest.mark.django_db
def test_division_max_teams_is_set_by_the_admin(admin_of, club_a, division):
    url = reverse("api-v1:club-divisions-detail", kwargs={"club_id": club_a.pk, "pk": division.pk})

    answer = admin_of(club_a).patch(url, {"max_teams": 8}, format="json")

    assert answer.json()["max_teams"] == 8
    assert Division.objects.get(pk=division.pk).max_teams == 8
