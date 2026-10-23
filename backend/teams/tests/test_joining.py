"""Players search Teams, ask to join, and leave; the Captain accepts or declines."""

import datetime as dt

import pytest
from django.urls import reverse
from django.utils import timezone

from clubs.models import Division, Night, Season
from teams.models import JoinRequest, Team, TeamMembership

TEAMS = reverse("api-v1:teams-list")
MY_TEAMS = reverse("api-v1:my-teams")
MY_REQUESTS = reverse("api-v1:my-join-requests")


def team_url(team, action):
    return reverse(f"api-v1:teams-{action}", kwargs={"pk": team.pk})


def request_url(join_request, action):
    return reverse(f"api-v1:join-requests-{action}", kwargs={"pk": join_request.pk})


def asks(client, team) -> JoinRequest:
    answer = client.post(team_url(team, "join"))
    assert answer.status_code == 201, answer.json()
    return JoinRequest.objects.get(pk=answer.json()["id"])


# Searching


@pytest.mark.django_db
def test_search_finds_active_teams_at_every_club(player, make_team, club_b, season):
    make_team("Red Lions", player("sipho").user)
    make_team("Red Stars", player("thabo").user, status=Team.Status.REQUESTED)
    make_team("Old Boys", player("lerato").user, status=Team.Status.DECLINED)
    friday_b = Night.objects.create(club=club_b, weekday=Night.Weekday.FRIDAY)
    other = make_team(
        "Red Devils",
        player("zanele").user,
        season=Season.objects.create(
            club=club_b, name="B", starts_on=season.starts_on, ends_on=season.ends_on
        ),
        division=Division.objects.create(night=friday_b, name="One", min_players=5),
    )
    naledi = player("naledi")

    every = naledi.get(TEAMS, {"q": "red"}).json()
    at_b = naledi.get(TEAMS, {"club": club_b.pk}).json()

    assert [t["name"] for t in every] == ["Red Devils", "Red Lions"]
    assert every[1]["captain_name"] == "Sipho"
    assert every[1]["club"]["name"] == "Club A"
    assert every[1]["division"]["name"] == "Division 2"
    assert every[1]["players"] == 1
    assert [t["id"] for t in at_b] == [other.pk]


@pytest.mark.django_db
def test_search_filters_by_night_and_division_and_skips_ended_seasons(
    player, make_team, season, division, friday_division
):
    today = timezone.localdate()
    ended = Season.objects.create(
        club=season.club,
        name="Autumn",
        starts_on=today - dt.timedelta(days=90),
        ends_on=today - dt.timedelta(days=1),
    )
    make_team("Red Lions", player("sipho").user)
    make_team("Old Boys", player("thabo").user, division=friday_division)
    make_team("Has Beens", player("lerato").user, season=ended)
    naledi = player("naledi")

    def names(**params):
        return [t["name"] for t in naledi.get(TEAMS, params).json()]

    assert names() == ["Old Boys", "Red Lions"]
    assert names(night=friday_division.night_id) == ["Old Boys"]
    assert names(division=division.pk) == ["Red Lions"]
    assert names(season=ended.pk) == ["Has Beens"]


@pytest.mark.django_db
def test_only_players_search(make_user, api):
    api.force_authenticate(make_user("hirer@example.com", booking=True))

    assert api.get(TEAMS).status_code == 403


# Asking to join


@pytest.mark.django_db
def test_the_captain_accepts_a_player(player, make_team):
    sipho, naledi = player("sipho"), player("naledi", "goalkeeper")
    team = make_team("Red Lions", sipho.user)
    join_request = asks(naledi, team)

    queue = sipho.get(team_url(team, "join-requests")).json()
    accepted = sipho.post(request_url(join_request, "accept"))

    assert [(r["player_name"], r["position"]) for r in queue] == [("Naledi", "goalkeeper")]
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    assert team.current_memberships().filter(player=naledi.user).exists()
    members = naledi.get(team_url(team, "members")).json()
    assert [(m["name"], m["is_captain"]) for m in members] == [("Naledi", False), ("Sipho", True)]
    assert sipho.get(team_url(team, "join-requests")).json() == []


@pytest.mark.django_db
def test_the_captain_declines_a_player(player, make_team):
    sipho, naledi = player("sipho"), player("naledi")
    team = make_team("Red Lions", sipho.user)
    join_request = asks(naledi, team)

    declined = sipho.post(request_url(join_request, "decline"))
    again = sipho.post(request_url(join_request, "accept"))

    assert declined.json()["status"] == "declined"
    assert again.status_code == 409
    assert not team.current_memberships().filter(player=naledi.user).exists()
    assert naledi.get(MY_REQUESTS).json()[0]["status"] == "declined"


@pytest.mark.django_db
def test_only_the_captain_answers(player, make_team):
    sipho, thabo, naledi = player("sipho"), player("thabo"), player("naledi")
    team = make_team("Red Lions", sipho.user, thabo.user)
    join_request = asks(naledi, team)

    assert naledi.post(request_url(join_request, "accept")).status_code == 403
    assert thabo.post(request_url(join_request, "accept")).status_code == 404
    assert thabo.get(team_url(team, "join-requests")).status_code == 403


@pytest.mark.django_db
def test_no_asking_twice_or_when_already_in(player, make_team):
    sipho, naledi = player("sipho"), player("naledi")
    team = make_team("Red Lions", sipho.user)
    asks(naledi, team)

    assert naledi.post(team_url(team, "join")).status_code == 409
    assert sipho.post(team_url(team, "join")).status_code == 409


@pytest.mark.django_db
def test_no_joining_a_team_waiting_for_the_admin(player, make_team):
    team = make_team("Red Lions", player("sipho").user, status=Team.Status.REQUESTED)

    assert player("naledi").post(team_url(team, "join")).status_code == 404


@pytest.mark.django_db
def test_no_asking_while_in_another_team_of_the_division(player, make_team, friday_division):
    naledi = player("naledi")
    make_team("Old Boys", player("thabo").user, naledi.user)
    same = make_team("Red Lions", player("sipho").user)
    other = make_team("Friday FC", player("lerato").user, division=friday_division)

    assert naledi.post(team_url(same, "join")).status_code == 409
    assert naledi.post(team_url(other, "join")).status_code == 201


@pytest.mark.django_db
def test_joining_one_team_withdraws_the_other_requests_in_its_division(
    player, make_team, friday_division
):
    sipho, thabo, naledi = player("sipho"), player("thabo"), player("naledi")
    lions = make_team("Red Lions", sipho.user)
    boys = make_team("Old Boys", thabo.user)
    friday = make_team("Friday FC", player("lerato").user, division=friday_division)
    to_lions, to_boys, to_friday = asks(naledi, lions), asks(naledi, boys), asks(naledi, friday)

    sipho.post(request_url(to_lions, "accept"))

    to_boys.refresh_from_db()
    to_friday.refresh_from_db()
    assert to_boys.status == JoinRequest.Status.WITHDRAWN
    assert to_friday.status == JoinRequest.Status.PENDING
    assert thabo.post(request_url(to_boys, "accept")).status_code == 409


@pytest.mark.django_db
def test_accepting_fails_once_the_player_joined_another_team_of_the_division(player, make_team):
    sipho, naledi = player("sipho"), player("naledi")
    lions = make_team("Red Lions", sipho.user)
    join_request = asks(naledi, lions)
    # Joined another Team some other way, e.g. by requesting it as Captain before the change.
    make_team("Old Boys", player("thabo").user, naledi.user)

    assert sipho.post(request_url(join_request, "accept")).status_code == 409


@pytest.mark.django_db
def test_a_player_withdraws_only_their_own_request(player, make_team):
    sipho, naledi, thabo = player("sipho"), player("naledi"), player("thabo")
    team = make_team("Red Lions", sipho.user)
    join_request = asks(naledi, team)

    assert sipho.post(request_url(join_request, "withdraw")).status_code == 403
    assert thabo.post(request_url(join_request, "withdraw")).status_code == 404
    withdrawn = naledi.post(request_url(join_request, "withdraw"))

    assert withdrawn.json()["status"] == "withdrawn"
    assert naledi.post(team_url(team, "join")).status_code == 201


# Leaving and history


@pytest.mark.django_db
def test_leaving_keeps_the_history_and_rejoining_starts_anew(player, make_team):
    sipho, naledi = player("sipho"), player("naledi")
    team = make_team("Red Lions", sipho.user, naledi.user)

    left = naledi.post(team_url(team, "leave"))
    sipho.post(request_url(asks(naledi, team), "accept"))

    assert left.status_code == 200 and left.json()["left_at"] is not None
    history = naledi.get(MY_TEAMS).json()
    assert [(h["team"]["name"], h["left_at"] is None) for h in history] == [
        ("Red Lions", True),
        ("Red Lions", False),
    ]
    assert TeamMembership.objects.filter(team=team, player=naledi.user).count() == 2


@pytest.mark.django_db
def test_the_captain_cannot_leave(player, make_team):
    sipho = player("sipho")
    team = make_team("Red Lions", sipho.user)

    assert sipho.post(team_url(team, "leave")).status_code == 409
    assert player("naledi").post(team_url(team, "leave")).status_code == 409


@pytest.mark.django_db
def test_my_teams_lists_teams_at_every_club(player, make_team, friday_division):
    naledi = player("naledi")
    make_team("Red Lions", naledi.user)
    make_team("Friday FC", player("lerato").user, naledi.user, division=friday_division)

    history = naledi.get(MY_TEAMS).json()

    assert {(h["team"]["name"], h["is_captain"]) for h in history} == {
        ("Red Lions", True),
        ("Friday FC", False),
    }


@pytest.mark.django_db
def test_only_the_teams_players_see_who_is_in_it(player, make_team):
    team = make_team("Red Lions", player("sipho").user)

    assert player("naledi").get(team_url(team, "members")).status_code == 403


@pytest.mark.django_db
def test_a_teams_page_counts_each_player_once(player, make_team):
    sipho, thabo, lerato = player("sipho"), player("thabo"), player("lerato")
    active = make_team("Red Lions", sipho.user, thabo.user, lerato.user)
    waiting = make_team(
        "Blue Bulls", player("naledi").user, sipho.user, status=Team.Status.REQUESTED
    )

    assert player("zanele").get(team_url(active, "detail")).json()["players"] == 3
    assert sipho.get(team_url(active, "detail")).json()["players"] == 3
    assert sipho.get(team_url(waiting, "detail")).json()["players"] == 2
