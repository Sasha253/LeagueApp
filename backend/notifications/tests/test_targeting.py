"""Every targeting rule in the PRD ("Notifications", "Targeting rules")."""

import pytest

from accounts.models import ClubRole
from clubs.models import Field, Night
from notifications import targeting
from notifications.models import Kind


def emails(users):
    return sorted(u.email.split("@")[0] for u in users)


@pytest.fixture
def outsiders(player, friday_division):
    """Players opted into Tuesday who are in neither Team, and one opted into Friday only."""
    return {
        "lerato": player("lerato"),  # outfield
        "bongani": player("bongani", "goalkeeper"),
        "zanele": player("zanele", "both"),
        "fridayonly": player("fridayonly", nights=[friday_division.night]),
        "nonights": player("nonights", nights=[]),
    }


@pytest.fixture
def officials(club_a, club_b, make_user, give_role, pitch):
    """Two Admins and a second Referee of Club A, and Club B's Admin and Referee."""
    people = {}
    for name, club, role in [
        ("admin1", club_a, ClubRole.Role.ADMIN),
        ("admin2", club_a, ClubRole.Role.ADMIN),
        ("otherref", club_a, ClubRole.Role.REFEREE),
        ("badmin", club_b, ClubRole.Role.ADMIN),
        ("bref", club_b, ClubRole.Role.REFEREE),
    ]:
        people[name] = make_user(f"{name}@example.com", name=name)
        give_role(people[name], club, role)
    return people


# Night opt-ins


@pytest.mark.django_db
def test_players_of_both_teams_get_confirmations(match):
    fixture, _ = match
    assert emails(targeting.confirmation_recipients(fixture)) == [
        "ayanda",
        "pieter",
        "sipho",
        "thandi",
    ]


@pytest.mark.django_db
def test_a_team_player_who_did_not_opt_into_the_night_gets_nothing(match, friday_division):
    fixture, people = match
    people["sipho"].player_profile.nights.set([friday_division.night])
    people["thandi"].player_profile.nights.clear()  # A Captain is a Player too.

    assert emails(targeting.confirmation_recipients(fixture)) == ["ayanda", "pieter"]
    assert "sipho" not in emails(targeting.reminder_recipients(fixture))
    assert "thandi" not in emails(targeting.team_players(fixture.home_team))


@pytest.mark.django_db
def test_opting_into_the_same_weekday_at_another_club_does_not_count(match, club_b):
    fixture, people = match
    other_tuesday = Night.objects.create(club=club_b, weekday=Night.Weekday.TUESDAY)
    people["sipho"].player_profile.nights.set([other_tuesday])

    assert "sipho" not in emails(targeting.confirmation_recipients(fixture))


@pytest.mark.django_db
def test_players_who_left_a_team_or_are_inactive_get_nothing(match):
    fixture, people = match
    people["sipho"].team_memberships.update(left_at=fixture.created_at)
    people["ayanda"].is_active = False
    people["ayanda"].save()

    assert emails(targeting.confirmation_recipients(fixture)) == ["pieter", "thandi"]


@pytest.mark.django_db
def test_team_players_is_one_team_only(match):
    fixture, _ = match
    assert emails(targeting.team_players(fixture.away_team)) == ["ayanda", "pieter"]


# Player and Goalkeeper Requests


@pytest.mark.django_db
def test_player_requests_go_to_outfield_players_outside_both_teams(match, outsiders):
    fixture, _ = match
    assert emails(targeting.request_recipients(fixture, Kind.PLAYER_REQUEST)) == [
        "lerato",
        "zanele",
    ]


@pytest.mark.django_db
def test_goalkeeper_requests_go_to_goalkeepers_outside_both_teams(match, outsiders):
    fixture, _ = match
    # Pieter and Ayanda keep goal but are in Old Boys, so they are left out.
    assert emails(targeting.request_recipients(fixture, Kind.GOALKEEPER_REQUEST)) == [
        "bongani",
        "zanele",
    ]


@pytest.mark.django_db
def test_requests_respect_night_opt_ins(match, outsiders):
    fixture, _ = match
    everyone = emails(targeting.players_outside(fixture))
    assert everyone == ["bongani", "lerato", "zanele"]
    assert "fridayonly" not in everyone and "nonights" not in everyone


@pytest.mark.django_db
def test_a_player_in_another_team_of_the_night_can_be_asked(match, outsiders, make_team):
    fixture, _ = match
    make_team("Blue Bulls", outsiders["lerato"], division=fixture.division)
    assert "lerato" in emails(targeting.request_recipients(fixture, Kind.PLAYER_REQUEST))


@pytest.mark.django_db
def test_only_request_kinds_have_request_recipients(match):
    fixture, _ = match
    with pytest.raises(ValueError):
        targeting.request_recipients(fixture, Kind.UPDATE)


# Admins and Referees


@pytest.mark.django_db
def test_reminders_go_to_players_admins_and_the_pitchs_referee(match, officials):
    fixture, _ = match
    assert emails(targeting.reminder_recipients(fixture)) == [
        "admin1",
        "admin2",
        "ayanda",
        "pieter",
        "ref",
        "sipho",
        "thandi",
    ]


@pytest.mark.django_db
def test_reschedule_tells_only_the_nights_admins_and_the_pitchs_referee(match, officials):
    fixture, _ = match
    told = emails(targeting.reschedule_officials(fixture))
    assert told == ["admin1", "admin2", "ref"]
    # Not another Referee of the Club, nor another Club's Admins and Referees.
    assert "otherref" not in told and "badmin" not in told and "bref" not in told
    assert emails(targeting.reschedule_players(fixture)) == ["ayanda", "pieter", "sipho", "thandi"]


@pytest.mark.django_db
def test_a_pitch_change_tells_the_referees_of_both_pitches(match, officials, club_a):
    fixture, _ = match
    old_pitch = fixture.pitch
    fixture.pitch = Field.objects.create(club=club_a, name="Pitch 1", referee=officials["otherref"])
    assert emails(targeting.reschedule_officials(fixture, old_pitch=old_pitch)) == [
        "admin1",
        "admin2",
        "otherref",
        "ref",
    ]


@pytest.mark.django_db
def test_a_referee_who_lost_the_role_is_not_told(match, officials):
    fixture, _ = match
    fixture.pitch.referee.club_roles.all().delete()
    assert emails(targeting.officials(fixture)) == ["admin1", "admin2"]


@pytest.mark.django_db
def test_a_pitch_without_a_referee_tells_the_admins(match, officials):
    fixture, _ = match
    fixture.pitch.referee = None
    assert emails(targeting.reschedule_officials(fixture)) == ["admin1", "admin2"]


@pytest.mark.django_db
def test_booking_notifications_go_to_that_clubs_admins_only(officials, club_a):
    assert emails(targeting.booking_recipients(club_a)) == ["admin1", "admin2"]


@pytest.mark.django_db
def test_admins_and_referees_are_not_filtered_by_night(match, officials, make_user, give_role):
    """An Admin who also plays, without the Night, is still told as an Admin."""
    fixture, _ = match
    playing_admin = make_user("playingadmin@example.com", position="outfield")
    give_role(playing_admin, fixture.club, ClubRole.Role.ADMIN)
    assert "playingadmin" in emails(targeting.officials(fixture))


@pytest.mark.django_db
def test_nobody_is_listed_twice(match, officials, give_role):
    """A Player of the match who is also the club's Admin gets one Reminder."""
    fixture, people = match
    give_role(people["thandi"], fixture.club, ClubRole.Role.ADMIN)
    recipients = list(targeting.reminder_recipients(fixture))
    assert len(recipients) == len({u.pk for u in recipients})
