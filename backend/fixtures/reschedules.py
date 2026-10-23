"""Admin reschedules (FR-7 to FR-9) and Captain requests to cancel or postpone (FR-18).

An Admin reschedules a Fixture to a new kick-off, a new pitch, or both. `plan()` checks the
move and says what it will do, `reschedule()` makes it; the backend decides everything:

- Only a match still on its way to being played as a league match (scheduled, confirming
  or ready) and not yet kicked off. A match that is out, offered to a replacement, a
  friendly, cancelled or played has its own flow.
- A new kick-off must be after the T-6h cutoff counted from now (`readiness_hours_before`,
  the Club's own), so Players can still reply before the readiness check; inside the
  Season; and on the Division's Night. The pitch must be the Club's and free then, and
  neither Team may have another match that day.
- A new kick-off restarts the lifecycle: the match goes back to `scheduled`, its open
  Notifications stop taking answers, and answers, the T-6h check and Reminders start again
  for the new kick-off (they are all per kick-off). If the new kick-off is within the
  Confirmation window (`confirmation_hours_before`, T-36h), the Confirmations go out now
  through the T-36h checkpoint (FR-9); otherwise the checkpoint sends them as usual.
  Pending Captain requests for the old kick-off no longer apply and close.
- A new pitch at the same kick-off changes nothing else: the answers stand.
- Either way one Update goes to the Players of both Teams (FR-7) and only to the Night's
  Admins and the Referee of the affected pitch, the old one and the new one (FR-8).
  Players only for the Nights they opted into (targeting rules).

A Captain asks for a cancellation or postponement of their Team's match (`request()`); the
Night's Admins are told. Nothing changes until an Admin accepts (FR-18):

- Accepting a cancellation takes the Captain's Team out of the match (`one_team_out`), and
  the replacement search starts (FR-13 to FR-16; fixtures/replacements.py), falling back
  to a friendly or a cancellation (FR-17; fixtures/fallbacks.py).
- Accepting a postponement is a reschedule to the new kick-off the Admin picks.
- The Admin may decline, the Captain may withdraw. The Captain is told of the decision.

Locks: the Fixture first, then the Captain request, in every path.
"""

import copy
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from clubs.models import Field
from core.exceptions import Conflict
from notifications import services as notifications
from notifications import targeting
from notifications.models import Kind, Notification
from notifications.services import match_day, match_time
from teams.models import Team

from . import checkpoints, lifecycle, replacements
from .models import (
    CaptainRequest,
    ConfirmationAnswer,
    Fixture,
    FixtureCheckpoint,
    FixtureReschedule,
    FixtureTransition,
    ReplacementOffer,
    TeamReadiness,
)

S = Fixture.Status
RequestKind = CaptainRequest.Kind
RequestStatus = CaptainRequest.Status

# Everything kept per kick-off. A new kick-off starts with none of these; moving back to a
# kick-off the match already had would bring back its old answers and skip its checkpoints.
PER_KICK_OFF = (FixtureCheckpoint, ConfirmationAnswer, TeamReadiness, ReplacementOffer)

# A match still on its way to being played as a league match.
OPEN_STATUSES = (S.SCHEDULED, S.CONFIRMING, S.READY)

RELATED = ("club__settings", "season", "division__night", "pitch", "home_team", "away_team")

NOT_NOW = "A {status} match can't be rescheduled."
KICKED_OFF = "This match has kicked off, so it can't be changed now."
NOTHING_TO_CHANGE = "Pick a new kick-off or pitch."
NOT_THE_CLUBS_PITCH = "The club has no such pitch."
TOO_SOON = (
    "Kick-off must be after {day}, {time}: Players reply until {hours} hours before kick-off."
)
OUTSIDE_SEASON = "{day} is outside the {season} Season."
WRONG_NIGHT = "{day} isn't a {weekday}, this Division's Night."
PITCH_TAKEN = "{pitch} already has a match at {day}, {time}."
TEAM_BUSY = "{team} already has a match on {day}."
KICK_OFF_USED = (
    "This match already had Confirmations or checks for {day}, {time}. Pick another kick-off."
)
MOVE_RACE = "The Fixtures changed while rescheduling. Try again."

NOT_CAPTAIN = "Only the Captain of a Team in this match can ask to cancel or postpone it."
REQUEST_CLOSED = "This match can't be cancelled or postponed now."
ALREADY_PENDING = "{team} already has a request waiting for the Admin."
NOT_PENDING = "This request has already been {status}."
REQUEST_MOVED_ON = "This match has moved on, so the request can't be accepted. Decline it."
NEEDS_KICK_OFF = "A postponement needs a new kick-off."
NOT_YOURS = "Only {team}'s Captain can withdraw this request."


def _when(kick_off: datetime, pitch: Field) -> str:
    return f"{match_day(kick_off)}, {match_time(kick_off)}, {pitch.name}"


def _match(fixture: Fixture) -> str:
    return f"{fixture.home_team.name} vs {fixture.away_team.name}"


def _hours(value: int) -> timedelta:
    return timedelta(hours=value)


# Rescheduling (FR-7 to FR-9)


@dataclass
class Plan:
    fixture: Fixture
    kick_off: datetime
    pitch: Field
    old_kick_off: datetime
    old_pitch: Field
    status_after: str
    confirmations_now: bool
    answer_by: datetime | None
    players: list
    officials: list

    @property
    def kick_off_changed(self) -> bool:
        return self.kick_off != self.old_kick_off

    @property
    def pitch_changed(self) -> bool:
        return self.pitch.pk != self.old_pitch.pk


def _check(fixture: Fixture, kick_off: datetime, pitch: Field, now: datetime) -> None:
    """Refuses a move the rules don't allow: 409 for the match's state, 400 for the input."""
    if fixture.status not in OPEN_STATUSES:
        raise Conflict(NOT_NOW.format(status=S(fixture.status).label.lower()))
    if fixture.kick_off <= now:
        raise Conflict(KICKED_OFF)
    if pitch.club_id != fixture.club_id:
        raise ValidationError({"pitch": [NOT_THE_CLUBS_PITCH]})
    if kick_off == fixture.kick_off and pitch.pk == fixture.pitch_id:
        raise ValidationError({"non_field_errors": [NOTHING_TO_CHANGE]})
    if kick_off != fixture.kick_off:
        hours = fixture.club.settings.readiness_hours_before
        earliest = now + _hours(hours)
        if kick_off <= earliest:
            raise ValidationError(
                {
                    "kick_off": [
                        TOO_SOON.format(
                            day=match_day(earliest), time=match_time(earliest), hours=hours
                        )
                    ]
                }
            )
        date = timezone.localtime(kick_off).date()
        day = match_day(kick_off)
        season = fixture.season
        if not season.starts_on <= date <= season.ends_on:
            raise ValidationError(
                {"kick_off": [OUTSIDE_SEASON.format(day=day, season=season.name)]}
            )
        night = fixture.division.night
        if date.weekday() != night.weekday:
            raise ValidationError(
                {"kick_off": [WRONG_NIGHT.format(day=day, weekday=night.get_weekday_display())]}
            )
        if any(m.objects.filter(fixture=fixture, kick_off=kick_off).exists() for m in PER_KICK_OFF):
            raise Conflict(KICK_OFF_USED.format(day=day, time=match_time(kick_off)))
    others = Fixture.objects.exclude(pk=fixture.pk).exclude(status=S.CANCELLED)
    if others.filter(pitch=pitch, kick_off=kick_off).exists():
        raise Conflict(
            PITCH_TAKEN.format(pitch=pitch.name, day=match_day(kick_off), time=match_time(kick_off))
        )
    if kick_off != fixture.kick_off:
        start = timezone.localtime(kick_off).replace(hour=0, minute=0, second=0, microsecond=0)
        same_day = others.filter(kick_off__gte=start, kick_off__lt=start + timedelta(days=1))
        for team in (fixture.home_team, fixture.away_team):
            if same_day.filter(Q(home_team=team) | Q(away_team=team)).exists():
                raise Conflict(TEAM_BUSY.format(team=team.name, day=match_day(kick_off)))


def plan(
    fixture: Fixture, kick_off: datetime, pitch: Field | None = None, now: datetime | None = None
) -> Plan:
    """Checks the move and says what it will do. Writes nothing."""
    now = now or timezone.now()
    pitch = pitch or fixture.pitch
    _check(fixture, kick_off, pitch, now)
    club_settings = fixture.club.settings
    moved = copy.copy(fixture)
    moved.kick_off, moved.pitch = kick_off, pitch
    if kick_off == fixture.kick_off:
        status_after, confirmations_now, answer_by = fixture.status, False, None
    else:
        confirmations_now = kick_off - _hours(club_settings.confirmation_hours_before) <= now
        status_after = S.CONFIRMING if confirmations_now else S.SCHEDULED
        answer_by = checkpoints.confirmation_cutoff(moved, club_settings)
    return Plan(
        fixture=fixture,
        kick_off=kick_off,
        pitch=pitch,
        old_kick_off=fixture.kick_off,
        old_pitch=fixture.pitch,
        status_after=status_after,
        confirmations_now=confirmations_now,
        answer_by=answer_by,
        players=list(targeting.reschedule_players(fixture)),
        officials=list(targeting.reschedule_officials(moved, fixture.pitch)),
    )


def _update_text(planned: Plan) -> tuple[str, str]:
    fixture = planned.fixture
    old = _when(planned.old_kick_off, planned.old_pitch)
    new = _when(planned.kick_off, planned.pitch)
    if planned.kick_off_changed:
        title = f"Rescheduled: {_match(fixture)}"
        tail = (
            " Confirmations for the new time are going out now."
            if planned.confirmations_now
            else " Confirmations for the new time go out as usual."
        )
    else:
        title = f"New pitch: {_match(fixture)}"
        tail = " Your reply stands."
    return title[:120], f"Now {new} (was {old}).{tail}"[:500]


def _close_requests(fixture: Fixture, now: datetime, why: str, *, keep=None) -> None:
    """Pending requests for the match no longer apply; their Captains are told."""
    pending = (
        CaptainRequest.objects.select_for_update(of=("self",))
        .filter(fixture=fixture, status=RequestStatus.PENDING)
        .select_related("team")
    )
    if keep is not None:
        pending = pending.exclude(pk=keep.pk)
    for closed in pending:
        closed.status = RequestStatus.CLOSED
        closed.decided_at = now
        closed.note = why[:300]
        closed.save(update_fields=["status", "decided_at", "note"])
        _tell_captain(
            fixture,
            closed,
            f"Your request no longer applies: {_match(fixture)}",
            f"{why} Send a new one if you still need it.",
        )


@transaction.atomic
def reschedule(
    fixture: Fixture,
    kick_off: datetime,
    pitch: Field | None = None,
    *,
    admin,
    note: str = "",
    request: CaptainRequest | None = None,
    now: datetime | None = None,
) -> FixtureReschedule:
    """Moves the Fixture and tells the right people (FR-7 to FR-9). See the module doc."""
    now = now or timezone.now()
    fixture = lifecycle.lock(fixture.pk, *RELATED)
    planned = plan(fixture, kick_off, pitch, now)
    note = note.strip()[:300]
    old = _when(planned.old_kick_off, planned.old_pitch)
    new = _when(planned.kick_off, planned.pitch)
    moved_note = f"Rescheduled from {old} to {new}." + (f" {note}" if note else "")

    fixture.kick_off, fixture.pitch = planned.kick_off, planned.pitch
    try:
        with transaction.atomic():
            fixture.save(update_fields=["kick_off", "pitch"])
    except IntegrityError as error:
        raise Conflict(MOVE_RACE) from error

    if planned.kick_off_changed:
        # Answers, offers and requests were for the old kick-off.
        notifications.close(Notification.objects.filter(fixture=fixture))
        if fixture.status != S.SCHEDULED:
            lifecycle.transition(
                fixture,
                S.SCHEDULED,
                cause=FixtureTransition.Cause.ADMIN,
                actor=admin,
                note=moved_note[:300],
            )
            fixture.status = S.SCHEDULED
        _close_requests(fixture, now, f"The match was rescheduled to {new}.", keep=request)

    # FR-7, FR-8: one Update, to both Teams' Players and only these officials.
    title, body = _update_text(planned)
    told = notifications.notify(
        Kind.UPDATE,
        [*planned.players, *planned.officials],
        club=fixture.club,
        title=title,
        body=body,
        fixture=fixture,
    )
    # FR-9: within the Confirmation window, the Confirmations go out now.
    sent = False
    if planned.confirmations_now:
        sent = checkpoints.send_confirmations(
            fixture.pk,
            now,
            actor=admin,
            note="Rescheduled to within the Confirmation window: Confirmations sent now.",
        )
    return FixtureReschedule.objects.create(
        fixture=fixture,
        from_kick_off=planned.old_kick_off,
        to_kick_off=planned.kick_off,
        from_pitch=planned.old_pitch,
        to_pitch=planned.pitch,
        at=now,
        by=admin,
        note=note,
        request=request,
        confirmations_sent=sent,
        notified=len(told),
    )


# Captain requests (FR-18)


def captain_team(fixture: Fixture, user) -> Team | None:
    """The Fixture's Team `user` captains, if any."""
    for team in (fixture.home_team, fixture.away_team):
        if team.captain_id == user.pk and team.status == Team.Status.ACTIVE:
            return team
    return None


def can_request(fixture: Fixture, now: datetime | None = None) -> bool:
    now = now or timezone.now()
    return fixture.status in OPEN_STATUSES and now < fixture.kick_off


def _tell_captain(fixture: Fixture, captain_request: CaptainRequest, title: str, body: str):
    """An Update to the Team's Captain, if they opted into the Night (targeting rules)."""
    notifications.notify(
        Kind.UPDATE,
        targeting.opted_in_captains([captain_request.team], fixture.night),
        club=fixture.club,
        title=title[:120],
        body=body[:500],
        fixture=fixture,
    )


@transaction.atomic
def request(fixture: Fixture, captain, kind: str, reason: str) -> CaptainRequest:
    """The Captain asks to cancel or postpone the match. 403 for anyone else, 409 when the
    match can't be changed now or the Team already has a request waiting."""
    now = timezone.now()
    fixture = lifecycle.lock(fixture.pk, *RELATED)
    team = captain_team(fixture, captain)
    if team is None:
        raise PermissionDenied(NOT_CAPTAIN)
    if not can_request(fixture, now):
        raise Conflict(REQUEST_CLOSED)
    if CaptainRequest.objects.filter(
        fixture=fixture, team=team, status=RequestStatus.PENDING
    ).exists():
        raise Conflict(ALREADY_PENDING.format(team=team.name))
    created = CaptainRequest.objects.create(
        fixture=fixture,
        team=team,
        kind=kind,
        reason=reason.strip()[:300],
        kick_off=fixture.kick_off,
        requested_by=captain,
        requested_at=now,
        status=RequestStatus.PENDING,
    )
    what = "cancel" if kind == RequestKind.CANCEL else "postpone"
    notifications.notify(
        Kind.UPDATE,
        targeting.night_admins(fixture.night),
        club=fixture.club,
        title=f"{team.name} asks to {what} {_match(fixture)}"[:120],
        body=f"{_when(fixture.kick_off, fixture.pitch)}. {created.reason}"[:500],
        fixture=fixture,
    )
    return created


def _lock_request(captain_request: CaptainRequest) -> tuple[Fixture, CaptainRequest]:
    fixture = lifecycle.lock(captain_request.fixture_id, *RELATED)
    locked = (
        CaptainRequest.objects.select_for_update(of=("self",))
        .select_related("team")
        .get(pk=captain_request.pk)
    )
    if locked.status != RequestStatus.PENDING:
        raise Conflict(NOT_PENDING.format(status=locked.get_status_display().lower()))
    return fixture, locked


def _decide(captain_request: CaptainRequest, status: str, admin, note: str, now) -> None:
    captain_request.status = status
    captain_request.decided_by = admin
    captain_request.decided_at = now
    captain_request.note = note.strip()[:300]
    captain_request.save(update_fields=["status", "decided_by", "decided_at", "note"])


@transaction.atomic
def withdraw(captain_request: CaptainRequest, captain) -> CaptainRequest:
    _fixture, locked = _lock_request(captain_request)
    if locked.team.captain_id != captain.pk:
        raise PermissionDenied(NOT_YOURS.format(team=locked.team.name))
    _decide(locked, RequestStatus.WITHDRAWN, None, "", timezone.now())
    return locked


@transaction.atomic
def decline(captain_request: CaptainRequest, admin, note: str = "") -> CaptainRequest:
    fixture, locked = _lock_request(captain_request)
    _decide(locked, RequestStatus.DECLINED, admin, note, timezone.now())
    what = "cancel" if locked.kind == RequestKind.CANCEL else "postpone"
    because = f" {locked.note}" if locked.note else ""
    _tell_captain(
        fixture,
        locked,
        f"Request declined: {_match(fixture)}",
        f"The Admin declined your request to {what} the match. It goes ahead as planned, "
        f"{_when(fixture.kick_off, fixture.pitch)}.{because}",
    )
    return locked


@transaction.atomic
def accept(
    captain_request: CaptainRequest,
    admin,
    *,
    kick_off: datetime | None = None,
    pitch: Field | None = None,
    note: str = "",
) -> CaptainRequest:
    """The Admin accepts: a cancellation takes the Team out, a postponement is a reschedule
    to `kick_off` (and `pitch`). 409 once the match has moved on from the request."""
    now = timezone.now()
    fixture, locked = _lock_request(captain_request)
    team = locked.team
    if (
        not can_request(fixture, now)
        or fixture.kick_off != locked.kick_off
        or team.pk not in (fixture.home_team_id, fixture.away_team_id)
    ):
        raise Conflict(REQUEST_MOVED_ON)
    if locked.kind == RequestKind.POSTPONE:
        if kick_off is None or kick_off == fixture.kick_off:
            raise ValidationError({"kick_off": [NEEDS_KICK_OFF]})
        _decide(locked, RequestStatus.ACCEPTED, admin, note, now)
        reschedule(fixture, kick_off, pitch, admin=admin, note=note, request=locked, now=now)
        fixture.refresh_from_db()
        _tell_captain(
            fixture,
            locked,
            f"Postponement accepted: {_match(fixture)}",
            f"The match is now {_when(fixture.kick_off, fixture.pitch)}.",
        )
        return locked

    _decide(locked, RequestStatus.ACCEPTED, admin, note, now)
    _close_requests(fixture, now, f"{team.name} withdrew from the match.", keep=locked)
    why = f"{team.name}'s Captain cancelled; accepted by the Admin. {locked.reason}"
    lifecycle.transition(
        fixture, S.ONE_TEAM_OUT, cause=FixtureTransition.Cause.ADMIN, actor=admin, note=why[:300]
    )
    fixture.status = S.ONE_TEAM_OUT
    _tell_captain(
        fixture,
        locked,
        f"Cancellation accepted: {_match(fixture)}",
        f"{team.name} is out of the match, {_when(fixture.kick_off, fixture.pitch)}.",
    )
    # FR-13 to FR-16, and FR-17 when no Team takes the slot.
    replacements.open_offer(fixture, team, actor=admin, now=now)
    return locked
