"""Teams, their Players and requests to join (PRD: Captain and Admin rows of the roles table).

- A Captain requests a Team for a Season and a Division; the Club's Admin confirms or
  declines it. Captain is not a stored role: a Player is Captain of the Team they captain.
- A Player asks to join an active Team; its Captain accepts or declines.
- Membership keeps its history: leaving closes a membership, and rejoining opens a new one.
- A Player is in at most one Team per Division and Season (docs/DECISIONS.md).
"""

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from clubs.models import Club, Division, Season


class Team(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Waiting for the Admin"
        ACTIVE = "active", "Active"
        DECLINED = "declined", "Declined"

    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="teams")
    season = models.ForeignKey(Season, on_delete=models.PROTECT, related_name="teams")
    division = models.ForeignKey(Division, on_delete=models.PROTECT, related_name="teams")
    name = models.CharField(max_length=60)
    captain = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="captained_teams",
    )
    status = models.CharField(max_length=10, choices=Status.choices)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decline_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "season",
                "division",
                condition=~models.Q(status="declined"),
                name="one_team_name_per_division_and_season",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.division}, {self.season.name})"

    def current_memberships(self) -> models.QuerySet:
        return self.memberships.filter(left_at__isnull=True)


TEAM_STATUSES = Team.Status  # One name for each status enum in the OpenAPI schema.


class TeamMembership(models.Model):
    """A Player's time in a Team. An open one (no `left_at`) means they are in it now."""

    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="memberships")
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="team_memberships"
    )
    joined_at = models.DateTimeField()
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "player"],
                condition=models.Q(left_at__isnull=True),
                name="one_open_membership_per_team",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.player} in {self.team}"

    def get_club_id(self) -> int:
        return self.team.club_id


class JoinRequest(models.Model):
    """A Player asking to join a Team. Its Captain accepts or declines."""

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for the Captain"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        WITHDRAWN = "withdrawn", "Withdrawn"

    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="join_requests")
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="join_requests"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "player"],
                condition=models.Q(status="pending"),
                name="one_pending_join_request_per_team",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.player} asks to join {self.team}"


JOIN_REQUEST_STATUSES = JoinRequest.Status
