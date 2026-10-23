"""Issuing, showing, revoking and checking Payment Barcodes.

- Issued only to a paid Team (FR-20: an active Team that owes nothing), automatically when
  it is paid (`team_paid`), or by an Admin of its Club (issue or reissue).
- The club's payment mode decides the validity (PRD "Barcode authorisation"): gateway mode
  gives a Barcode for the Team's current match; cash-only mode one for the rest of the
  Season.
- The Captain's Barcode is issued on first look when the Team is paid and has none for
  this match yet (a Season's later matches), never again after an Admin revoked it: then
  only an Admin reissues.
- A Barcode is valid while it is genuine (signed), not revoked, not past its match or
  Season, and its Team is still paid. That is checked at every look and every scan.
- At the gate (`scan`, FR-23) a valid Barcode also has to fit the match: its own match
  (or, for a Season Barcode, the Team's match today or the one the gate names), today,
  still on, the Team not ruled out of it, and not scanned in already: a Barcode lets its
  Team in once per match. Every scan is logged, whatever the result.

Everything here is decided by the backend; the app only shows it.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from clubs.models import Club, PaymentMode
from core.exceptions import Conflict
from fixtures.models import Fixture, TeamReadiness
from ledger import services as ledger
from notifications.models import Kind
from notifications.services import match_day, match_time, notify
from teams.models import Team

from . import signing
from .models import Barcode, BarcodeScan

Mode = Barcode.Mode

NOT_PAID = "This Team hasn't paid yet."
NO_MATCH = "This Team has no match coming up."
NOT_ACTIVE = "This Team isn't active."
ALREADY_REVOKED = "This Barcode is already revoked."
REISSUED = "Reissued by an Admin."
ATTEMPTS = 5  # New nonces tried if a code is already taken (one in 2^50 each time).

FINISHED = (Fixture.Status.CANCELLED, Fixture.Status.PLAYED)
OFF = (*FINISHED, Fixture.Status.BOTH_TEAMS_OUT)  # Matches nobody is let in for.


class State:
    """Why a Barcode is or isn't valid. One name per reason, for the app and the gate."""

    VALID = "valid"
    NOT_GENUINE = "not_genuine"
    REVOKED = "revoked"
    EXPIRED = "expired"
    UNPAID = "unpaid"
    INACTIVE = "inactive"
    NO_MATCH = "no_match"
    NOT_FOUND = "not_found"
    # At the gate only (`scan`):
    WRONG_MATCH = "wrong_match"
    NOT_TODAY = "not_today"
    NO_MATCH_TODAY = "no_match_today"
    MATCH_OFF = "match_off"
    RULED_OUT = "ruled_out"
    USED = "used"

    choices = [
        (VALID, "Valid"),
        (NOT_GENUINE, "Not genuine"),
        (REVOKED, "Revoked"),
        (EXPIRED, "No longer valid"),
        (UNPAID, "Not paid"),
        (INACTIVE, "Team not active"),
        (NO_MATCH, "No match coming up"),
        (NOT_FOUND, "No such Barcode"),
    ]
    # A scan at the gate answers any of the above, or one of these.
    scan_choices = [
        *choices,
        (WRONG_MATCH, "Not for this match"),
        (NOT_TODAY, "Not for today"),
        (NO_MATCH_TODAY, "No match today"),
        (MATCH_OFF, "Match is off"),
        (RULED_OUT, "Team ruled out"),
        (USED, "Already scanned"),
    ]


@dataclass(frozen=True)
class Status:
    state: str
    reason: str = ""

    @property
    def valid(self) -> bool:
        return self.state == State.VALID


def _rand(amount: Decimal) -> str:
    """Money as the app shows it: "R 5", "R 18,550", "R 12.50"."""
    return f"R {amount:,.0f}" if amount == amount.to_integral_value() else f"R {amount:,.2f}"


def _day(date: dt.date) -> str:
    return f"{date:%a} {date.day} {date:%b}"


def _today() -> dt.date:
    return timezone.localdate()


def _start_of(date: dt.date) -> dt.datetime:
    return timezone.make_aware(dt.datetime.combine(date, dt.time()))


def _lock(team: Team) -> Team:
    return (
        Team.objects.select_for_update(of=("self",))
        .select_related("club__settings", "season")
        .get(pk=team.pk)
    )


def next_match(team: Team) -> Fixture | None:
    """The Team's current match: its first match not cancelled or played, on today's date
    (South African time) or later."""
    return (
        Fixture.objects.filter(Q(home_team=team) | Q(away_team=team))
        .filter(kick_off__gte=_start_of(_today()))
        .exclude(status__in=FINISHED)
        .select_related("home_team", "away_team", "pitch")
        .order_by("kick_off", "pk")
        .first()
    )


def status_of(barcode: Barcode) -> Status:
    """Whether `barcode` proves its Team has paid, right now, and if not why not."""
    if not signing.is_signed(barcode):
        return Status(State.NOT_GENUINE, "This Barcode isn't genuine.")
    if barcode.revoked_at is not None:
        return Status(State.REVOKED, f"This Barcode was revoked: {barcode.revoke_reason}")
    team = barcode.team
    if team.status != Team.Status.ACTIVE:
        return Status(State.INACTIVE, NOT_ACTIVE)
    today = _today()
    if barcode.mode == Mode.MATCH:
        fixture = barcode.fixture
        played_on = timezone.localdate(fixture.kick_off)
        if fixture.status == Fixture.Status.CANCELLED:
            return Status(State.EXPIRED, f"The match on {_day(played_on)} was cancelled.")
        if fixture.status == Fixture.Status.PLAYED or played_on < today:
            return Status(
                State.EXPIRED, f"This Barcode was for {_day(played_on)}. It isn't valid now."
            )
        if team.pk not in (fixture.home_team_id, fixture.away_team_id):
            return Status(
                State.EXPIRED,
                f"{team.name} no longer plays in the match on {_day(played_on)}.",
            )
    elif barcode.season.ends_on < today:
        return Status(State.EXPIRED, f"The {barcode.season.name} Season has ended.")
    balance = ledger.team_balance(team)
    if not balance.is_paid:
        return Status(State.UNPAID, f"{team.name} still owes {_rand(balance.outstanding)}.")
    return Status(State.VALID)


# Issuing


def _create(team: Team, mode: str, fixture: Fixture | None, by: User | None) -> Barcode:
    for _ in range(ATTEMPTS):
        barcode = Barcode(
            club=team.club,
            team=team,
            mode=mode,
            season=team.season,
            fixture=fixture,
            nonce=signing.new_nonce(),
            issued_by=by,
        )
        barcode.code = signing.sign(barcode)
        try:
            with transaction.atomic():
                barcode.save()
        except IntegrityError:
            if Barcode.objects.filter(code=barcode.code).exists():
                continue  # The code is taken: try another nonce.
            raise
        return barcode
    raise RuntimeError("Couldn't find a free Barcode code.")


def _scope(team: Team, mode: str, fixture: Fixture | None):
    if mode == Mode.SEASON:
        return Barcode.objects.filter(team=team, mode=Mode.SEASON, season=team.season)
    return Barcode.objects.filter(team=team, mode=Mode.MATCH, fixture=fixture)


def _mode_of(team: Team) -> str:
    if team.club.settings.payment_mode == PaymentMode.CASH_ONLY:
        return Mode.SEASON
    return Mode.MATCH


def _tell_captain(barcode: Barcode) -> None:
    captain = barcode.team.captain
    if captain is None:
        return
    if barcode.mode == Mode.MATCH:
        kick_off = barcode.fixture.kick_off
        valid = f"Valid for your match on {match_day(kick_off)} at {match_time(kick_off)}."
    else:
        valid = f"Valid until {_day(barcode.season.ends_on)}."
    notify(
        Kind.UPDATE,
        [captain],
        club=barcode.club,
        title=f"Payment Barcode for {barcode.team.name}",
        body=f"{barcode.team.name} has paid. {valid} Show it at the gate.",
        fixture=barcode.fixture,
    )


def _issuable(team: Team) -> tuple[str, Fixture | None]:
    """The mode and match a Barcode would be issued for now. Conflict if none can be."""
    if team.status != Team.Status.ACTIVE:
        raise Conflict(NOT_ACTIVE)
    if not ledger.team_balance(team).is_paid:
        raise Conflict(NOT_PAID)
    mode = _mode_of(team)
    fixture = None
    if mode == Mode.MATCH:
        fixture = next_match(team)
        if fixture is None:
            raise Conflict(NO_MATCH)
    return mode, fixture


@transaction.atomic
def issue(team: Team, *, by: User) -> Barcode:
    """An Admin issues the Team's Barcode, or reissues it: a live one for the same match
    (or Season) is revoked first. Only for a paid Team. The Captain is told."""
    team = _lock(team)
    mode, fixture = _issuable(team)
    now = timezone.now()
    for live in _scope(team, mode, fixture).filter(revoked_at__isnull=True):
        live.revoked_at, live.revoked_by, live.revoke_reason = now, by, REISSUED
        live.save(update_fields=["revoked_at", "revoked_by", "revoke_reason"])
    barcode = _create(team, mode, fixture, by)
    _tell_captain(barcode)
    return barcode


def issue_on_payment(team: Team) -> Barcode | None:
    """When a Team is paid (`team_paid`): its Barcode, unless it already has one for this
    match (or Season), live or revoked. Call inside the payment's transaction."""
    team = _lock(team)
    try:
        mode, fixture = _issuable(team)
    except Conflict:
        return None  # No match yet: issued when the Captain opens it.
    if _scope(team, mode, fixture).exists():
        return None
    barcode = _create(team, mode, fixture, None)
    _tell_captain(barcode)
    return barcode


@dataclass(frozen=True)
class Current:
    barcode: Barcode | None
    status: Status


@transaction.atomic
def current_for(team: Team) -> Current:
    """The Barcode the Captain shows at the gate now, or why there is none.

    A live Season Barcode still in its Season wins; else the one for the current match,
    issued now if the Team is paid and has never had one for it.
    """
    team = _lock(team)
    if team.status != Team.Status.ACTIVE:
        return Current(None, Status(State.INACTIVE, NOT_ACTIVE))

    season_barcode = (
        Barcode.objects.filter(team=team, mode=Mode.SEASON, season=team.season)
        .select_related("team", "season", "fixture")
        .first()
    )
    mode = _mode_of(team)
    if season_barcode is not None:
        status = status_of(season_barcode)
        # In gateway mode (the club changed mode in the Season) only a valid Season Barcode
        # wins; otherwise the current match's Barcode is the one that counts.
        if status.state != State.EXPIRED and (mode == Mode.SEASON or status.valid):
            return _shown(season_barcode, status)

    fixture = next_match(team)
    if fixture is not None:
        match_barcode = (
            Barcode.objects.filter(team=team, mode=Mode.MATCH, fixture=fixture)
            .select_related("team", "season", "fixture")
            .first()
        )
        if match_barcode is not None:
            return _shown(match_barcode, status_of(match_barcode))

    balance = ledger.team_balance(team)
    if not balance.is_paid:
        reason = f"{team.name} still owes {_rand(balance.outstanding)}."
        return Current(None, Status(State.UNPAID, reason))
    if mode == Mode.MATCH and fixture is None:
        return Current(None, Status(State.NO_MATCH, NO_MATCH))
    if mode == Mode.SEASON and season_barcode is not None:
        return Current(None, status_of(season_barcode))  # Its Season has ended.
    barcode = _create(team, mode, fixture, None)
    return Current(barcode, status_of(barcode))


def _shown(barcode: Barcode, status: Status) -> Current:
    """Only a valid Barcode is shown; otherwise only why not."""
    return Current(barcode if status.valid else None, status)


@transaction.atomic
def revoke(barcode: Barcode, *, by: User, reason: str) -> Barcode:
    barcode = Barcode.objects.select_for_update().get(pk=barcode.pk)
    if barcode.revoked_at is not None:
        raise Conflict(ALREADY_REVOKED)
    barcode.revoked_at = timezone.now()
    barcode.revoked_by = by
    barcode.revoke_reason = reason.strip()[:300]
    barcode.save(update_fields=["revoked_at", "revoked_by", "revoke_reason"])
    return barcode


# Scanning


@dataclass(frozen=True)
class ScanResult:
    scan: BarcodeScan
    barcode: Barcode | None
    status: Status
    match: Fixture | None = None

    @property
    def paid(self) -> bool:
        return self.status.valid


def _plays_in(team: Team, fixture: Fixture) -> bool:
    return team.pk in (fixture.home_team_id, fixture.away_team_id)


def _admitted(barcode: Barcode, fixture: Fixture) -> BarcodeScan | None:
    """The scan that already let `barcode`'s Team in for `fixture`, if any."""
    return (
        BarcodeScan.objects.filter(barcode=barcode, fixture=fixture, result=BarcodeScan.Result.PAID)
        .select_related("scanned_by")
        .first()
    )


def _match_today(barcode: Barcode) -> Fixture | None:
    """For a Season Barcode: the Team's match today that is still on, the first one it
    hasn't been let in for yet (else the first)."""
    team = barcode.team
    today = _today()
    matches = list(
        Fixture.objects.filter(Q(home_team=team) | Q(away_team=team))
        .filter(
            kick_off__gte=_start_of(today),
            kick_off__lt=_start_of(today + dt.timedelta(days=1)),
        )
        .exclude(status__in=OFF)
        .select_related("home_team", "away_team", "pitch")
        .order_by("kick_off", "pk")
    )
    for match in matches:
        if _admitted(barcode, match) is None:
            return match
    return matches[0] if matches else None


def _off_reason(match: Fixture) -> str:
    day = _day(timezone.localdate(match.kick_off))
    if match.status == Fixture.Status.CANCELLED:
        return f"The match on {day} was cancelled."
    if match.status == Fixture.Status.PLAYED:
        return f"The match on {day} has been played."
    return f"The match on {day} is off: both Teams are out."


def _at_the_gate(barcode: Barcode, fixture: Fixture | None) -> tuple[Status, Fixture | None]:
    """Whether a valid `barcode` lets its Team in now, for which match. `fixture` is the
    match the gate is checking for, when it says."""
    team = barcode.team
    if barcode.mode == Mode.MATCH:
        match = barcode.fixture
        if fixture is not None and fixture.pk != match.pk:
            played_on = _day(timezone.localdate(match.kick_off))
            return (
                Status(
                    State.WRONG_MATCH,
                    f"This Barcode is for {team.name}'s match on {played_on}, not this one.",
                ),
                fixture,
            )
    elif fixture is not None:
        if not _plays_in(team, fixture):
            return Status(State.WRONG_MATCH, f"{team.name} doesn't play in this match."), fixture
        match = fixture
    else:
        match = _match_today(barcode)
        if match is None:
            return Status(State.NO_MATCH_TODAY, f"{team.name} has no match today."), None

    if match.status in OFF:
        return Status(State.MATCH_OFF, _off_reason(match)), match
    played_on = timezone.localdate(match.kick_off)
    if played_on != _today():
        return (
            Status(
                State.NOT_TODAY, f"This Barcode is for {_day(played_on)}. It isn't valid today."
            ),
            match,
        )
    ruled_out = TeamReadiness.objects.filter(
        fixture=match,
        team=team,
        kick_off=match.kick_off,
        outcome=TeamReadiness.Outcome.OUT,
    ).exists()
    if ruled_out:
        return Status(State.RULED_OUT, f"{team.name} was ruled out of this match."), match
    earlier = _admitted(barcode, match)
    if earlier is not None:
        return Status(State.USED, _used_reason(earlier)), match
    return Status(State.VALID), match


def _used_reason(earlier: BarcodeScan | None) -> str:
    if earlier is None:
        return "Already scanned. A Barcode lets its Team in once per match."
    at = timezone.localtime(earlier.scanned_at)
    return (
        f"Already scanned at {at:%H:%M} by {earlier.scanned_by.name}. "
        "A Barcode lets its Team in once per match."
    )


def _log(**fields) -> BarcodeScan:
    fields["reason"] = fields["reason"][:300]
    return BarcodeScan.objects.create(**fields)


@transaction.atomic
def scan(
    entered: str,
    *,
    club: Club,
    by: User,
    method: str,
    fixture: Fixture | None = None,
) -> ScanResult:
    """Checks a scanned or typed code at `club`'s gate (FR-23), and logs the scan whatever
    the result. Only this club's Barcodes are found. `fixture` is the match the gate is
    checking for, when it says; else the Barcode's own match (or, for a Season Barcode,
    the Team's match today).

    Paid means: the Barcode is valid (`status_of`), its match is today and still on, the
    Team isn't ruled out of it, and the Barcode hasn't let the Team in for it already.
    """
    code = signing.normalise(entered)
    barcode = None
    if code is not None:
        # Locked, so two gates scanning the same Barcode at once can't both let it in.
        barcode = (
            Barcode.objects.select_for_update(of=("self",))
            .filter(club=club, code=code)
            .select_related("team", "season", "fixture")
            .first()
        )
    match = fixture
    if barcode is None:
        status = Status(State.NOT_FOUND, "No Barcode has this code.")
    else:
        status = status_of(barcode)
        if status.valid:
            status, match = _at_the_gate(barcode, fixture)
        elif match is None:
            match = barcode.fixture
    entry = {
        "club": club,
        "barcode": barcode,
        "code": entered.strip()[:40],
        "method": method,
        "fixture": match,
        "scanned_by": by,
    }
    if status.valid:
        try:
            with transaction.atomic():
                logged = _log(**entry, result=BarcodeScan.Result.PAID, reason="")
        except IntegrityError:
            # Let in by another gate in the same moment (the constraint backs the lock).
            status = Status(State.USED, _used_reason(_admitted(barcode, match)))
        else:
            return ScanResult(logged, barcode, status, match)
    logged = _log(**entry, result=BarcodeScan.Result.NOT_PAID, reason=status.reason)
    return ScanResult(logged, barcode, status, match)
