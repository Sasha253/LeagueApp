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
- Every scan is logged (`scan`). Matching the scan to tonight's match and refusing a
  reused per-match Barcode is the gate's job (chunk 21).

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
from fixtures.models import Fixture
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
    if season_barcode is not None:
        status = status_of(season_barcode)
        if status.state != State.EXPIRED:
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
    mode = _mode_of(team)
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

    @property
    def paid(self) -> bool:
        return self.status.valid


def scan(
    entered: str,
    *,
    club: Club,
    by: User,
    method: str,
    fixture: Fixture | None = None,
) -> ScanResult:
    """Checks a scanned or typed code at `club`'s gate, and logs the scan whatever the
    result. Only this club's Barcodes are found."""
    code = signing.normalise(entered)
    barcode = None
    if code is not None:
        barcode = (
            Barcode.objects.filter(club=club, code=code)
            .select_related("team", "season", "fixture")
            .first()
        )
    if barcode is None:
        status = Status(State.NOT_FOUND, "No Barcode has this code.")
    else:
        status = status_of(barcode)
    logged = BarcodeScan.objects.create(
        club=club,
        barcode=barcode,
        code=entered.strip()[:40],
        method=method,
        fixture=fixture,
        scanned_by=by,
        result=BarcodeScan.Result.PAID if status.valid else BarcodeScan.Result.NOT_PAID,
        reason=status.reason[:300],
    )
    return ScanResult(logged, barcode, status)
