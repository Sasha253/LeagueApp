"""The Admin adds a Team with its Captain, and invites people to play in a Team by email."""

import datetime as dt

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from ledger.models import LedgerEntry
from notifications.models import Notification
from teams.models import JoinRequest, Team, TeamInvite

ME = reverse("api-v1:me")
REGISTER = reverse("api-v1:register")


def club_teams(club):
    return reverse("api-v1:club-teams-list", kwargs={"club_id": club.pk})


def invites(club, invite=None):
    if invite is None:
        return reverse("api-v1:club-team-invites-list", kwargs={"club_id": club.pk})
    return reverse("api-v1:club-team-invites-detail", kwargs={"club_id": club.pk, "pk": invite.pk})


def add(client, club, season, division, captain_email, name="Red Lions"):
    return client.post(
        club_teams(club),
        {
            "season": season.pk,
            "division": division.pk,
            "name": name,
            "captain_email": captain_email,
        },
        format="json",
    )


# Adding a Team


@pytest.mark.django_db
def test_the_admin_adds_a_confirmed_team_with_its_captain(
    admin_of, club_a, season, division, make_user
):
    thandi = make_user("thandi@example.com", position="outfield", name="Thandi")
    thandi.player_profile.nights.add(division.night)
    admin = admin_of(club_a)

    answer = add(admin, club_a, season, division, "  THANDI@example.com ", "  Red Lions ")

    assert answer.status_code == 201
    body = answer.json()
    assert (body["name"], body["status"], body["captain_id"]) == ("Red Lions", "active", thandi.pk)
    assert [m["player_id"] for m in body["members"]] == [thandi.pk]
    team = Team.objects.get(pk=body["id"])
    assert team.decided_by == admin.user
    charge = LedgerEntry.objects.get(team=team)
    assert charge.amount == 350
    told = Notification.objects.get(recipient=thandi)
    assert told.kind == "update"
    assert told.title == "You're Captain of Red Lions"


@pytest.mark.django_db
def test_a_captain_who_skipped_the_night_is_not_told(admin_of, club_a, season, division, make_user):
    make_user("thandi@example.com", position="outfield")

    assert add(admin_of(club_a), club_a, season, division, "thandi@example.com").status_code == 201
    assert not Notification.objects.exists()


@pytest.mark.django_db
def test_the_captain_must_be_a_player_in_the_app(admin_of, club_a, season, division, make_user):
    make_user("hirer@example.com", booking=True)
    admin = admin_of(club_a)

    for email in ("hirer@example.com", "nobody@example.com"):
        answer = add(admin, club_a, season, division, email)
        assert answer.status_code == 400
        assert "No Player" in answer.json()["captain_email"][0]
    assert not Team.objects.exists()


@pytest.mark.django_db
def test_the_captain_cant_be_in_another_team_of_the_division(
    admin_of, club_a, season, division, make_user, make_team
):
    thandi = make_user("thandi@example.com", position="outfield")
    make_team("Old Boys", thandi)

    answer = add(admin_of(club_a), club_a, season, division, thandi.email)

    assert answer.status_code == 400
    assert "another Team" in answer.json()["captain_email"][0]


@pytest.mark.django_db
def test_the_captains_pending_requests_in_the_division_are_withdrawn(
    admin_of, club_a, season, division, make_user, make_team
):
    pieter = make_user("pieter@example.com", position="goalkeeper")
    thandi = make_user("thandi@example.com", position="outfield")
    asked = JoinRequest.objects.create(team=make_team("Old Boys", pieter), player=thandi)

    assert add(admin_of(club_a), club_a, season, division, thandi.email).status_code == 201
    asked.refresh_from_db()
    assert asked.status == JoinRequest.Status.WITHDRAWN


@pytest.mark.django_db
def test_team_names_stay_unique(admin_of, club_a, season, division, make_user, make_team):
    make_team("Red Lions", make_user("pieter@example.com", position="goalkeeper"))
    make_user("thandi@example.com", position="outfield")

    answer = add(admin_of(club_a), club_a, season, division, "thandi@example.com", "red lions")

    assert answer.status_code == 400
    assert "already has a Team" in answer.json()["name"][0]


@pytest.mark.django_db
def test_a_full_division_takes_no_more_teams(
    admin_of, club_a, season, division, make_user, make_team
):
    division.max_teams = 1
    division.save()
    make_team("Old Boys", make_user("pieter@example.com", position="goalkeeper"))
    make_user("thandi@example.com", position="outfield")

    assert add(admin_of(club_a), club_a, season, division, "thandi@example.com").status_code == 409


@pytest.mark.django_db
def test_no_team_for_an_ended_season(admin_of, club_a, season, division, make_user):
    season.starts_on = timezone.localdate() - dt.timedelta(days=60)
    season.ends_on = timezone.localdate() - dt.timedelta(days=1)
    season.save()
    make_user("thandi@example.com", position="outfield")

    answer = add(admin_of(club_a), club_a, season, division, "thandi@example.com")

    assert answer.status_code == 400
    assert "ended" in answer.json()["season"][0]


@pytest.mark.django_db
def test_another_clubs_season_or_division_is_refused(
    admin_of, club_a, club_b, season, division, make_user
):
    make_user("thandi@example.com", position="outfield")

    answer = add(admin_of(club_b), club_b, season, division, "thandi@example.com")

    assert answer.status_code == 400
    assert set(answer.json()) == {"season", "division"}


@pytest.mark.django_db
def test_only_the_clubs_admins_add_teams(player, club_a, season, division, make_user):
    make_user("thandi@example.com", position="outfield")

    assert add(player("sipho"), club_a, season, division, "thandi@example.com").status_code == 403


# Inviting Players


@pytest.fixture
def lions(make_team, make_user):
    return make_team("Red Lions", make_user("thandi@example.com", position="outfield"))


@pytest.mark.django_db
def test_a_player_in_the_app_joins_at_once(admin_of, club_a, lions, make_user, division):
    sipho = make_user("sipho@example.com", position="outfield", name="Sipho")
    sipho.player_profile.nights.add(division.night)

    answer = admin_of(club_a).post(
        invites(club_a), {"team": lions.pk, "email": "Sipho@Example.com"}, format="json"
    )

    assert answer.status_code == 201
    assert answer.json()["accepted"] is True
    assert answer.json()["team_name"] == "Red Lions"
    assert lions.current_memberships().filter(player=sipho).exists()
    assert lions.captain.email == "thandi@example.com"
    assert Notification.objects.get(recipient=sipho).title == "You're a Player in Red Lions"
    assert mail.outbox == []


@pytest.mark.django_db(transaction=True)
def test_someone_new_gets_an_email_and_joins_when_they_sign_up(
    admin_of, club_a, lions, api, settings
):
    settings.APP_SIGNUP_URL = "https://app.example.com/signup"

    answer = admin_of(club_a).post(invites(club_a), {"team": lions.pk, "email": "new@example.com"})

    assert answer.status_code == 201
    assert answer.json()["accepted"] is False
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["new@example.com"]
    assert "Red Lions" in mail.outbox[0].subject
    assert "https://app.example.com/signup" in mail.outbox[0].body

    signed_up = api.post(
        REGISTER,
        {
            "email": "new@example.com",
            "name": "New Player",
            "password": "floodlit-pitch-19",
            "player": {"position": "outfield"},
        },
        format="json",
    )

    assert signed_up.status_code == 201
    assert lions.current_memberships().filter(player__email="new@example.com").exists()
    assert TeamInvite.objects.get().accepted_at is not None


@pytest.mark.django_db
def test_an_account_that_starts_playing_joins(admin_of, club_a, lions, make_user, api):
    hirer = make_user("hirer@example.com", booking=True)
    admin_of(club_a).post(invites(club_a), {"team": lions.pk, "email": hirer.email})
    assert not lions.current_memberships().filter(player=hirer).exists()

    api.force_authenticate(hirer)
    answer = api.patch(ME, {"player": {"position": "outfield"}}, format="json")

    assert answer.status_code == 200
    assert lions.current_memberships().filter(player=hirer).exists()


@pytest.mark.django_db
def test_an_invite_that_cant_be_met_stays_open(admin_of, club_a, lions, make_team, make_user, api):
    admin_of(club_a).post(invites(club_a), {"team": lions.pk, "email": "new@example.com"})
    new = make_user("new@example.com", booking=True)
    make_team("Old Boys", make_user("pieter@example.com", position="goalkeeper"), new)

    api.force_authenticate(new)
    api.patch(ME, {"player": {"position": "outfield"}}, format="json")

    assert not lions.current_memberships().filter(player=new).exists()
    assert TeamInvite.objects.get().accepted_at is None


@pytest.mark.django_db
def test_the_first_player_of_an_empty_team_is_its_captain(
    admin_of, club_a, season, division, make_user
):
    empty = Team.objects.create(
        club=club_a, season=season, division=division, name="Empty", status="active"
    )
    sipho = make_user("sipho@example.com", position="outfield")

    admin_of(club_a).post(invites(club_a), {"team": empty.pk, "email": sipho.email})

    empty.refresh_from_db()
    assert empty.captain == sipho


@pytest.mark.django_db
def test_no_second_invite_or_member(admin_of, club_a, lions):
    admin = admin_of(club_a)
    admin.post(invites(club_a), {"team": lions.pk, "email": "new@example.com"})

    again = admin.post(invites(club_a), {"team": lions.pk, "email": "NEW@example.com"})
    member = admin.post(invites(club_a), {"team": lions.pk, "email": "thandi@example.com"})

    assert again.status_code == 400
    assert "already invited" in again.json()["email"][0]
    assert member.status_code == 400
    assert "already in this Team" in member.json()["email"][0]


@pytest.mark.django_db
def test_a_player_in_another_team_of_the_division_is_refused(
    admin_of, club_a, lions, make_team, make_user
):
    pieter = make_user("pieter@example.com", position="goalkeeper")
    make_team("Old Boys", pieter)

    answer = admin_of(club_a).post(invites(club_a), {"team": lions.pk, "email": pieter.email})

    assert answer.status_code == 400
    assert not TeamInvite.objects.exists()


@pytest.mark.django_db
def test_no_invites_to_a_team_waiting_for_the_admin(admin_of, club_a, make_team, make_user):
    waiting = make_team(
        "Waiting", make_user("w@example.com", position="outfield"), status="requested"
    )

    answer = admin_of(club_a).post(invites(club_a), {"team": waiting.pk, "email": "x@example.com"})

    assert answer.status_code == 409


@pytest.mark.django_db
def test_the_admin_lists_and_cancels_open_invites(admin_of, club_a, lions, make_user):
    admin = admin_of(club_a)
    make_user("sipho@example.com", position="outfield")
    admin.post(invites(club_a), {"team": lions.pk, "email": "sipho@example.com"})  # Accepted.
    admin.post(invites(club_a), {"team": lions.pk, "email": "new@example.com"})

    listed = admin.get(invites(club_a)).json()

    assert [i["email"] for i in listed] == ["new@example.com"]
    invite = TeamInvite.objects.get(email="new@example.com")
    assert admin.delete(invites(club_a, invite)).status_code == 204
    assert admin.get(invites(club_a)).json() == []


@pytest.mark.django_db
def test_another_clubs_admin_sees_and_invites_nothing(admin_of, club_a, club_b, lions):
    admin_of(club_a).post(invites(club_a), {"team": lions.pk, "email": "new@example.com"})
    other = admin_of(club_b)

    assert other.get(invites(club_b)).json() == []
    answer = other.post(invites(club_b), {"team": lions.pk, "email": "x@example.com"})
    assert answer.status_code == 400
    assert "team" in answer.json()
    invite = TeamInvite.objects.get()
    assert other.delete(invites(club_b, invite)).status_code == 404
