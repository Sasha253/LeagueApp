"""Friendly fees (FR-24, FR-49): what a friendly costs, who pays it, and its Captain.

An Admin of the Fixture's Club sets, per friendly (`FriendlyFee`):

- the fee: the friendly's total, in rand (0 or more). The form starts at the club's
  `friendly_fee` setting; the Admin can change it per match.
- who pays (`payer`):
  - the borrowed Players: the Players who joined the friendly from outside its Teams;
  - the Team's Players: the current Players of the Team still in it (FR-17). With both
    Teams out there is no Team, so this isn't offered;
  - the club/manager: nothing is collected from Players.
- the Captain who receives the friendly's Payment Barcode and has it verified at the gate:
  a Player who plays in it (one who joined it, or a current Player of the remaining Team).

Terms can be set while the match is a friendly for that kick-off and kick-off is still to
come. The fee and payer are fixed once a payment towards it stands; the Captain can change
(the old Captain's Barcode is revoked and the new one gets one).

Payments are ledger entries in the `friendly` category for the Fixture, on no Team's
account (FR-49: friendly income is its own line). An Admin records cash from a Player in
the payer group, never more than is still owed. If the friendly is cancelled later, they
come back as the Player's credit (fallbacks.cancel_match, FR-43, FR-52).

Locks: the Fixture first, then ledger rows, as in fallbacks.py.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from barcodes import services as barcodes
from core.exceptions import Conflict
from ledger import services as ledger
from ledger.models import LedgerEntry

from . import fallbacks, lifecycle
from .models import Fixture, FixtureFallback, FriendlyFee

Payer = FriendlyFee.Payer
S = Fixture.Status

NOT_A_FRIENDLY = "This match isn't a friendly."
NOT_ON = "This friendly is no longer on."
STARTED = "This friendly has kicked off, so its fee can't change."
NO_TEAM = "Both Teams are out, so no Team's Players can pay. Pick another payer."
FIXED = "Payments have been recorded for this friendly, so its fee and who pays are fixed."
NOT_PLAYING = "The Captain must be a Player in the friendly: one who joined it, or a Player "
NOT_PLAYING += "of the Team still in it."
NOTHING_TO_COLLECT = "Nothing is collected from Players for this friendly."
NOTHING_OWED = "This friendly has nothing left to pay."
MORE_THAN_OWED = "That is more than the friendly still owes."
NOT_A_PAYER = "That Player isn't one of the friendly's payers."
NO_TERMS = "Set the friendly's fee first."


def friendly_fallback(fixture: Fixture) -> FixtureFallback:
    """The friendly the Fixture became. Conflict if it never became one."""
    fallback = (
        FixtureFallback.objects.filter(fixture=fixture, outcome=FixtureFallback.Outcome.FRIENDLY)
        .select_related("remaining_team")
        .first()
    )
    if fallback is None:
        raise Conflict(NOT_A_FRIENDLY)
    return fallback


def is_on(fixture: Fixture, fallback: FixtureFallback) -> bool:
    return fixture.status == S.FRIENDLY and fixture.kick_off == fallback.kick_off


def team_players(fallback: FixtureFallback) -> list[User]:
    """The current Players of the Team still in the friendly; none with both out."""
    team = fallback.remaining_team
    if team is None:
        return []
    return [
        membership.player
        for membership in team.current_memberships()
        .select_related("player")
        .order_by("player__name", "player_id")
    ]


def joined_players(fallback: FixtureFallback) -> list[User]:
    return [invite.player for invite in fallbacks.joined(fallback)]


def borrowed_players(fallback: FixtureFallback) -> list[User]:
    """The Players who joined the friendly from outside the Team still in it."""
    team_ids = {player.pk for player in team_players(fallback)}
    return [player for player in joined_players(fallback) if player.pk not in team_ids]


def captain_candidates(fallback: FixtureFallback) -> list[User]:
    """Who can be the friendly's Captain: anyone who plays in it, by name."""
    people = {player.pk: player for player in team_players(fallback)}
    for player in joined_players(fallback):
        people.setdefault(player.pk, player)
    return sorted(people.values(), key=lambda player: (player.name, player.pk))


def payers(friendly: FriendlyFee) -> list[User]:
    """The Players who can pay towards the fee; none when nothing is collected."""
    if not friendly.collects:
        return []
    if friendly.payer == Payer.TEAM_PLAYERS:
        return team_players(friendly.fallback)
    return borrowed_players(friendly.fallback)


@dataclass(frozen=True)
class Totals:
    due: Decimal
    paid: Decimal
    outstanding: Decimal
    settled: bool


def totals(friendly: FriendlyFee) -> Totals:
    paid = ledger.friendly_paid(friendly.fixture)
    due = friendly.fee if friendly.collects else Decimal("0.00")
    outstanding = max(due - paid, Decimal("0.00"))
    return Totals(due=due, paid=paid, outstanding=outstanding, settled=outstanding <= 0)


def _has_payments(fixture: Fixture) -> bool:
    return ledger.friendly_paid(fixture) > 0


def _lock_friendly(fixture: Fixture) -> tuple[Fixture, FixtureFallback]:
    fixture = lifecycle.lock(fixture.pk, "club", "season", "home_team", "away_team")
    fallback = friendly_fallback(fixture)
    if not is_on(fixture, fallback):
        raise Conflict(NOT_ON)
    return fixture, fallback


@transaction.atomic
def set_terms(
    fixture: Fixture,
    *,
    fee: Decimal,
    payer: str,
    captain: User | None,
    by: User,
    now: datetime | None = None,
) -> FriendlyFee:
    """The Admin sets the friendly's fee, who pays it and its Captain (FR-24)."""
    now = now or timezone.now()
    fixture, fallback = _lock_friendly(fixture)
    if now >= fixture.kick_off:
        raise Conflict(STARTED)
    if isinstance(fee, float):
        raise TypeError("Money must be a Decimal, never a float.")
    if fee < 0:
        raise ValueError("The fee can't be below zero.")
    if payer == Payer.TEAM_PLAYERS and fallback.remaining_team_id is None:
        raise Conflict(NO_TEAM)
    if captain is not None and captain.pk not in {p.pk for p in captain_candidates(fallback)}:
        raise Conflict(NOT_PLAYING)

    friendly = FriendlyFee.objects.filter(fixture=fixture).first()
    if friendly is None:
        friendly = FriendlyFee(fallback=fallback, fixture=fixture)
        previous_captain = None
    else:
        previous_captain = friendly.captain_id
        changes_money = friendly.fee != fee or friendly.payer != payer
        if changes_money and _has_payments(fixture):
            raise Conflict(FIXED)
    friendly.fee = fee
    friendly.payer = payer
    friendly.captain = captain
    friendly.set_by = by
    friendly.set_at = now
    friendly.save()
    barcodes.sync_friendly(
        friendly,
        by=by,
        captain_changed=previous_captain is not None and previous_captain != friendly.captain_id,
    )
    return friendly


@transaction.atomic
def record_cash(
    fixture: Fixture, *, player: User, amount: Decimal, by: User, reason: str = ""
) -> LedgerEntry:
    """Cash paid to the club towards the friendly's fee by one of its payers, recorded by
    an Admin. Never more than the friendly still owes."""
    fixture, _fallback = _lock_friendly(fixture)
    friendly = FriendlyFee.objects.filter(fixture=fixture).select_related("fallback").first()
    if friendly is None:
        raise Conflict(NO_TERMS)
    if not friendly.collects:
        raise Conflict(NOTHING_TO_COLLECT)
    if player.pk not in {p.pk for p in payers(friendly)}:
        raise Conflict(NOT_A_PAYER)
    outstanding = totals(friendly).outstanding
    if outstanding <= 0:
        raise Conflict(NOTHING_OWED)
    if amount > outstanding:
        raise Conflict(MORE_THAN_OWED)
    when = f"{fallbacks.match_day(fixture.kick_off)}"
    entry = ledger.record_friendly_payment(
        fixture=fixture,
        player=player,
        amount=amount,
        method=LedgerEntry.Method.CASH,
        recorded_by=by,
        reason=(reason.strip() or f"Cash for the friendly, {when}")[:300],
    )
    barcodes.sync_friendly(friendly, by=by)
    return entry
