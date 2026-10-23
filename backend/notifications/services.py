"""Creating, pushing, reading and answering notifications.

Later chunks call `notify()` with recipients picked in targeting.py. Each recipient gets
their own Notification in the inbox, and the push goes out after the surrounding
transaction commits, so a rolled-back change never notifies anyone.

What an answer does (confirming a Player, filling a request, approving a booking) belongs
to later chunks: they connect to the `notification_answered` signal.
"""

from collections.abc import Iterable
from zoneinfo import ZoneInfo

from django.db import transaction
from django.dispatch import Signal
from django.utils import timezone

from core.exceptions import Conflict

from .models import DeviceToken, Kind, Notification, PushStatus
from .push import PushMessage, get_sender

SOUTH_AFRICA = ZoneInfo("Africa/Johannesburg")

# Sent after an answer is saved, inside its transaction: sender=Notification,
# notification=..., previous="" or the earlier answer.
notification_answered = Signal()


# Content (PRD Notifications table). Times in South African time: "Tue 27 Oct", "19:40".


def match_day(kick_off) -> str:
    local = kick_off.astimezone(SOUTH_AFRICA)
    return f"{local:%a} {local.day} {local:%b}"


def match_time(kick_off) -> str:
    return f"{kick_off.astimezone(SOUTH_AFRICA):%H:%M}"


def confirmation_content(fixture) -> tuple[str, str]:
    """Both team names, date and time."""
    title = f"{fixture.home_team.name} vs {fixture.away_team.name}"
    return title, f"{match_day(fixture.kick_off)}, {match_time(fixture.kick_off)}. Are you playing?"


def reminder_content(fixture) -> tuple[str, str]:
    """Date, time and field."""
    title = f"Match tonight: {fixture.home_team.name} vs {fixture.away_team.name}"
    body = f"{match_day(fixture.kick_off)}, {match_time(fixture.kick_off)}, {fixture.pitch.name}"
    return title, body


# Sending


def notify(
    kind: str,
    recipients: Iterable,
    *,
    club,
    title: str,
    body: str = "",
    fixture=None,
    answer_by=None,
) -> list[Notification]:
    """One Notification per recipient (each at most once), pushed after commit."""
    if kind not in Kind.values:
        raise ValueError(f"Unknown notification kind {kind!r}.")
    if fixture is not None and fixture.club_id != club.pk:
        raise ValueError("The Fixture belongs to another Club.")
    seen: set[int] = set()
    notifications = []
    for user in recipients:
        if user.pk in seen:
            continue
        seen.add(user.pk)
        notifications.append(
            Notification(
                club=club,
                recipient=user,
                kind=kind,
                title=title,
                body=body,
                fixture=fixture,
                answer_by=answer_by,
            )
        )
    created = Notification.objects.bulk_create(notifications)
    ids = [n.pk for n in created]
    if ids:
        transaction.on_commit(lambda: push(ids))
    return created


def push_data(notification: Notification) -> dict[str, str]:
    """What the app needs to open the right screen. FCM data values must be strings."""
    data = {"notification_id": str(notification.pk), "kind": notification.kind}
    if notification.fixture_id:
        data["fixture_id"] = str(notification.fixture_id)
    return data


def push(notification_ids: list[int]) -> None:
    """Pushes these Notifications to every device of their recipients and records the result.

    A token Firebase reports as dead is deleted. A failed push leaves the Notification in
    the inbox with status "failed" (delivery fallback: docs/OPEN_QUESTIONS.md "Chunk 9").
    """
    notifications = list(
        Notification.objects.filter(pk__in=notification_ids, push_status=PushStatus.PENDING)
    )
    if not notifications:
        return
    tokens: dict[int, list[str]] = {}
    for device in DeviceToken.objects.filter(
        user_id__in={n.recipient_id for n in notifications}
    ).order_by("pk"):
        tokens.setdefault(device.user_id, []).append(device.token)

    messages, owners = [], []
    for notification in notifications:
        for token in tokens.get(notification.recipient_id, []):
            messages.append(
                PushMessage(token, notification.title, notification.body, push_data(notification))
            )
            owners.append(notification)
    results = get_sender().send(messages) if messages else []

    outcome: dict[int, list] = {n.pk: [] for n in notifications}
    for owner, result in zip(owners, results, strict=True):
        outcome[owner.pk].append(result)
    dead = [r.token for r in results if r.token_invalid]
    if dead:
        DeviceToken.objects.filter(token__in=dead).delete()

    now = timezone.now()
    for notification in notifications:
        sent = outcome[notification.pk]
        if not sent:
            notification.push_status = PushStatus.NO_DEVICE
        elif any(r.ok for r in sent):
            notification.push_status = PushStatus.SENT
            notification.pushed_at = now
        else:
            notification.push_status = PushStatus.FAILED
            notification.push_error = "; ".join(sorted({r.error for r in sent}))[:300]
    Notification.objects.bulk_update(notifications, ["push_status", "pushed_at", "push_error"])


# The inbox


def mark_read(notification: Notification) -> Notification:
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    return notification


@transaction.atomic
def answer(notification: Notification, value: str) -> Notification:
    """Records the recipient's answer. They may change it while it is still answerable."""
    notification = Notification.objects.select_for_update().get(pk=notification.pk)
    if not notification.answers:
        raise Conflict("This notification has nothing to answer.")
    if value not in notification.answers:
        raise Conflict(f"Answer with one of: {', '.join(notification.answers)}.")
    now = timezone.now()
    if not notification.is_answerable(now):
        raise Conflict("This can no longer be answered.")
    previous = notification.answer
    if previous == value:
        return notification
    notification.answer = value
    notification.answered_at = now
    notification.read_at = notification.read_at or now
    notification.save(update_fields=["answer", "answered_at", "read_at"])
    notification_answered.send(sender=Notification, notification=notification, previous=previous)
    return notification


def close(notifications) -> int:
    """Stops these Notifications being answered (a request filled, a match was cancelled)."""
    return notifications.filter(closed_at__isnull=True).update(closed_at=timezone.now())
