"""User accounts and roles (PRD: "User roles and permissions").

- One account per person, app-wide: a Player can play at any club (docs/DECISIONS.md).
- Player and Booking User are held app-wide. A Player has a PlayerProfile.
- Admin and Referee are held per Club, as a ClubRole, never app-wide.
- Captain is not stored here: a Player is a Captain of the Team they captain (chunk 5).
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

from clubs.models import Club, Night


class UserManager(BaseUserManager["User"]):
    def create_user(self, email: str, password: str | None = None, **fields) -> "User":
        if not email:
            raise ValueError("Users must have an email address.")
        user = self.model(email=normalize_email(email), **fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **fields) -> "User":
        fields.setdefault("is_staff", True)
        fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **fields)

    def get_by_natural_key(self, username: str | None) -> "User":
        # Log in with the email in any case.
        return self.get(email__iexact=username)


def normalize_email(email: str) -> str:
    return email.strip().lower()


class User(AbstractBaseUser, PermissionsMixin):
    # Saved lowercased, so unique also means unique in any case.
    email = models.EmailField(max_length=254, unique=True)
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, blank=True)
    is_booking_user = models.BooleanField(
        default=False, help_text="Hires fields (Book and My bookings tabs)."
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, help_text="Can log in to the Django admin.")
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    def __str__(self) -> str:
        return self.email

    def save(self, *args, **kwargs) -> None:
        self.email = normalize_email(self.email)
        super().save(*args, **kwargs)

    @property
    def is_player(self) -> bool:
        return hasattr(self, "player_profile")

    def club_ids_with_role(self, *roles: str) -> models.QuerySet:
        """The ids of the Clubs where this user holds any of these roles."""
        return self.club_roles.filter(role__in=roles).values("club_id")


class PlayerProfile(models.Model):
    """What makes a user a Player: their position and the Nights they opted into."""

    class Position(models.TextChoices):
        OUTFIELD = "outfield", "Outfield"
        GOALKEEPER = "goalkeeper", "Goalkeeper"
        BOTH = "both", "Outfield and goalkeeper"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="player_profile")
    position = models.CharField(max_length=10, choices=Position.choices)
    nights = models.ManyToManyField(
        Night,
        blank=True,
        related_name="opted_in_players",
        help_text="The Nights this Player gets notifications for (FR-8).",
    )

    def __str__(self) -> str:
        return f"{self.user} ({self.get_position_display()})"

    @property
    def plays_outfield(self) -> bool:
        return self.position in (self.Position.OUTFIELD, self.Position.BOTH)

    @property
    def plays_goalkeeper(self) -> bool:
        return self.position in (self.Position.GOALKEEPER, self.Position.BOTH)


class ClubRole(models.Model):
    """A role a user holds at one Club. Admins and Referees see only that Club's data."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        REFEREE = "referee", "Referee"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="club_roles")
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="roles")
    role = models.CharField(max_length=10, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "club", "role"], name="one_role_per_club"),
        ]
        ordering = ["club__name", "role"]

    def __str__(self) -> str:
        return f"{self.user}: {self.get_role_display()} at {self.club}"
