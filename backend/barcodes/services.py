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

A friendly's Barcode (FR-24) is tied to the friendly, not a Team: issued to the Captain the
Admin assigned once the friendly's fee is settled (paid, free, or paid by the club), valid
for that match while it is still a friendly. A new Captain revokes the old one. A Team's
own Barcode doesn't let it into a match that has become a friendly.

A Booking's Barcode (FR-30) is tied to the Booking: issued to the Booking User when an
Admin accepts it, revoked when it is cancelled or rescheduled. It is valid while the Booking
is accepted, not over, and paid (until chunk 24 takes Booking payments, only a R 0 Booking
is paid). At the gate it counts on the Booking's day only, once per Booking, and only an
Admin of the club checks it (PRD roles: Referees check Teams).

Everything here is decided by the backend; the app only shows it.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import ClubRole, User
from bookings import money as booking_money
from bookings.models import Booking
from clubs.models import Club, PaymentMode
from core.exceptions import Conflict
from fixtures.models import Fixture, FriendlyFee, ReplacementOffer, TeamReadiness
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
NOT_LEAGUE = (*FINISHED, Fixture.Status.FRIENDLY)  # Matches a Team's own Barcode isn't for.
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
    FRIENDLY = "friendly"
    # A friendly's Barcode only:
    NO_CAPTAIN = "no_captain"
    # A Booking's Barcode only:
    NOT_ACCEPTED = "not_accepted"
    ADMINS_ONLY = "admins_only"

    choices = [
        (VALID, "Valid"),
        (NOT_GENUINE, "Not genuine"),
        (REVOKED, "Revoked"),
        (EXPIRED, "No longer valid"),
        (UNPAID, "Not paid"),
        (INACTIVE, "Team not active"),
        (NO_MATCH, "No match coming up"),
        (NOT_FOUND, "No such Barcode"),
        (NO_CAPTAIN, "No Captain assigned"),
        (NOT_ACCEPTED, "Booking not accepted"),
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
        (FRIENDLY, "Match is now a friendly"),
        (ADMINS_ONLY, "Only an Admin checks bookings"),
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
    """The Team's current match: its first match not cancelled, played or turned into a
    friendly, on today's date (South African time) or later."""
    return (
        Fixture.objects.filter(Q(home_team=team) | Q(away_team=team))
        .filter(kick_off__gte=_start_of(_today()))
        .exclude(status__in=NOT_LEAGUE)
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
    if barcode.friendly_id is not None:
        return _friendly_status(barcode)
    if barcode.booking_id is not None:
        return _booking_status(barcode.booking)
    team = barcode.team
    if team.status != Team.Status.ACTIVE:
        return Status(State.INACTIVE, NOT_ACTIVE)
    today = _today()
    if barcode.mode == Mode.MATCH:
        fixture = barcode.fixture
        played_on = timezone.localdate(fixture.kick_off)
        if fixture.status == Fixture.Status.CANCELLED:
            return Status(State.EXPIRED, f"The match on {_day(played_on)} was cancelled.")
        if fixture.status == Fixture.Status.FRIENDLY:
            return Status(
                State.EXPIRED,
                f"The match on {_day(played_on)} is now a friendly. "
                "Its Captain has the friendly's Barcode.",
            )
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


def _create(
    team: Team | None,
    mode: str,
    fixture: Fixture | None,
    by: User | None,
    friendly: FriendlyFee | None = None,
    booking: Booking | None = None,
) -> Barcode:
    if booking is not None:
        club, season = booking.club, None
    elif team is None:
        club, season = fixture.club, fixture.season
    else:
        club, season = team.club, team.season
    for _ in range(ATTEMPTS):
        barcode = Barcode(
            club=club,
            team=team,
            friendly=friendly,
            booking=booking,
            mode=mode,
            season=season,
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


# Friendlies (FR-24)

FRIENDLY_NOT_ON = "This friendly is no longer on."
NO_FRIENDLY_CAPTAIN = "No Captain has been assigned to this friendly yet."
CAPTAIN_CHANGED = "The friendly's Captain changed."


def friendly_is_on(friendly: FriendlyFee) -> bool:
    fixture = friendly.fixture
    return (
        fixture.status == Fixture.Status.FRIENDLY and fixture.kick_off == friendly.fallback.kick_off
    )


def friendly_outstanding(friendly: FriendlyFee) -> Decimal:
    """What is still to be paid towards the friendly's fee; 0 when nothing is collected."""
    if not friendly.collects:
        return Decimal("0.00")
    return friendly.fee - ledger.friendly_paid(friendly.fixture)


def friendly_settled(friendly: FriendlyFee) -> bool:
    """Its fee is paid, free, or paid by the club/manager."""
    return friendly_outstanding(friendly) <= 0


def _friendly_status(barcode: Barcode) -> Status:
    friendly = barcode.friendly
    fixture = barcode.fixture
    played_on = timezone.localdate(fixture.kick_off)
    if not friendly_is_on(friendly):
        return Status(State.EXPIRED, FRIENDLY_NOT_ON)
    if played_on < _today():
        return Status(State.EXPIRED, f"This Barcode was for {_day(played_on)}. It isn't valid now.")
    outstanding = friendly_outstanding(friendly)
    if outstanding > 0:
        return Status(State.UNPAID, f"The friendly still owes {_rand(outstanding)}.")
    return Status(State.VALID)


def _tell_friendly_captain(barcode: Barcode) -> None:
    friendly = barcode.friendly
    kick_off = barcode.fixture.kick_off
    notify(
        Kind.UPDATE,
        [friendly.captain],
        club=barcode.club,
        title="Payment Barcode for the friendly",
        body=(
            f"You are the Captain of the friendly on {match_day(kick_off)} at "
            f"{match_time(kick_off)}. Show its Barcode at the gate."
        ),
        fixture=barcode.fixture,
    )


def _live_friendly(friendly: FriendlyFee):
    return Barcode.objects.filter(friendly=friendly, revoked_at__isnull=True)


def sync_friendly(friendly: FriendlyFee, *, by: User | None, captain_changed: bool = False):
    """After the friendly's terms or payments change: a new Captain (or none) revokes the
    live Barcode; a settled friendly with a Captain and no live Barcode gets one, and the
    Captain is told. Returns the new Barcode, if one was issued. Call in a transaction
    with the Fixture locked."""
    now = timezone.now()
    if captain_changed:
        for live in _live_friendly(friendly).select_for_update():
            live.revoked_at, live.revoked_by, live.revoke_reason = now, by, CAPTAIN_CHANGED
            live.save(update_fields=["revoked_at", "revoked_by", "revoke_reason"])
    if friendly.captain_id is None or not friendly_is_on(friendly):
        return None
    if not friendly_settled(friendly) or _live_friendly(friendly).exists():
        return None
    barcode = _create(None, Mode.MATCH, friendly.fixture, None, friendly=friendly)
    _tell_friendly_captain(barcode)
    return barcode


@transaction.atomic
def current_for_friendly(friendly: FriendlyFee) -> Current:
    """The friendly's Barcode its Captain shows at the gate now, or why there is none.
    Issued on first look when it is due and has never been issued; never again after an
    Admin revoked it (an Admin saving the friendly's terms issues a new one)."""
    Fixture.objects.select_for_update().filter(pk=friendly.fixture_id).values_list("pk").get()
    live = (
        _live_friendly(friendly)
        .select_related("season", "fixture__home_team", "fixture__away_team", "fixture__pitch")
        .first()
    )
    if live is not None:
        return _shown(live, status_of(live))
    if not friendly_is_on(friendly):
        return Current(None, Status(State.EXPIRED, FRIENDLY_NOT_ON))
    if friendly.captain_id is None:
        return Current(None, Status(State.NO_CAPTAIN, NO_FRIENDLY_CAPTAIN))
    outstanding = friendly_outstanding(friendly)
    if outstanding > 0:
        return Current(None, Status(State.UNPAID, f"The friendly still owes {_rand(outstanding)}."))
    latest = Barcode.objects.filter(friendly=friendly).select_related("fixture").first()
    if latest is not None:
        return Current(None, status_of(latest))  # Revoked by an Admin.
    barcode = _create(None, Mode.MATCH, friendly.fixture, None, friendly=friendly)
    return _shown(barcode, status_of(barcode))


# Bookings (FR-30)

BOOKING_OVER = "This booking is over."


def _booking_not_on(booking: Booking) -> str:
    if booking.status == Booking.Status.PENDING:
        return "This booking is waiting for an Admin."
    if booking.status == Booking.Status.DECLINED:
        return "This booking was declined."
    return "This booking was cancelled."


def _booking_status(booking: Booking) -> Status:
    if booking.status != Booking.Status.ACCEPTED:
        return Status(State.NOT_ACCEPTED, _booking_not_on(booking))
    if booking.ends_at <= timezone.now():
        return Status(State.EXPIRED, BOOKING_OVER)
    outstanding = booking_money.outstanding(booking)
    if outstanding > 0:
        return Status(State.UNPAID, f"The booking still owes {_rand(outstanding)}.")
    return Status(State.VALID)


def _live_booking(booking: Booking):
    return Barcode.objects.filter(booking=booking, revoked_at__isnull=True)


def issue_for_booking(booking: Booking) -> Barcode:
    """The accepted Booking's Barcode (FR-30). Call in the accept's transaction, with the
    Booking locked. A live one left from before is revoked first."""
    for live in _live_booking(booking).select_for_update():
        live.revoked_at, live.revoke_reason = timezone.now(), REISSUED
        live.save(update_fields=["revoked_at", "revoke_reason"])
    return _create(None, Mode.BOOKING, None, None, booking=booking)


def revoke_for_booking(booking: Booking, *, by: User | None, reason: str) -> None:
    """A cancelled or rescheduled Booking's Barcode no longer counts."""
    now = timezone.now()
    for live in _live_booking(booking).select_for_update():
        live.revoked_at, live.revoked_by, live.revoke_reason = now, by, reason[:300]
        live.save(update_fields=["revoked_at", "revoked_by", "revoke_reason"])


def current_for_booking(booking: Booking) -> tuple[Barcode | None, Status]:
    """The Booking's live Barcode and whether it counts at the gate now; the Booking User
    sees it as soon as the Booking is accepted (FR-30), paid or not."""
    live = _live_booking(booking).select_related("booking__user", "booking__field").first()
    if live is None:
        if booking.status == Booking.Status.ACCEPTED:
            latest = Barcode.objects.filter(booking=booking).first()
            if latest is not None:  # Revoked by an Admin.
                return None, status_of(latest)
        return None, _booking_status(booking)
    return live, status_of(live)


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
    if barcode.booking_id is not None:
        return _booking_at_the_gate(barcode, fixture), fixture
    if barcode.mode == Mode.MATCH:
        match = barcode.fixture
        if fixture is not None and fixture.pk != match.pk:
            played_on = _day(timezone.localdate(match.kick_off))
            whose = "the friendly" if team is None else f"{team.name}'s match"
            return (
                Status(
                    State.WRONG_MATCH,
                    f"This Barcode is for {whose} on {played_on}, not this one.",
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
    if match.status == Fixture.Status.FRIENDLY and barcode.friendly_id is None:
        return (
            Status(
                State.FRIENDLY,
                "This match is now a friendly. Scan the Barcode its Captain was given.",
            ),
            match,
        )
    played_on = timezone.localdate(match.kick_off)
    if played_on != _today():
        return (
            Status(
                State.NOT_TODAY, f"This Barcode is for {_day(played_on)}. It isn't valid today."
            ),
            match,
        )
    if team is None:  # A friendly's Barcode: no Team to be ruled out.
        # Once per friendly, not per Barcode: a new Captain's Barcode doesn't let it in again.
        earlier = (
            BarcodeScan.objects.filter(
                barcode__friendly_id=barcode.friendly_id,
                fixture=match,
                result=BarcodeScan.Result.PAID,
            )
            .select_related("scanned_by")
            .first()
        )
        if earlier is not None:
            return Status(State.USED, _used_reason(earlier)), match
        return Status(State.VALID), match
    ruled_out = TeamReadiness.objects.filter(
        fixture=match,
        team=team,
        kick_off=match.kick_off,
        outcome=TeamReadiness.Outcome.OUT,
    ).exists()
    if ruled_out:
        return Status(State.RULED_OUT, f"{team.name} was ruled out of this match."), match
    # Out by any other way too (a Captain's cancellation the Admin accepted): every Team
    # out of a match has its slot offered to other Teams, whether or not one took it.
    withdrew = ReplacementOffer.objects.filter(
        fixture=match, out_team=team, kick_off=match.kick_off
    ).exists()
    if withdrew:
        return Status(State.RULED_OUT, f"{team.name} is out of this match."), match
    earlier = _admitted(barcode, match)
    if earlier is not None:
        return Status(State.USED, _used_reason(earlier)), match
    return Status(State.VALID), match


def _booking_at_the_gate(barcode: Barcode, fixture: Fixture | None) -> Status:
    booking = barcode.booking
    starts_on = timezone.localdate(booking.starts_at)
    if fixture is not None:
        return Status(
            State.WRONG_MATCH, f"This Barcode is for a booking on {_day(starts_on)}, not a match."
        )
    if starts_on != _today():
        return Status(
            State.NOT_TODAY, f"This Barcode is for {_day(starts_on)}. It isn't valid today."
        )
    # Once per Booking, not per Barcode: a reissued Barcode doesn't let it in again.
    earlier = (
        BarcodeScan.objects.filter(barcode__booking_id=booking.pk, result=BarcodeScan.Result.PAID)
        .select_related("scanned_by")
        .first()
    )
    if earlier is not None:
        at = timezone.localtime(earlier.scanned_at)
        return Status(
            State.USED,
            f"Already scanned at {at:%H:%M} by {earlier.scanned_by.name}. "
            "A booking's Barcode lets it in once.",
        )
    return Status(State.VALID)


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
            .select_related("team", "season", "fixture", "booking__user", "booking__field")
            .first()
        )
    match = fixture
    if barcode is None:
        status = Status(State.NOT_FOUND, "No Barcode has this code.")
    elif (
        barcode.booking_id is not None
        and not by.club_roles.filter(club=club, role=ClubRole.Role.ADMIN).exists()
    ):
        status = Status(State.ADMINS_ONLY, "Only an Admin checks a booking's Barcode.")
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
