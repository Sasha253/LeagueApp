"""One Fixture the Admin adds in the app, checked as a row of the league import's Fixtures
sheet (fixtures/imports.py), so both follow the same rules: inside its Season, a kick-off
still to come, its pitch and both Teams free then (docs/DECISIONS.md).

Unlike the import, it adds no Teams (both are picked from the Division's active Teams) and
never touches a Fixture the club already has.
"""

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from clubs.models import Club, Division, Field, Season
from core.tables import ImportAction as Action
from core.tables import Row
from teams.models import Team

from . import imports, lifecycle
from .models import Fixture, FixtureTransition

ALREADY_EXISTS = "The club already has this Fixture."
NOT_IN_DIVISION = "Pick a Team of this Division this Season."
NOT_ACTIVE = "This Team isn't active."
SAME_TEAM = "Home and Away are the same Team."
AMBIGUOUS = "Another record has a name too close to this one. Rename one of them first."
WEEKDAYS = ["Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays"]


@dataclass
class NewFixture:
    season: Season
    division: Division
    pitch: Field
    home_team: Team
    away_team: Team
    kick_off: object  # An aware datetime.
    friendly_eligible: bool = False


def _check(new: NewFixture) -> None:
    errors = {}
    weekday = new.division.night.weekday
    if timezone.localtime(new.kick_off).weekday() != weekday:
        errors["kick_off"] = [f"{new.division.name} plays on {WEEKDAYS[weekday]}."]
    for side in ("home_team", "away_team"):
        team = getattr(new, side)
        if team.season_id != new.season.pk or team.division_id != new.division.pk:
            errors[side] = [NOT_IN_DIVISION]
        elif team.status != Team.Status.ACTIVE:
            errors[side] = [NOT_ACTIVE]
    if not errors and new.home_team.pk == new.away_team.pk:
        errors["away_team"] = [SAME_TEAM]
    if errors:
        raise ValidationError(errors)


def _as_row(new: NewFixture) -> Row:
    local = timezone.localtime(new.kick_off)
    return Row(
        number=1,
        cells={
            "season": new.season.name,
            "date": local.date().isoformat(),
            "time": local.strftime("%H:%M"),
            "division": new.division.name,
            "pitch": new.pitch.name,
            "home": new.home_team.name,
            "away": new.away_team.name,
            "friendly_eligible": "yes" if new.friendly_eligible else "no",
        },
    )


@transaction.atomic
def add_fixture(club: Club, new: NewFixture, admin) -> Fixture:
    _check(new)
    planned = imports.plan(club, [_as_row(new)]).rows[0]
    if planned.errors:
        raise ValidationError({"non_field_errors": planned.errors})
    if planned.action != Action.CREATE:
        raise ValidationError({"non_field_errors": [ALREADY_EXISTS]})
    # The plan finds records by name: make sure it found the ones the Admin picked.
    picked = [
        (planned.season_obj, new.season),
        (planned.division_obj, new.division),
        (planned.pitch_obj, new.pitch),
        (planned.home_obj, new.home_team),
        (planned.away_obj, new.away_team),
    ]
    if any(found is None or found.pk != chosen.pk for found, chosen in picked):
        raise ValidationError({"non_field_errors": [AMBIGUOUS]})
    now = timezone.now()
    fixture = Fixture.objects.create(
        club=club,
        season=new.season,
        division=new.division,
        pitch=new.pitch,
        kick_off=planned.kick_off,
        home_team=new.home_team,
        away_team=new.away_team,
        friendly_eligible=new.friendly_eligible,
        friendly_eligible_changed_by=admin if new.friendly_eligible else None,
        friendly_eligible_changed_at=now if new.friendly_eligible else None,
        status=Fixture.Status.SCHEDULED,
    )
    lifecycle.log_creation(fixture, cause=FixtureTransition.Cause.ADMIN, actor=admin)
    return fixture
