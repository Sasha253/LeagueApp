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


TRANSITION_CAUSES = FixtureTransition.Cause


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


class ReplacementOffer(models.Model):
    """The search for a new opponent once one Team of a Fixture is out (FR-13 to FR-16).

    The slot is offered to the Captains of eligible Teams (ReplacementCandidate) until
    `closes_at`; the first to accept takes the out Team's place in the Fixture (FR-15). If
    none does in time it lapses and chunk 15 decides between a friendly and a cancellation
    (FR-17). A Fixture has at most one open offer. Only fixtures/replacements.py writes
    these; they are never deleted.
    """

    class Status(models.TextChoices):
        OPEN = "open", "Offered"
        ACCEPTED = "accepted", "Accepted"
        LAPSED = "lapsed", "No Team accepted"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class Slot(models.TextChoices):
        HOME = "home", "Home"
        AWAY = "away", "Away"

    fixture = models.ForeignKey(Fixture, on_delete=models.PROTECT, related_name="replacements")
    kick_off = models.DateTimeField(help_text="The kick-off the slot was offered for.")
    out_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="+")
    remaining_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="+")
    slot = models.CharField(max_length=4, choices=Slot.choices, help_text="The out Team's.")
    opened_at = models.DateTimeField()
    closes_at = models.DateTimeField(help_text="No Team can accept after this.")
    status = models.CharField(max_length=10, choices=Status.choices)
    accepted_team = models.ForeignKey(
        Team, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="The Captain who accepted.",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(
        null=True, blank=True, help_text="When it was accepted, lapsed or withdrawn."
    )

    class Meta:
        ordering = ["opened_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["fixture"],
                condition=models.Q(status="open"),
                name="one_open_replacement_per_fixture",
            ),
            models.CheckConstraint(
                condition=~models.Q(status="accepted") | models.Q(accepted_team__isnull=False),
                name="accepted_replacement_has_team",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.fixture}: replacing {self.out_team} ({self.get_status_display()})"

    def get_club_id(self) -> int:
        return self.fixture.club_id

    def delete(self, *args, **kwargs):
        raise ValueError("A ReplacementOffer is never deleted.")


class ReplacementCandidate(models.Model):
    """A Team the slot was offered to, and its Captain's offer (a Confirmation Notification).

    The Captain's "Confirm" on that Notification accepts for the Team (FR-15).
    """

    offer = models.ForeignKey(ReplacementOffer, on_delete=models.PROTECT, related_name="candidates")
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="+")
    notification = models.OneToOneField(
        "notifications.Notification",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="replacement_candidate",
    )

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(fields=["offer", "team"], name="one_candidate_per_offer_team"),
        ]

    def __str__(self) -> str:
        return f"{self.team} for {self.offer}"

    def delete(self, *args, **kwargs):
        raise ValueError("A ReplacementCandidate is never deleted.")


REPLACEMENT_STATUSES = ReplacementOffer.Status
REPLACEMENT_SLOTS = ReplacementOffer.Slot


class FixtureFallback(models.Model):
    """What became of a match that couldn't go ahead as a league match (FR-10 to FR-12,
    FR-17, FR-43).

    Both Teams were out at T-6h, or one was and no Team took its slot. A friendly-eligible
    match whose kick-off is still to come becomes a friendly open to other Players
    (FriendlyInvite); any other is cancelled and every payment for it becomes credit to
    whoever paid. One per Fixture. Only fixtures/fallbacks.py writes these; they are never
    changed or deleted.
    """

    class Cause(models.TextChoices):
        BOTH_TEAMS_OUT = "both_teams_out", "Both Teams out"
        NO_REPLACEMENT = "no_replacement", "No replacement found"

    class Outcome(models.TextChoices):
        FRIENDLY = "friendly", "Friendly"
        CANCELLED = "cancelled", "Cancelled"

    fixture = models.OneToOneField(Fixture, on_delete=models.PROTECT, related_name="fallback")
    kick_off = models.DateTimeField(help_text="The kick-off it was decided for.")
    cause = models.CharField(max_length=16, choices=Cause.choices)
    remaining_team = models.ForeignKey(
        Team,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="The Team that was still in; empty when both were out.",
    )
    outcome = models.CharField(max_length=10, choices=Outcome.choices)
    decided_at = models.DateTimeField()

    class Meta:
        ordering = ["decided_at", "pk"]

    def __str__(self) -> str:
        return f"{self.fixture}: {self.get_outcome_display()} ({self.get_cause_display()})"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("A FixtureFallback is never changed.")
        super().save(*args, **kwargs)

    def get_club_id(self) -> int:
        return self.fixture.club_id

    def delete(self, *args, **kwargs):
        raise ValueError("A FixtureFallback is never deleted.")


class FriendlyInvite(models.Model):
    """A Player invited to join a friendly, and their invite (a Confirmation Notification).

    "Confirm" on that Notification joins the friendly, "Decline" doesn't; the Player can
    change it until kick-off (FR-11, FR-17). The answer lives on the Notification.
    """

    fallback = models.ForeignKey(FixtureFallback, on_delete=models.PROTECT, related_name="invites")
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friendly_invites"
    )
    notification = models.OneToOneField(
        "notifications.Notification", on_delete=models.CASCADE, related_name="friendly_invite"
    )

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["fallback", "player"], name="one_friendly_invite_per_player"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.player} for {self.fallback}"

    def delete(self, *args, **kwargs):
        raise ValueError("A FriendlyInvite is never deleted.")


FALLBACK_CAUSES = FixtureFallback.Cause
FALLBACK_OUTCOMES = FixtureFallback.Outcome


class CaptainRequest(models.Model):
    """A Captain asks the Admin to cancel or postpone a match for their Team (FR-18).

    Nothing changes until an Admin accepts it. Accepting a cancellation takes the Team out
    of the match and the replacement search starts (FR-13 to FR-17); accepting a
    postponement is an Admin reschedule to the kick-off the Admin picks (FR-7 to FR-9). One
    pending request per Fixture and Team. Only fixtures/reschedules.py writes these; they
    are never deleted.
    """

    class Kind(models.TextChoices):
        CANCEL = "cancel", "Cancel"
        POSTPONE = "postpone", "Postpone"

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for the Admin"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        WITHDRAWN = "withdrawn", "Withdrawn"
        CLOSED = "closed", "No longer applies"

    fixture = models.ForeignKey(Fixture, on_delete=models.PROTECT, related_name="captain_requests")
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    reason = models.CharField(max_length=300)
    kick_off = models.DateTimeField(help_text="The kick-off the request was made for.")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    requested_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="The Admin who accepted or declined it.",
    )
    decided_at = models.DateTimeField(
        null=True, blank=True, help_text="When it was accepted, declined, withdrawn or closed."
    )
    note = models.CharField(max_length=300, blank=True, help_text="The Admin's note, or why.")

    class Meta:
        ordering = ["requested_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["fixture", "team"],
                condition=models.Q(status="pending"),
                name="one_pending_captain_request_per_team",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.team}: {self.get_kind_display()} {self.fixture} ({self.get_status_display()})"
        )

    def get_club_id(self) -> int:
        return self.fixture.club_id

    def delete(self, *args, **kwargs):
        raise ValueError("A CaptainRequest is never deleted.")


CAPTAIN_REQUEST_KINDS = CaptainRequest.Kind
CAPTAIN_REQUEST_STATUSES = CaptainRequest.Status


class FixtureReschedule(models.Model):
    """An Admin moved a Fixture to a new kick-off or pitch (FR-7 to FR-9). Never changed.

    The lifecycle restarts at the new kick-off: Confirmations, answers, the T-6h check and
    Reminders are per kick-off. See fixtures/reschedules.py.
    """

    fixture = models.ForeignKey(Fixture, on_delete=models.PROTECT, related_name="reschedules")
    from_kick_off = models.DateTimeField()
    to_kick_off = models.DateTimeField()
    from_pitch = models.ForeignKey(Field, on_delete=models.PROTECT, related_name="+")
    to_pitch = models.ForeignKey(Field, on_delete=models.PROTECT, related_name="+")
    at = models.DateTimeField()
    by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    note = models.CharField(max_length=300, blank=True)
    request = models.OneToOneField(
        CaptainRequest,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reschedule",
        help_text="The Captain's postponement request it answered, if any.",
    )
    confirmations_sent = models.BooleanField(
        help_text="The new kick-off was within the Confirmation window, so they went out (FR-9)."
    )
    notified = models.PositiveIntegerField(help_text="How many were sent the Update.")

    class Meta:
        ordering = ["at", "pk"]

    def __str__(self) -> str:
        return f"{self.fixture}: moved from {self.from_kick_off:%Y-%m-%d %H:%M}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("A FixtureReschedule is never changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("A FixtureReschedule is never deleted.")


class PlayerRequest(models.Model):
    """A Captain short of Players asks other Players to join their Team for one match
    (FR-35 to FR-37): a Player Request (outfield) or a Goalkeeper Request.

    It goes to the Players opted into the match's Night who are in neither Team and play
    that position (notifications/targeting.py). The first `places` Players to accept join
    (BorrowedPlayer); then it is filled and stops taking answers. One open request per
    Fixture, Team and kind. Only fixtures/borrowing.py writes these; never deleted.
    """

    class Kind(models.TextChoices):
        PLAYER = "player", "Player"
        GOALKEEPER = "goalkeeper", "Goalkeeper"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        FILLED = "filled", "Filled"
        WITHDRAWN = "withdrawn", "Withdrawn"
        CLOSED = "closed", "No longer applies"

    fixture = models.ForeignKey(Fixture, on_delete=models.PROTECT, related_name="player_requests")
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    places = models.PositiveSmallIntegerField(help_text="How many Players are wanted.")
    kick_off = models.DateTimeField(help_text="The kick-off the request was made for.")
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    raised_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices)
    ended_at = models.DateTimeField(
        null=True, blank=True, help_text="When it filled, was withdrawn or stopped applying."
    )
    note = models.CharField(max_length=300, blank=True, help_text="Why it closed.")
    notified = models.PositiveIntegerField(help_text="How many Players were asked.")

    class Meta:
        ordering = ["raised_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["fixture", "team", "kind"],
                condition=models.Q(status="open"),
                name="one_open_player_request_per_team_and_kind",
            ),
            models.CheckConstraint(condition=models.Q(places__gte=1), name="player_request_places"),
        ]

    def __str__(self) -> str:
        return f"{self.team}: {self.places} {self.get_kind_display()} for {self.fixture}"

    def get_club_id(self) -> int:
        return self.fixture.club_id

    def delete(self, *args, **kwargs):
        raise ValueError("A PlayerRequest is never deleted.")


PLAYER_REQUEST_KINDS = PlayerRequest.Kind
PLAYER_REQUEST_STATUSES = PlayerRequest.Status


class PlayerRequestInvite(models.Model):
    """A Player a PlayerRequest was sent to, and their Notification (Accept / Decline)."""

    request = models.ForeignKey(PlayerRequest, on_delete=models.PROTECT, related_name="invites")
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="player_request_invites"
    )
    notification = models.OneToOneField(
        "notifications.Notification", on_delete=models.CASCADE, related_name="player_request_invite"
    )

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["request", "player"], name="one_invite_per_request_player"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.player} for {self.request}"

    def delete(self, *args, **kwargs):
        raise ValueError("A PlayerRequestInvite is never deleted.")


class BorrowedPlayer(models.Model):
    """A Player from outside both Teams who accepted a PlayerRequest and plays for its Team
    in that match (FR-37). They count as confirmed for the Team at that kick-off (FR-5,
    FR-38). One place per Player, match and kick-off. Never changed or deleted.
    """

    request = models.ForeignKey(PlayerRequest, on_delete=models.PROTECT, related_name="joined")
    fixture = models.ForeignKey(Fixture, on_delete=models.PROTECT, related_name="borrowed_players")
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="+")
    kick_off = models.DateTimeField(help_text="The kick-off they joined for.")
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="borrowed_places"
    )
    joined_at = models.DateTimeField()

    class Meta:
        ordering = ["joined_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["fixture", "kick_off", "player"], name="one_borrowed_place_per_match"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.player} for {self.team} in {self.fixture}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("A BorrowedPlayer is never changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("A BorrowedPlayer is never deleted.")


class FriendlyFee(models.Model):
    """What a friendly costs, who pays it and its Captain (FR-24), set by an Admin.

    One per friendly (a FixtureFallback with outcome friendly). The fee is the friendly's
    total; Players in the payer group contribute towards it, recorded in the ledger as
    `friendly` payments for the Fixture (ledger/services.py `record_friendly_payment`).
    The club/manager paying, or a fee of R 0, means nothing is collected from Players.
    The fee and payer are fixed once a payment stands; the Captain can change until
    kick-off. The friendly's Payment Barcode is issued to the Captain (barcodes app).
    Only fixtures/friendlies.py writes these; they are never deleted.
    """

    class Payer(models.TextChoices):
        BORROWED_PLAYERS = "borrowed_players", "The borrowed Players"
        TEAM_PLAYERS = "team_players", "The Team's Players"
        CLUB = "club", "The club/manager"

    fallback = models.OneToOneField(
        FixtureFallback, on_delete=models.PROTECT, related_name="friendly_fee"
    )
    fixture = models.OneToOneField(Fixture, on_delete=models.PROTECT, related_name="friendly_fee")
    fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="The friendly's fee in rand, for the whole match.",
    )
    payer = models.CharField(max_length=16, choices=Payer.choices)
    captain = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="friendlies_captained",
        help_text="The Player who receives the friendly's Barcode and has it verified.",
    )
    set_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    set_at = models.DateTimeField()

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fee__gte=0), name="friendly_fee_not_negative"
            ),
        ]

    def __str__(self) -> str:
        return f"Friendly fee R {self.fee} for {self.fixture} ({self.get_payer_display()})"

    @property
    def collects(self) -> bool:
        """Whether Players pay anything towards it."""
        return self.payer != self.Payer.CLUB and self.fee > 0

    def delete(self, *args, **kwargs):
        raise ValueError("A FriendlyFee is never deleted.")


FRIENDLY_PAYERS = FriendlyFee.Payer
