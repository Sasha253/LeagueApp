"""Fixtures: one league match between two Teams of a Division, on a pitch, at a kick-off.

A Fixture's status follows the match lifecycle (PRD "Match lifecycle"). Only the moves in
lifecycle.TRANSITIONS are allowed, lifecycle.transition() is the only thing that makes them,
and every move is logged in FixtureTransition with who or what caused it. That log is
append-only: a FixtureTransition is never changed or deleted.

Kick-off is stored in UTC and shown in South African time (CLAUDE.md).
"""

from decimal import Decimal

from django.conf import settings
from django.db import models

from clubs.models import Club, Division, Field, Season
from teams.models import Team


class Fixture(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        CONFIRMING = "confirming", "Confirming"
        READY = "ready", "Ready"
        ONE_TEAM_OUT = "one_team_out", "One team out"
        BOTH_TEAMS_OUT = "both_teams_out", "Both teams out"
        REPLACEMENT_OFFERED = "replacement_offered", "Replacement offered"
        FRIENDLY = "friendly", "Friendly"
        CANCELLED = "cancelled", "Cancelled"
        PLAYED = "played", "Played"

    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="fixtures")
    season = models.ForeignKey(Season, on_delete=models.PROTECT, related_name="fixtures")
    division = models.ForeignKey(Division, on_delete=models.PROTECT, related_name="fixtures")
    pitch = models.ForeignKey(Field, on_delete=models.PROTECT, related_name="fixtures")
    kick_off = models.DateTimeField()
    home_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="home_fixtures")
    away_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="away_fixtures")
    friendly_eligible = models.BooleanField(
        default=False,
        help_text="If the match can't go ahead, it may become a friendly (FR-10, FR-17).",
    )
    friendly_eligible_changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    friendly_eligible_changed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kick_off", "pitch__name"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(home_team=models.F("away_team")),
                name="fixture_teams_differ",
            ),
            models.UniqueConstraint(
                fields=["pitch", "kick_off"],
                condition=~models.Q(status="cancelled"),
                name="one_fixture_per_pitch_and_kick_off",
            ),
        ]
        indexes = [models.Index(fields=["club", "kick_off"])]

    def __str__(self) -> str:
        return f"{self.home_team.name} vs {self.away_team.name}, {self.kick_off:%Y-%m-%d %H:%M}"

    @property
    def night(self):
        return self.division.night


FIXTURE_STATUSES = Fixture.Status  # One name for the status enum in the OpenAPI schema.


class FixtureTransition(models.Model):
    """One move of a Fixture's status, and who or what made it. Never changed or deleted."""

    class Cause(models.TextChoices):
        IMPORT = "import", "Fixture import"
        ADMIN = "admin", "Admin"
        CAPTAIN = "captain", "Captain"
        CHECKPOINT = "checkpoint", "Timed checkpoint"
        SYSTEM = "system", "League App"

    fixture = models.ForeignKey(Fixture, on_delete=models.PROTECT, related_name="transitions")
    from_status = models.CharField(
        max_length=20,
        choices=Fixture.Status.choices,
        blank=True,
        help_text="Empty for the Fixture's creation.",
    )
    to_status = models.CharField(max_length=20, choices=Fixture.Status.choices)
    at = models.DateTimeField()
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="The user who caused it; empty when the app did.",
    )
    cause = models.CharField(max_length=12, choices=Cause.choices)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["at", "pk"]

    def __str__(self) -> str:
        return f"{self.fixture}: {self.from_status or 'new'} to {self.to_status}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("A FixtureTransition is never changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("A FixtureTransition is never deleted.")


class FixtureCheckpoint(models.Model):
    """A timed checkpoint that has run for a Fixture (FR-1, FR-2, FR-4). Never changed.

    Unique per Fixture, kind and kick-off: each checkpoint runs exactly once for a kick-off,
    however often or late the timed job runs, and a reschedule to a new kick-off (FR-9)
    gets checkpoints of its own. See fixtures/checkpoints.py.
    """

    class Kind(models.TextChoices):
        CONFIRMATION = "confirmation", "Confirmations sent (T-36h)"
        RESEND = "resend", "Unanswered Confirmations resent"
        READINESS = "readiness", "Readiness checked (T-6h)"
        REMINDER = "reminder", "Reminders sent (T-6h)"

    fixture = models.ForeignKey(Fixture, on_delete=models.PROTECT, related_name="checkpoints")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    kick_off = models.DateTimeField(help_text="The kick-off this checkpoint ran for.")
    ran_at = models.DateTimeField()
    notified = models.PositiveIntegerField(help_text="How many people were notified.")

    class Meta:
        ordering = ["ran_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["fixture", "kind", "kick_off"], name="one_checkpoint_per_kick_off"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.fixture}: {self.get_kind_display()}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("A FixtureCheckpoint is never changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("A FixtureCheckpoint is never deleted.")


class ConfirmationAnswer(models.Model):
    """A Player's answer to a Fixture's Confirmation: playing or not (FR-3, FR-38).

    One per Fixture, Player and kick-off: the Player's current answer, changed in place
    until the cutoff (T-6h). A reschedule to a new kick-off starts with no answers. The
    T-6h readiness check counts the confirmed ones of each Team (FR-5). Only
    fixtures/confirmations.py writes them.
    """

    class Value(models.TextChoices):
        CONFIRM = "confirm", "Playing"
        DECLINE = "decline", "Not playing"

    class Via(models.TextChoices):
        NOTIFICATION = "notification", "Confirmation Notification"
        FIXTURE = "fixture", "Match screen"

    fixture = models.ForeignKey(
        Fixture, on_delete=models.PROTECT, related_name="confirmation_answers"
    )
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="+")
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="confirmation_answers"
    )
    kick_off = models.DateTimeField(help_text="The kick-off this answer is for.")
    answer = models.CharField(max_length=10, choices=Value.choices)
    answered_at = models.DateTimeField()
    via = models.CharField(max_length=12, choices=Via.choices)

    class Meta:
        ordering = ["answered_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["fixture", "player", "kick_off"], name="one_answer_per_player_and_kick_off"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.player} for {self.fixture}: {self.get_answer_display()}"


CONFIRMATION_ANSWERS = ConfirmationAnswer.Value


class TeamReadiness(models.Model):
    """What the T-6h readiness check decided for one Team of a Fixture (FR-5, FR-6).

    One per Fixture, Team and kick-off. A Team below its Division's minimum is out at once
    (FR-5). A Team that still owes money waits for the Admin, who rules it in or out (FR-6);
    so does every Team of a match whose Confirmations never went out. Nothing else rules a
    Team out. The counts are what the check saw then. Only fixtures/readiness.py writes
    these; an Admin's ruling is made once and never changed.
    """

    class Outcome(models.TextChoices):
        PENDING = "pending", "Waiting for the Admin"
        PLAYING = "playing", "Playing"
        OUT = "out", "Out"

    class Reason(models.TextChoices):
        NONE = "", "None"
        SHORT = "short", "Below the Division minimum"
        UNPAID = "unpaid", "Not paid"
        NO_REPLIES = "no_replies", "Confirmations didn't go out"

    fixture = models.ForeignKey(Fixture, on_delete=models.PROTECT, related_name="readiness")
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="+")
    kick_off = models.DateTimeField(help_text="The kick-off this check was for.")
    checked_at = models.DateTimeField()
    confirmed = models.PositiveIntegerField(help_text="Players confirmed at the check.")
    min_players = models.PositiveIntegerField(help_text="The Division minimum at the check.")
    outstanding = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="What the Team still owed at the check, in rand (below 0 when overpaid).",
    )
    outcome = models.CharField(max_length=10, choices=Outcome.choices)
    reason = models.CharField(
        max_length=12,
        choices=Reason.choices,
        blank=True,
        help_text="Why the Team is out or waits for the Admin.",
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="The Admin who ruled; empty when the check decided.",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["checked_at", "pk"]
        verbose_name_plural = "team readiness"
        constraints = [
            models.UniqueConstraint(
                fields=["fixture", "team", "kick_off"], name="one_readiness_per_team_and_kick_off"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.team} for {self.fixture}: {self.get_outcome_display()}"

    def get_club_id(self) -> int:
        """For the permission classes: the Club is the Fixture's."""
        return self.fixture.club_id

    def delete(self, *args, **kwargs):
        raise ValueError("A TeamReadiness is never deleted.")


READINESS_OUTCOMES = TeamReadiness.Outcome
READINESS_REASONS = TeamReadiness.Reason
