"""The timed checkpoints (FR-1, FR-2, FR-4), on a frozen clock."""

import datetime as dt
from unittest import mock

import pytest
from django.conf import settings
from django.utils import timezone

from accounts.models import ClubRole
from clubs.models import Division
from fixtures import checkpoints, lifecycle
from fixtures.confirmations import answer as answer_confirmation
from fixtures.models import Fixture, FixtureCheckpoint, FixtureTransition
from fixtures.tasks import run_checkpoints
from notifications import services, targeting
from notifications.models import DeviceToken, Kind, Notification, PushStatus
from notifications.tests import conftest as notification_fixtures

# The Notifications tests' pytest fixtures: Players opted into Tuesday, and a match.
player = notification_fixtures.player
match = notification_fixtures.match

S = Fixture.Status
Checkpoint = FixtureCheckpoint.Kind
NOTHING = {kind: 0 for kind in Checkpoint.values}

pytestmark = pytest.mark.django_db


@pytest.fixture
def clock(time_machine):
    """Stops the clock at `fixture.kick_off - hours` (and `minutes`)."""

    def at(fixture, hours=0, minutes=0):
        moment = fixture.kick_off - dt.timedelta(hours=hours, minutes=minutes)
        time_machine.move_to(moment, tick=False)
        return moment

    return at


@pytest.fixture
def admin(club_a, make_user, give_role):
    user = make_user("admin@example.com", name="Ada Admin")
    give_role(user, club_a, ClubRole.Role.ADMIN)
    return user


def ran(**counts):
    return {**NOTHING, **counts}


def confirmations(fixture):
    return Notification.objects.filter(fixture=fixture, kind=Kind.CONFIRMATION)


def device(user, token):
    return DeviceToken.objects.create(
        user=user, token=token, platform="android", last_seen_at=timezone.now()
    )


# T-36h Confirmations (FR-1)


def test_nothing_runs_before_t36h(match, clock):
    fixture, _ = match
    clock(fixture, hours=36, minutes=1)

    assert checkpoints.run_due() == NOTHING
    fixture.refresh_from_db()
    assert fixture.status == S.SCHEDULED
    assert not Notification.objects.exists()


def test_t36h_sends_confirmations_to_every_player_of_both_teams(
    match, clock, fake_push, django_capture_on_commit_callbacks
):
    fixture, people = match
    device(people["thandi"], "thandi-phone")
    now = clock(fixture, hours=36)

    with django_capture_on_commit_callbacks(execute=True):
        assert checkpoints.run_due() == ran(confirmation=1)

    sent = confirmations(fixture)
    assert {n.recipient for n in sent} == set(people.values())
    assert {n.answer_by for n in sent} == {fixture.kick_off - dt.timedelta(hours=6)}
    assert sent.first().title == "Red Lions vs Old Boys"
    assert [m.token for m in fake_push.sent] == ["thandi-phone"]

    fixture.refresh_from_db()
    assert fixture.status == S.CONFIRMING
    move = fixture.transitions.last()
    assert (move.from_status, move.to_status) == (S.SCHEDULED, S.CONFIRMING)
    assert move.cause == FixtureTransition.Cause.CHECKPOINT
    assert move.actor is None
    checkpoint = FixtureCheckpoint.objects.get(fixture=fixture)
    assert (checkpoint.kind, checkpoint.kick_off, checkpoint.ran_at) == (
        Checkpoint.CONFIRMATION,
        fixture.kick_off,
        now,
    )
    assert checkpoint.notified == 4


def test_confirmations_skip_players_not_opted_into_the_night(match, clock):
    fixture, people = match
    people["sipho"].player_profile.nights.clear()
    clock(fixture, hours=36)

    checkpoints.run_due()

    assert people["sipho"] not in {n.recipient for n in confirmations(fixture)}


def test_running_twice_sends_once(match, clock):
    fixture, _ = match
    clock(fixture, hours=36)

    checkpoints.run_due()
    assert checkpoints.run_due() == NOTHING
    assert checkpoints.send_confirmations(fixture.pk) is False

    assert confirmations(fixture).count() == 4
    assert FixtureCheckpoint.objects.count() == 1
    assert fixture.transitions.filter(to_status=S.CONFIRMING).count() == 1


def test_a_checkpoint_already_claimed_is_not_run_again(match, clock):
    """Another worker claimed it first (its row is there): this run does nothing."""
    fixture, _ = match
    now = clock(fixture, hours=36)
    FixtureCheckpoint.objects.create(
        fixture=fixture,
        kind=Checkpoint.CONFIRMATION,
        kick_off=fixture.kick_off,
        ran_at=now,
        notified=4,
    )

    assert checkpoints.send_confirmations(fixture.pk) is False
    assert not Notification.objects.exists()
    fixture.refresh_from_db()
    assert fixture.status == S.SCHEDULED


def test_a_late_run_still_sends_confirmations_before_the_cutoff(match, clock):
    fixture, _ = match
    clock(fixture, hours=20)

    assert checkpoints.run_due() == ran(confirmation=1)
    assert confirmations(fixture).count() == 4


def test_too_late_for_confirmations_after_the_cutoff_but_the_reminder_goes(match, clock):
    fixture, _ = match
    clock(fixture, hours=5)

    assert checkpoints.run_due() == ran(readiness=1, reminder=1)
    assert not confirmations(fixture).exists()
    fixture.refresh_from_db()
    assert fixture.status == S.SCHEDULED  # both Teams wait for the Admin (chunk 13)


@pytest.mark.parametrize("status", [S.CANCELLED, S.ONE_TEAM_OUT, S.FRIENDLY])
def test_fixtures_out_of_the_league_flow_get_no_checkpoints(match, clock, status):
    fixture, _ = match
    Fixture.objects.filter(pk=fixture.pk).update(status=status, friendly_eligible=True)

    clock(fixture, hours=36)
    assert checkpoints.run_due() == NOTHING
    clock(fixture, hours=6)
    assert checkpoints.run_due() == NOTHING
    assert not Notification.objects.exists()


def test_each_club_uses_its_own_hours(match, clock, club_b):
    fixture, _ = match
    club_settings = fixture.club.settings
    club_settings.confirmation_hours_before = 48
    club_settings.confirmation_resend_after_hours = 24
    club_settings.save()
    assert club_b.settings.confirmation_hours_before == 36

    clock(fixture, hours=48, minutes=1)
    assert checkpoints.run_due() == NOTHING
    clock(fixture, hours=48)
    assert checkpoints.run_due() == ran(confirmation=1)
    clock(fixture, hours=24, minutes=1)
    assert checkpoints.run_due() == NOTHING
    clock(fixture, hours=24)
    assert checkpoints.run_due() == ran(resend=1)


def test_a_rescheduled_kick_off_gets_new_checkpoints(match, clock):
    fixture, _ = match
    clock(fixture, hours=36)
    checkpoints.run_due()

    # An Admin reschedule (chunk 16) moves the kick-off a week on and restarts the process.
    lifecycle.transition(fixture, S.SCHEDULED, cause=FixtureTransition.Cause.ADMIN)
    fixture.refresh_from_db()
    fixture.kick_off += dt.timedelta(days=7)
    fixture.save(update_fields=["kick_off"])

    clock(fixture, hours=36)
    assert checkpoints.run_due() == ran(confirmation=1)
    assert confirmations(fixture).count() == 8
    assert FixtureCheckpoint.objects.filter(kind=Checkpoint.CONFIRMATION).count() == 2


def test_one_failing_fixture_does_not_stop_the_others(match, clock, make_fixture):
    fixture, _ = match
    later = make_fixture(fixture.home_team, fixture.away_team, time="20:40")
    real = targeting.confirmation_recipients
    clock(later, hours=36)

    with mock.patch.object(
        checkpoints.targeting,
        "confirmation_recipients",
        side_effect=[RuntimeError("boom"), real(later)],
    ):
        assert checkpoints.run_due() == ran(confirmation=1)

    assert not confirmations(fixture).exists()
    assert confirmations(later).count() == 4
    fixture.refresh_from_db()
    assert fixture.status == S.SCHEDULED
    assert not fixture.checkpoints.exists()
    # The next pass tries the failed one again.
    assert checkpoints.run_due() == ran(confirmation=1)
    assert confirmations(fixture).count() == 4


# Resend (FR-2)


def test_resend_goes_once_to_players_who_have_not_answered(
    match, clock, fake_push, django_capture_on_commit_callbacks
):
    fixture, people = match
    for name, user in people.items():
        device(user, f"{name}-phone")
    clock(fixture, hours=36)
    with django_capture_on_commit_callbacks(execute=True):
        checkpoints.run_due()
    sent = {n.recipient.email.split("@")[0]: n for n in confirmations(fixture)}
    services.answer(sent["sipho"], "confirm")
    services.answer(sent["pieter"], "decline")
    services.mark_read(sent["ayanda"])
    fake_push.reset()

    clock(fixture, hours=24, minutes=1)
    assert checkpoints.run_due() == NOTHING

    now = clock(fixture, hours=24)
    with django_capture_on_commit_callbacks(execute=True):
        assert checkpoints.run_due() == ran(resend=1)

    assert sorted(m.token for m in fake_push.sent) == ["ayanda-phone", "thandi-phone"]
    assert confirmations(fixture).count() == 4  # the same inbox entries, pushed again
    resent = confirmations(fixture).filter(resent_at__isnull=False)
    assert {n.recipient for n in resent} == {people["thandi"], people["ayanda"]}
    assert all(n.read_at is None and n.push_status == PushStatus.SENT for n in resent)
    assert {n.resent_at for n in resent} == {now}
    assert FixtureCheckpoint.objects.get(kind=Checkpoint.RESEND).notified == 2

    fake_push.reset()
    clock(fixture, hours=12)
    with django_capture_on_commit_callbacks(execute=True):
        assert checkpoints.run_due() == NOTHING
    assert fake_push.sent == []


def test_resend_skips_a_player_who_left_the_team(match, clock):
    fixture, people = match
    clock(fixture, hours=36)
    checkpoints.run_due()
    people["sipho"].team_memberships.update(left_at=timezone.now())

    clock(fixture, hours=24)
    checkpoints.run_due()

    resent = confirmations(fixture).filter(resent_at__isnull=False)
    assert people["sipho"] not in {n.recipient for n in resent}
    assert resent.count() == 3


def test_no_resend_once_the_cutoff_has_passed(match, clock):
    """Confirmations sent late, at T-10h: the resend would fall after T-6h, so never."""
    fixture, _ = match
    clock(fixture, hours=10)
    checkpoints.run_due()

    clock(fixture, hours=6, minutes=1)
    assert checkpoints.run_due() == NOTHING
    clock(fixture, hours=6)
    # No one confirmed, so both Teams are out at T-6h and no Reminder goes (chunk 13).
    assert checkpoints.run_due() == ran(readiness=1)
    assert not FixtureCheckpoint.objects.filter(kind=Checkpoint.RESEND).exists()


# T-6h Reminders (FR-4)


def test_t6h_reminds_players_captains_admins_and_the_referee(
    match, clock, admin, pitch, make_user, club_b, give_role
):
    fixture, people = match
    other_admin = make_user("other@example.com", name="Other Club Admin")
    give_role(other_admin, club_b, ClubRole.Role.ADMIN)
    clock(fixture, hours=36)
    checkpoints.run_due()

    clock(fixture, hours=6, minutes=1)
    assert checkpoints.run_due() == ran(resend=1)  # missed at T-24h, caught up before T-6h
    Division.objects.filter(pk=fixture.division_id).update(min_players=2)
    for person in people.values():
        answer_confirmation(fixture, person, "confirm", via="fixture")
    clock(fixture, hours=6)
    assert checkpoints.run_due() == ran(readiness=1, reminder=1)

    reminders = Notification.objects.filter(fixture=fixture, kind=Kind.REMINDER)
    assert {n.recipient for n in reminders} == {*people.values(), admin, pitch.referee}
    title, body = services.reminder_content(fixture)
    assert {(n.title, n.body) for n in reminders} == {(title, body)}
    assert "Pitch 3" in body
    assert all(n.answer_by is None for n in reminders)
    fixture.refresh_from_db()
    assert fixture.status == S.READY  # both Teams have their minimum and owe nothing

    assert checkpoints.run_due() == NOTHING
    assert reminders.count() == 6


def test_no_reminder_after_kick_off(match, clock):
    fixture, _ = match
    clock(fixture, hours=0)

    assert checkpoints.run_due() == NOTHING
    assert not Notification.objects.exists()


# Celery


def test_the_task_runs_the_checkpoints(match, clock):
    fixture, _ = match
    clock(fixture, hours=36)

    result = run_checkpoints.apply().get()

    assert result == ran(confirmation=1)


def test_beat_starts_the_task_every_minute():
    from config.celery import app

    entry = settings.CELERY_BEAT_SCHEDULE["timed-checkpoints"]
    assert entry["task"] == run_checkpoints.name == "fixtures.run_checkpoints"
    assert entry["schedule"] == 60
    assert entry["options"]["expires"] == 60
    assert app.conf.beat_schedule == settings.CELERY_BEAT_SCHEDULE
