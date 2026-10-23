"""Notifications (PRD "Notifications"): what each user is told, and their answers.

- One Notification per recipient, of one of the seven PRD kinds. It belongs to one Club.
- Its action buttons come from its kind (ACTIONS), not from the record.
- Answering is allowed until `answer_by` and while the Notification is open; the recipient
  can change an answer in that time (PRD targeting rules, FR-3).
- Every Notification stays in the recipient's inbox, whether or not the push arrived. The
  push result is recorded on it (NFR Timeliness).

Who receives a Notification is decided in targeting.py, never here.
"""

from django.conf import settings
from django.db import models

from clubs.models import Club


class Kind(models.TextChoices):
    CONFIRMATION = "confirmation", "Confirmation"
    REMINDER = "reminder", "Reminder"
    GENERAL = "general", "General"
    UPDATE = "update", "Update"
    PLAYER_REQUEST = "player_request", "Player Request"
    GOALKEEPER_REQUEST = "goalkeeper_request", "Goalkeeper Request"
    BOOKING = "booking", "Booking"


class Answer(models.TextChoices):
    CONFIRM = "confirm", "Confirm"
    DECLINE = "decline", "Decline"
    ACCEPT = "accept", "Accept"


class PushStatus(models.TextChoices):
    PENDING = "pending", "Not sent yet"
    SENT = "sent", "Sent to at least one device"
    FAILED = "failed", "Every device failed"
    NO_DEVICE = "no_device", "No device registered"


# The buttons each kind carries (PRD Notifications table). An `answer` button records an
# answer; an `open` button only opens a screen in the app.
FIND_MATCH = "find_match"
ACTIONS: dict[str, list[tuple[str, str, str]]] = {
    Kind.CONFIRMATION: [
        (Answer.CONFIRM, "Confirm", "answer"),
        (Answer.DECLINE, "Decline", "answer"),
    ],
    Kind.REMINDER: [],
    Kind.GENERAL: [(FIND_MATCH, "Find a match", "open")],
    Kind.UPDATE: [],
    Kind.PLAYER_REQUEST: [
        (Answer.ACCEPT, "Accept", "answer"),
        (Answer.DECLINE, "Decline", "answer"),
    ],
    Kind.GOALKEEPER_REQUEST: [
        (Answer.ACCEPT, "Accept", "answer"),
        (Answer.DECLINE, "Decline", "answer"),
    ],
    Kind.BOOKING: [(Answer.CONFIRM, "Confirm", "answer"), (Answer.DECLINE, "Decline", "answer")],
}


def answers_for(kind: str) -> list[str]:
    return [key for key, _, action in ACTIONS[kind] if action == "answer"]


class Notification(models.Model):
    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="notifications")
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    title = models.CharField(max_length=120)
    body = models.CharField(max_length=500, blank=True)
    fixture = models.ForeignKey(
        "fixtures.Fixture",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="notifications",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    answer = models.CharField(max_length=10, choices=Answer.choices, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    answer_by = models.DateTimeField(
        null=True, blank=True, help_text="No answer is taken after this (e.g. T-6h, FR-3)."
    )
    closed_at = models.DateTimeField(
        null=True, blank=True, help_text="No longer answerable: the request filled, etc."
    )
    push_status = models.CharField(
        max_length=10, choices=PushStatus.choices, default=PushStatus.PENDING
    )
    pushed_at = models.DateTimeField(null=True, blank=True)
    resent_at = models.DateTimeField(
        null=True, blank=True, help_text="Pushed again to someone who hadn't answered (FR-2)."
    )
    push_error = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["recipient", "-created_at"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(answer="") | models.Q(answered_at__isnull=False),
                name="notification_answer_has_time",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} to {self.recipient}: {self.title}"

    @property
    def answers(self) -> list[str]:
        return answers_for(self.kind)

    def is_answerable(self, now) -> bool:
        return bool(
            self.answers
            and self.closed_at is None
            and (self.answer_by is None or now < self.answer_by)
        )


NOTIFICATION_KINDS = Kind  # One name for each enum in the OpenAPI schema.
NOTIFICATION_ANSWERS = Answer
NOTIFICATION_ACTIONS = [("answer", "Answer"), ("open", "Open")]  # The kinds of button.


class DeviceToken(models.Model):
    """A phone's Firebase Cloud Messaging token. One token belongs to one user at a time."""

    class Platform(models.TextChoices):
        IOS = "ios", "iOS"
        ANDROID = "android", "Android"
        WEB = "web", "Web"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="device_tokens"
    )
    token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(max_length=10, choices=Platform.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField()

    class Meta:
        ordering = ["-last_seen_at"]

    def __str__(self) -> str:
        return f"{self.user}: {self.get_platform_display()}"


DEVICE_PLATFORMS = DeviceToken.Platform
