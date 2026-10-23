"""DRF permission classes per role, reused by every feature.

Admin and Referee are held per Club, so their checks need the Club in question:

- On a club-level URL, the view names it with a `club_id` URL kwarg, or with
  `get_permission_club_id()` when the Club comes from elsewhere.
- On a single record, the object names it with a `club_id` attribute (every Club-owned
  model has one), or with `get_club_id()` when the Club is further away.

A view with no Club in its URL only lets in users who hold the role at some Club, and its
queryset must then be limited with ClubScopedQuerysetMixin, so a list never shows another
Club's records.

Captain is not a stored role: IsTeamCaptain checks the Team's `captain` on the record, a
Team or anything with a `team`.
"""

from rest_framework.permissions import BasePermission

from .models import ClubRole


def _club_id_of_view(view) -> int | None:
    if hasattr(view, "get_permission_club_id"):
        return view.get_permission_club_id()
    club_id = getattr(view, "kwargs", {}).get("club_id")
    return int(club_id) if club_id is not None else None


def _club_id_of_object(obj) -> int:
    if hasattr(obj, "get_club_id"):
        return obj.get_club_id()
    return obj.club_id


class ClubRolePermission(BasePermission):
    """Lets in users who hold `roles` at the Club of the URL or of the record."""

    roles: tuple[str, ...] = ()

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        club_ids = user.club_roles.filter(role__in=self.roles)
        club_id = _club_id_of_view(view)
        if club_id is not None:
            club_ids = club_ids.filter(club_id=club_id)
        return club_ids.exists()

    def has_object_permission(self, request, view, obj) -> bool:
        return request.user.club_roles.filter(
            role__in=self.roles, club_id=_club_id_of_object(obj)
        ).exists()


class IsClubAdmin(ClubRolePermission):
    roles = (ClubRole.Role.ADMIN,)


class IsClubReferee(ClubRolePermission):
    roles = (ClubRole.Role.REFEREE,)


class IsClubAdminOrReferee(ClubRolePermission):
    """For what both may do, such as scanning a Payment Barcode at the gate."""

    roles = (ClubRole.Role.ADMIN, ClubRole.Role.REFEREE)


class IsPlayer(BasePermission):
    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_player)


class IsBookingUser(BasePermission):
    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_booking_user)


class IsTeamCaptain(IsPlayer):
    """Lets in the Captain of the Team the record is, or belongs to."""

    def has_object_permission(self, request, view, obj) -> bool:
        team = getattr(obj, "team", obj)
        return team.captain_id == request.user.pk


class ClubScopedQuerysetMixin:
    """Limits a view's queryset to the Clubs where the user holds `club_roles`.

    `club_field` is the lookup from the model to its Club, e.g. "club" or "team__club".
    """

    club_roles: tuple[str, ...] = (ClubRole.Role.ADMIN,)
    club_field = "club"

    def get_queryset(self):
        queryset = super().get_queryset()
        club_ids = self.request.user.club_ids_with_role(*self.club_roles)
        return queryset.filter(**{f"{self.club_field}__in": club_ids})
