"""notify(), pushing, content, answering and closing."""

import datetime as dt
from unittest import mock

import pytest
from django.utils import timezone

from core.exceptions import Conflict
from notifications import services, targeting
from notifications.models import DeviceToken, Kind, Notification, PushStatus
from notifications.push import FirebaseSender, PushMessage


def device(user, token, platform="android"):
    return DeviceToken.objects.create(
        user=user, token=token, platform=platform, last_seen_at=timezone.now()
    )


def send(match, kind=Kind.CONFIRMATION, **kwargs):
    fixture, _ = match
    title, body = services.confirmation_content(fixture)
    return services.notify(
        kind,
        targeting.confirmation_recipients(fixture),
        club=fixture.club,
        title=title,
        body=body,
        fixture=fixture,
        **kwargs,
    )


@pytest.mark.django_db
def test_notify_creates_one_per_recipient_and_pushes_after_commit(
    match, fake_push, django_capture_on_commit_callbacks
):
    _, people = match
    device(people["sipho"], "sipho-phone")
    device(people["sipho"], "sipho-tablet", "ios")

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        created = send(match)
    assert fake_push.sent == []  # Nothing goes out before the commit.
    for callback in callbacks:
        callback()

    assert len(created) == 4
    assert sorted(m.token for m in fake_push.sent) == ["sipho-phone", "sipho-tablet"]
    message = fake_push.sent[0]
    assert message.data["kind"] == "confirmation"
    assert message.data["fixture_id"] == str(created[0].fixture_id)
    statuses = dict(Notification.objects.values_list("recipient__email", "push_status"))
    assert statuses["sipho@example.com"] == PushStatus.SENT
    assert statuses["thandi@example.com"] == PushStatus.NO_DEVICE


@pytest.mark.django_db
def test_a_rolled_back_change_pushes_nothing(match, fake_push, django_capture_on_commit_callbacks):
    from django.db import transaction

    _, people = match
    device(people["sipho"], "sipho-phone")
    with (
        django_capture_on_commit_callbacks(execute=True) as callbacks,
        pytest.raises(RuntimeError),
        transaction.atomic(),
    ):
        send(match)
        raise RuntimeError("rolled back")

    assert callbacks == []
    assert fake_push.sent == []
    assert not Notification.objects.exists()


@pytest.mark.django_db
def test_failed_pushes_are_recorded_and_dead_tokens_removed(
    match, fake_push, django_capture_on_commit_callbacks
):
    _, people = match
    device(people["sipho"], "dead")
    device(people["thandi"], "flaky")
    fake_push.invalid = {"dead"}
    fake_push.failing = {"flaky"}

    with django_capture_on_commit_callbacks(execute=True):
        send(match)

    sipho = Notification.objects.get(recipient=people["sipho"])
    thandi = Notification.objects.get(recipient=people["thandi"])
    assert sipho.push_status == PushStatus.FAILED
    assert thandi.push_status == PushStatus.FAILED
    assert thandi.push_error == "Unavailable"
    assert not DeviceToken.objects.filter(token="dead").exists()
    assert DeviceToken.objects.filter(token="flaky").exists()


@pytest.mark.django_db
def test_one_working_device_is_enough(match, fake_push, django_capture_on_commit_callbacks):
    _, people = match
    device(people["sipho"], "flaky")
    device(people["sipho"], "good")
    fake_push.failing = {"flaky"}

    with django_capture_on_commit_callbacks(execute=True):
        send(match)

    assert Notification.objects.get(recipient=people["sipho"]).push_status == PushStatus.SENT


@pytest.mark.django_db
def test_notify_skips_duplicates_and_refuses_bad_input(match, club_b):
    fixture, people = match
    created = services.notify(
        Kind.UPDATE, [people["sipho"], people["sipho"]], club=fixture.club, title="Moved"
    )
    assert len(created) == 1
    with pytest.raises(ValueError):
        services.notify("shout", [people["sipho"]], club=fixture.club, title="x")
    with pytest.raises(ValueError):
        services.notify(Kind.UPDATE, [people["sipho"]], club=club_b, title="x", fixture=fixture)


@pytest.mark.django_db
def test_content_is_in_south_african_time(match):
    fixture, _ = match
    title, body = services.confirmation_content(fixture)
    assert title == "Red Lions vs Old Boys"
    day = f"{fixture.kick_off.astimezone(services.SOUTH_AFRICA):%a}"
    assert body.startswith(day) and "19:40" in body
    title, body = services.reminder_content(fixture)
    assert body.endswith("19:40, Pitch 3")


# Answers


@pytest.mark.django_db
def test_answering_records_it_and_can_be_changed(match):
    notification = send(match)[0]
    received = []

    def listener(notification, previous, **kwargs):
        received.append((notification.answer, previous))

    services.notification_answered.connect(listener)
    try:
        services.answer(notification, "confirm")
        services.answer(notification, "confirm")  # Same answer: nothing new.
        services.answer(notification, "decline")
    finally:
        services.notification_answered.disconnect(listener)

    notification.refresh_from_db()
    assert notification.answer == "decline"
    assert notification.read_at is not None
    assert received == [("confirm", ""), ("decline", "confirm")]


@pytest.mark.django_db
def test_only_the_kinds_answers_are_taken(match):
    confirmation = send(match)[0]
    with pytest.raises(Conflict):
        services.answer(confirmation, "accept")
    update = send(match, Kind.UPDATE)[0]
    with pytest.raises(Conflict):
        services.answer(update, "confirm")


@pytest.mark.django_db
def test_no_answer_after_the_cutoff_or_once_closed(match):
    late = send(match, answer_by=timezone.now() - dt.timedelta(minutes=1))[0]
    with pytest.raises(Conflict):
        services.answer(late, "confirm")

    request = send(match, Kind.PLAYER_REQUEST)
    assert services.close(Notification.objects.filter(kind=Kind.PLAYER_REQUEST)) == 4
    with pytest.raises(Conflict):
        services.answer(request[0], "accept")


@pytest.mark.django_db
def test_mark_read_keeps_the_first_time(match):
    notification = send(match)[0]
    first = services.mark_read(notification).read_at
    assert services.mark_read(notification).read_at == first


# The Firebase sender, with firebase-admin mocked


def test_firebase_sender_maps_results(settings):
    from firebase_admin import messaging

    settings.FIREBASE_CREDENTIALS_JSON = ""
    settings.FIREBASE_CREDENTIALS_FILE = ""
    sent_ok = mock.Mock(success=True, exception=None)
    dead = mock.Mock(success=False, exception=messaging.UnregisteredError("gone"))
    flaky = mock.Mock(success=False, exception=RuntimeError("busy"))
    response = mock.Mock(responses=[sent_ok, dead, flaky])
    messages = [PushMessage(t, "Title", "Body", {"kind": "update"}) for t in "abc"]

    with (
        mock.patch.object(FirebaseSender, "_app", return_value=object()),
        mock.patch.object(messaging, "send_each", return_value=response) as send_each,
    ):
        results = FirebaseSender().send(messages)

    assert [(r.ok, r.token_invalid) for r in results] == [
        (True, False),
        (False, True),
        (False, False),
    ]
    assert send_each.call_args.args[0][0].token == "a"


def test_firebase_sender_without_credentials_fails_every_push(settings):
    settings.FIREBASE_CREDENTIALS_JSON = ""
    settings.FIREBASE_CREDENTIALS_FILE = ""
    results = FirebaseSender().send([PushMessage("a", "T", "B")])
    assert not results[0].ok
    assert "FIREBASE_CREDENTIALS" in results[0].error


@pytest.mark.django_db
def test_a_push_that_raises_never_fails_the_action(
    match, fake_push, django_capture_on_commit_callbacks, monkeypatch
):
    from notifications import push as push_module

    class Broken(push_module.PushSender):
        def send(self, messages):
            raise RuntimeError("Firebase down")

    monkeypatch.setattr("notifications.services.get_sender", lambda: Broken())
    _, people = match
    device(people["sipho"], "sipho-phone")
    with django_capture_on_commit_callbacks(execute=True):
        created = send(match)

    assert len(created) == 4  # Saved and in the inbox; the push stays pending for a retry.
    sipho = Notification.objects.get(recipient=people["sipho"])
    assert sipho.push_status == PushStatus.PENDING
