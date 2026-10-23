"""Paying what a Team owes: a Player's contribution by credit and card, and cash.

- A Player in an active Team chooses how much to pay, up to what the Team still owes
  (FR-19). Credit can be spent first: the Player's own, or, for the Captain, the Team's
  (FR-52). The rest is paid by card at the gateway.
- A card payment is recorded in the ledger only once the gateway's notification passes
  every check, and only once however often it is sent (`handle_notification`).
- An Admin of the Team's Club records cash paid to the club (FR-22).
- When a payment takes what the Team owes to nothing, `team_paid` is sent (FR-20).

Amounts are decided here, never by the app.
"""

import uuid
from collections.abc import Callable
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import User
from clubs.models import PaymentMode
from core.exceptions import Conflict
from ledger import services as ledger
from ledger.models import LedgerEntry
from teams.models import Team

from .gateways import NotificationRejected, gateway_for
from .models import GatewayNotification, Payment
from .signals import team_paid

Status = Payment.Status
Credit = Payment.Credit
Outcome = GatewayNotification.Outcome

NOT_ACTIVE = "This Team isn't active."
NOT_IN_TEAM = "You aren't in this Team."
NOTHING_OWED = "This Team has nothing left to pay."
MORE_THAN_OWED = "That is more than the Team still owes."
NO_CREDIT = "There is no credit to use."
ONLY_CAPTAIN_TEAM_CREDIT = "Only the Team's Captain can spend its credit."
CASH_ONLY = "This club takes cash only. Pay an Admin of the club."
CARD_NOT_SET_UP = "Card payments aren't set up for this club yet."


def _rand(amount: Decimal) -> str:
    """Money as the app shows it: "R 5", "R 18,550", "R 12.50"."""
    return f"R {amount:,.0f}" if amount == amount.to_integral_value() else f"R {amount:,.2f}"


def _below_minimum(minimum: Decimal) -> str:
    return f"Pay at least {_rand(minimum)} by card, or use less credit."


def _lock(team: Team) -> Team:
    return (
        Team.objects.select_for_update(of=("self",))
        .select_related("club__settings")
        .get(pk=team.pk)
    )


def _is_member(team: Team, player: User) -> bool:
    return team.current_memberships().filter(player=player).exists()


def paying(team: Team, write: Callable[[], LedgerEntry]) -> LedgerEntry:
    """Runs `write` (a payment) with the Team locked, and sends `team_paid` if it took
    what the Team owes from above zero to zero or below. Call inside a transaction."""
    team = _lock(team)
    before = ledger.team_balance(team).outstanding
    entry = write()
    if before > 0 >= ledger.team_balance(team).outstanding:
        team_paid.send(sender=Team, team=team)
    return entry


def card_options(team: Team) -> tuple[bool, Decimal | None]:
    """Whether the Team's Club takes cards now, and the smallest card amount."""
    club_settings = team.club.settings
    if club_settings.payment_mode != PaymentMode.GATEWAY:
        return False, None
    gateway = gateway_for(club_settings.payment_provider)
    return gateway.merchant_id_for(team.club) is not None, gateway.minimum_amount


@transaction.atomic
def start_payment(*, team: Team, player: User, amount: Decimal, credit: str) -> Payment:
    """A Player's contribution towards what their Team owes: credit first if chosen, the
    rest by card. Credit is spent at once; the card part waits for the gateway."""
    team = _lock(team)
    if team.status != Team.Status.ACTIVE:
        raise Conflict(NOT_ACTIVE)
    if not _is_member(team, player):
        raise Conflict(NOT_IN_TEAM)
    outstanding = ledger.team_balance(team).outstanding
    if outstanding <= 0:
        raise Conflict(NOTHING_OWED)
    if amount > outstanding:
        raise Conflict(MORE_THAN_OWED)

    credit_amount = Decimal("0.00")
    if credit == Credit.PLAYER:
        credit_amount = min(ledger.player_credit(team.club, player), amount)
    elif credit == Credit.TEAM:
        if team.captain_id != player.pk:
            raise Conflict(ONLY_CAPTAIN_TEAM_CREDIT)
        credit_amount = min(ledger.team_credit(team), amount)
    if credit != Credit.NONE and credit_amount <= 0:
        raise Conflict(NO_CREDIT)
    card_amount = amount - credit_amount

    club_settings = team.club.settings
    merchant_id = ""
    if card_amount > 0:
        if club_settings.payment_mode != PaymentMode.GATEWAY:
            raise Conflict(CASH_ONLY)
        gateway = gateway_for(club_settings.payment_provider)
        merchant_id = gateway.merchant_id_for(team.club)
        if merchant_id is None:
            raise Conflict(CARD_NOT_SET_UP)
        if card_amount < gateway.minimum_amount:
            raise Conflict(_below_minimum(gateway.minimum_amount))

    payment = Payment.objects.create(
        club=team.club,
        team=team,
        player=player,
        amount=amount,
        credit_used=credit,
        credit_amount=credit_amount,
        card_amount=card_amount,
        provider=club_settings.payment_provider,
        merchant_id=merchant_id,
        status=Status.PENDING if card_amount > 0 else Status.COMPLETE,
        completed_at=None if card_amount > 0 else timezone.now(),
    )
    if credit_amount > 0:
        payment.credit_entry = paying(
            team,
            lambda: ledger.spend_credit(
                team=team,
                amount=credit_amount,
                spent_by=player,
                player=player if credit == Credit.PLAYER else None,
                reason=f"Credit towards the league fee, payment {payment.reference}",
            ),
        )
        payment.save(update_fields=["credit_entry"])
    return payment


def checkout_for(payment: Payment):
    """The gateway page for a pending Payment's card part; None once it isn't pending."""
    if payment.status != Status.PENDING or payment.card_amount <= 0:
        return None
    return gateway_for(payment.provider).checkout(payment)


# Gateway notifications


def _log(provider, payment, source_ip, fields, outcome, detail) -> GatewayNotification:
    return GatewayNotification.objects.create(
        provider=provider,
        payment=payment,
        source_ip=source_ip,
        fields=dict(fields),
        outcome=outcome,
        detail=detail[:300],
    )


def _find(reference: str) -> Payment | None:
    try:
        reference = uuid.UUID(reference)
    except (TypeError, ValueError):
        return None
    return Payment.objects.select_related("team", "player").filter(reference=reference).first()


def handle_notification(
    provider: str, fields: list[tuple[str, str]], source_ip: str | None
) -> GatewayNotification:
    """Verifies a gateway's notification and applies it to its Payment, once.

    Every notification is logged with its outcome: accepted, repeat (already applied, or
    nothing to change) or rejected (a check failed; nothing is recorded).
    """
    gateway = gateway_for(provider)
    payment = None
    try:
        if not gateway.source_allowed(source_ip):
            raise NotificationRejected("It didn't come from the gateway's networks.")
        payment = _find(gateway.reference_of(fields))
        if payment is None or payment.provider != provider:
            payment = None
            raise NotificationRejected("No such payment.")
        if payment.card_amount <= 0:
            raise NotificationRejected("This payment has no card part.")
        confirmation = gateway.verify(payment, fields)
    except NotificationRejected as rejected:
        return _log(provider, payment, source_ip, fields, Outcome.REJECTED, str(rejected))

    try:
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(pk=payment.pk)
            outcome, detail = _apply(payment, confirmation)
            return _log(provider, payment, source_ip, fields, outcome, detail)
    except IntegrityError:
        detail = "That gateway payment id is already on another payment."
        return _log(provider, payment, source_ip, fields, Outcome.REJECTED, detail)


def _apply(payment: Payment, confirmation) -> tuple[str, str]:
    if confirmation.status == Status.COMPLETE:
        if payment.card_entry_id is not None:
            return Outcome.REPEAT, "Already recorded."
        gateway_id = confirmation.gateway_payment_id
        payment.card_entry = paying(
            payment.team,
            lambda: ledger.record_payment(
                team=payment.team,
                amount=payment.card_amount,
                method=LedgerEntry.Method.CARD,
                recorded_by=None,
                player=payment.player,
                reason=f"Card payment, {payment.get_provider_display()} {gateway_id}".strip(),
                money_taken=True,
            ),
        )
        payment.status = Status.COMPLETE
        payment.gateway_payment_id = gateway_id or None
        payment.completed_at = timezone.now()
        payment.save(update_fields=["card_entry", "status", "gateway_payment_id", "completed_at"])
        return Outcome.ACCEPTED, "Card payment recorded."
    if confirmation.status in (Status.FAILED, Status.CANCELLED):
        if payment.status != Status.PENDING:
            return Outcome.REPEAT, f"Already {payment.get_status_display().lower()}."
        payment.status = confirmation.status
        payment.save(update_fields=["status"])
        return Outcome.ACCEPTED, f"Payment {confirmation.status}."
    return Outcome.REPEAT, "Still pending at the gateway."


# Cash


@transaction.atomic
def record_cash(
    *, team: Team, admin: User, amount: Decimal, player: User | None = None, reason: str = ""
) -> LedgerEntry:
    """Cash paid to the club, recorded by one of its Admins (FR-22). For one Player of
    the Team, or for the whole Team. No more than the Team still owes."""
    team = _lock(team)
    if team.status != Team.Status.ACTIVE:
        raise Conflict(NOT_ACTIVE)
    outstanding = ledger.team_balance(team).outstanding
    if outstanding <= 0:
        raise Conflict(NOTHING_OWED)
    if amount > outstanding:
        raise Conflict(MORE_THAN_OWED)
    return paying(
        team,
        lambda: ledger.record_payment(
            team=team,
            amount=amount,
            method=LedgerEntry.Method.CASH,
            recorded_by=admin,
            player=player,
            reason=reason.strip() or "Cash paid to the club",
        ),
    )
