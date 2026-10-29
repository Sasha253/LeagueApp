"""Test accounts: one user per role at a Club, that only a superuser can sign in as.

They let us, who run the app, see each screen as an Admin, a Referee, a Player, a
Goalkeeper or a Booking User sees it, at a real Club, without knowing anyone's password.
They have no usable password, so the login form refuses them; a superuser signs in as one
with `POST /api/v1/auth/test-users/{id}/login/` (docs/DECISIONS.md).

Captain isn't one of them: a Captain captains a Team, and a test Team would play in the
Club's league. The test Player can request a Team, which then waits for the Admin.
"""

from dataclasses import dataclass

from django.db import transaction

from clubs.models import Club

from .models import ClubRole, PlayerProfile, User

# Never delivered: the .invalid top-level domain is reserved (RFC 2606).
EMAIL_DOMAIN = "test.invalid"


@dataclass(frozen=True)
class TesterRole:
    key: str
    label: str
    club_role: str | None = None
    position: str | None = None
    booking: bool = False


ROLES = [
    TesterRole("admin", "Admin", club_role=ClubRole.Role.ADMIN),
    TesterRole("referee", "Referee", club_role=ClubRole.Role.REFEREE),
    TesterRole("player", "Player", position=PlayerProfile.Position.OUTFIELD),
    TesterRole("keeper", "Goalkeeper", position=PlayerProfile.Position.GOALKEEPER),
    TesterRole("booker", "Booking User", booking=True),
]


def email_for(club: Club, role: TesterRole) -> str:
    return f"{role.key}.club{club.pk}@{EMAIL_DOMAIN}"


@transaction.atomic
def make_test_users(club: Club) -> list[User]:
    """Adds the Club's test users, or brings them up to date. Players opt into its Nights."""
    users = []
    for role in ROLES:
        user, created = User.objects.get_or_create(
            email=email_for(club, role),
            defaults={"name": f"Test {role.label} ({club.name})", "is_test_account": True},
        )
        if created:
            user.set_unusable_password()
        user.is_test_account = True
        user.is_booking_user = role.booking
        user.save()
        if role.club_role:
            ClubRole.objects.get_or_create(user=user, club=club, role=role.club_role)
        if role.position:
            profile, _ = PlayerProfile.objects.update_or_create(
                user=user, defaults={"position": role.position}
            )
            profile.nights.add(*club.nights.all())
        users.append(user)
    return users


def roles_of(user: User) -> list[str]:
    """What the test user is, in words, for the superuser's list."""
    roles = [f"{role.get_role_display()} at {role.club.name}" for role in user.club_roles.all()]
    if user.is_player:
        roles.append(f"Player ({user.player_profile.get_position_display().lower()})")
    if user.is_booking_user:
        roles.append("Booking User")
    return roles
