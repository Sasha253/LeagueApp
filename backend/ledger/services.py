"""The only way ledger entries are written, and the balances computed from them.

Other chunks call these: the gateway records card payments, Admins record cash, the
cancellation flow returns payments as credit, and so on. Each function checks its own money
rules, so a caller can't post an entry that breaks them.

Credit (FR-52, docs/DECISIONS.md):
- Player credit belongs to the Player and is spent on any Team the Player is in now, at
  the Club that issued it. Only the Player spends it.
- Team credit belongs to the Team; only its Captain spends it, and only on that Team.
- Credit goes back to whoever paid: a Player's own payment becomes Player credit, and a
  payment for the whole Team becomes Team credit.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import DecimalField, Q, QuerySet, Sum, Value
from django.db.models.functions import Coalesce

from accounts.models import User
from clubs.models import Club
from core.exceptions import Conflict
from fixtures.models import Fixture
from teams.models import Team

from .models import LedgerEntry

Kind = LedgerEntry.Kind
Method = LedgerEntry.Method
Subject = LedgerEntry.Subject
Category = LedgerEntry.Category

CENT = Decimal("0.01")
ZERO = Decimal("0.00")

NO_LEAGUE_FEE = "Set the league fee for this Division first."
NOT_ACTIVE = "This Team isn't active."
NOT_ENOUGH_CREDIT = "There isn't enough credit for that."
MORE_THAN_OUTSTANDING = "That is more than the Team still owes."
ALREADY_REVERSED = "This entry has already been reversed."
NO_REVERSING_A_REVERSAL = "A reversal can't be reversed. Record the entry again instead."
CREDIT_ALREADY_SPENT = "This credit has been spent, so it can't be reversed."
CREDIT_RETURNED = "Part of this payment was returned as credit. Reverse that credit first."
MORE_THAN_PAID = "That is more credit than is left of this payment."
REASON_NEEDED = "Give a reason."


# Checks


def _money(amount) -> Decimal:
    """A rand amount above zero, to the cent. Floats are refused: money is never a float."""
    if isinstance(amount, float) or not isinstance(amount, (Decimal, int, str)):
        raise TypeError("Money must be a Decimal, never a float.")
    value = Decimal(amount)
    if value != value.quantize(CENT):
        raise ValueError("Money is to the cent.")
    if value <= 0:
        raise ValueError("The amount must be above zero.")
    return value.quantize(CENT)


def _reason(reason: str) -> str:
    reason = (reason or "").strip()
    if not reason:
        raise ValueError(REASON_NEEDED)
    return reason


def _same_club(club: Club, *records) -> None:
    for record in records:
        if record is not None and record.club_id != club.pk:
            raise ValueError(f"{record} belongs to another Club.")


def _lock_team(team: Team) -> Team:
    return Team.objects.select_for_update().get(pk=team.pk)


def _lock_user(user: User) -> User:
    return User.objects.select_for_update().get(pk=user.pk)


def _is_member(team: Team, player: User) -> bool:
    return team.current_memberships().filter(player=player).exists()


def _active(team: Team) -> None:
    if team.status != Team.Status.ACTIVE:
        raise Conflict(NOT_ACTIVE)


# Balances


def _net(entries: QuerySet, kind: str, **where) -> Decimal:
    """The sum of `kind` entries matching `where`, less the reversals of those entries."""
    matching = Q(**where)
    total = entries.aggregate(
        added=Coalesce(
            Sum("amount", filter=matching & Q(kind=kind)),
            Value(ZERO),
            output_field=DecimalField(),
        ),
        reversed=Coalesce(
            Sum("amount", filter=matching & Q(kind=Kind.REVERSAL, reverses__kind=kind)),
            Value(ZERO),
            output_field=DecimalField(),
        ),
    )
    return (total["added"] - total["reversed"]).quantize(CENT)


@dataclass
class TeamBalance:
    due: Decimal
    paid: Decimal
    outstanding: Decimal
    paid_by_method: dict[str, Decimal] = field(default_factory=dict)
    is_paid: bool = False


def team_balance(team: Team) -> TeamBalance:
    """What the Team owes, has paid (less refunds) and still owes. Overpaid shows below 0.

    `is_paid` (FR-20): an active Team that owes nothing.
    """
    entries = LedgerEntry.objects.filter(team=team)
    due = _net(entries, Kind.CHARGE)
    by_method = {
        method: _net(entries, Kind.PAYMENT, method=method)
        - _net(entries, Kind.REFUND, method=method)
        for method in Method.values
    }
    paid = sum(by_method.values(), ZERO)
    outstanding = due - paid
    return TeamBalance(
        due=due,
        paid=paid,
        outstanding=outstanding,
        paid_by_method=by_method,
        is_paid=team.status == Team.Status.ACTIVE and outstanding <= 0,
    )


def team_balances(teams: QuerySet[Team]) -> dict[int, TeamBalance]:
    """`team_balance` for many Teams in one query, keyed by Team id."""
    sums = {
        "charge": Q(kind=Kind.CHARGE),
        "charge_reversed": Q(kind=Kind.REVERSAL, reverses__kind=Kind.CHARGE),
    }
    for method in Method.values:
        for kind in (Kind.PAYMENT, Kind.REFUND):
            sums[f"{kind}_{method}"] = Q(kind=kind, method=method)
            sums[f"{kind}_{method}_reversed"] = Q(
                kind=Kind.REVERSAL, reverses__kind=kind, method=method
            )
    rows = (
        LedgerEntry.objects.filter(team__in=teams)
        .values("team_id")
        .annotate(
            **{
                name: Coalesce(
                    Sum("amount", filter=where), Value(ZERO), output_field=DecimalField()
                )
                for name, where in sums.items()
            }
        )
    )
    totals = {row["team_id"]: row for row in rows}
    balances = {}
    for team in teams:
        row = totals.get(team.pk, {})

        def net(name, row=row):
            return Decimal(row.get(name, ZERO)) - Decimal(row.get(f"{name}_reversed", ZERO))

        due = net("charge").quantize(CENT)
        by_method = {
            method: (net(f"payment_{method}") - net(f"refund_{method}")).quantize(CENT)
            for method in Method.values
        }
        paid = sum(by_method.values(), ZERO)
        outstanding = due - paid
        balances[team.pk] = TeamBalance(
            due=due,
            paid=paid,
            outstanding=outstanding,
            paid_by_method=by_method,
            is_paid=team.status == Team.Status.ACTIVE and outstanding <= 0,
        )
    return balances


def paid_by_payer(team: Team) -> dict[int | None, Decimal]:
    """What each payer has paid towards the Team, net of refunds and reversals: the same
    sums as `team_balance`'s `paid`, split by Player id (None: paid for the whole Team).
    Payers with nothing left paid are left out."""
    sums = {}
    for kind in (Kind.PAYMENT, Kind.REFUND):
        sums[kind] = Q(kind=kind)
        sums[f"{kind}_reversed"] = Q(kind=Kind.REVERSAL, reverses__kind=kind)
    rows = (
        LedgerEntry.objects.filter(team=team)
        .values("user_id")
        .annotate(
            **{
                name: Coalesce(
                    Sum("amount", filter=where), Value(ZERO), output_field=DecimalField()
                )
                for name, where in sums.items()
            }
        )
    )
    paid = {}
    for row in rows:
        payments = row[Kind.PAYMENT] - row[f"{Kind.PAYMENT}_reversed"]
        refunds = row[Kind.REFUND] - row[f"{Kind.REFUND}_reversed"]
        amount = (payments - refunds).quantize(CENT)
        if amount != 0:
            paid[row["user_id"]] = amount
    return paid


def team_credit(team: Team) -> Decimal:
    """The Team's own credit: issued to it, less what its Captain has spent."""
    entries = LedgerEntry.objects.filter(subject=Subject.TEAM, team=team)
    return _net(entries, Kind.CREDIT) - _net(entries, Kind.PAYMENT, method=Method.CREDIT)


def user_credit(club: Club, user: User, subject: str = Subject.PLAYER) -> Decimal:
    """A Player's (or Booking User's) credit at one Club."""
    entries = LedgerEntry.objects.filter(club=club, subject=subject, user=user)
    return _net(entries, Kind.CREDIT) - _net(entries, Kind.PAYMENT, method=Method.CREDIT)


def player_credit(club: Club, player: User) -> Decimal:
    return user_credit(club, player, Subject.PLAYER)


def account_entries(team: Team) -> QuerySet[LedgerEntry]:
    """The lines on a Team's account: charges, payments, refunds and their reversals."""
    credits = Q(kind=Kind.CREDIT) | Q(kind=Kind.REVERSAL, reverses__kind=Kind.CREDIT)
    return LedgerEntry.objects.filter(team=team).exclude(credits)


def credit_entries(holder_filter: Q) -> QuerySet[LedgerEntry]:
    """The entries that move a credit wallet: credits, spending, and their reversals."""
    moves = Q(kind=Kind.CREDIT) | Q(kind=Kind.PAYMENT, method=Method.CREDIT)
    reversals = Q(kind=Kind.REVERSAL) & (
        Q(reverses__kind=Kind.CREDIT) | Q(reverses__kind=Kind.PAYMENT, method=Method.CREDIT)
    )
    return LedgerEntry.objects.filter(holder_filter & (moves | reversals))


def _credit_left_of(payment: LedgerEntry) -> Decimal:
    """How much of a payment can still be returned as credit."""
    returned = _net(LedgerEntry.objects.all(), Kind.CREDIT, source=payment)
    return payment.amount - returned


# Writing entries


def _subject_of(team: Team | None, user: User | None, subject: str | None) -> str:
    if subject is None:
        subject = Subject.TEAM if user is None else Subject.PLAYER
    if subject == Subject.TEAM and (team is None or user is not None):
        raise ValueError("A Team entry names the Team and no user.")
    if subject == Subject.PLAYER and (user is None or not user.is_player):
        raise ValueError("A Player entry names a Player.")
    if subject == Subject.BOOKING_USER and (user is None or not user.is_booking_user):
        raise ValueError("A Booking User entry names a Booking User.")
    return subject


@transaction.atomic
def charge(
    *,
    club: Club,
    amount,
    category: str,
    reason: str,
    recorded_by: User | None = None,
    team: Team | None = None,
    user: User | None = None,
    subject: str | None = None,
    fixture: Fixture | None = None,
) -> LedgerEntry:
    """Something owed: a Team's league or friendly fee, a Player's fee, a booking."""
    _same_club(club, team, fixture)
    return LedgerEntry.objects.create(
        club=club,
        kind=Kind.CHARGE,
        category=category,
        amount=_money(amount),
        subject=_subject_of(team, user, subject),
        team=team,
        user=user,
        fixture=fixture,
        reason=_reason(reason),
        recorded_by=recorded_by,
    )


def _league_fee_charged(team: Team) -> bool:
    entries = LedgerEntry.objects.filter(team=team, category=Category.LEAGUE, fixture=None)
    return _net(entries, Kind.CHARGE) > 0


@transaction.atomic
def charge_league_fee(team: Team, recorded_by: User | None = None) -> LedgerEntry | None:
    """Charges the Team its Season's league fee, once. None if it is already charged.

    The fee is the Division's own, else the club's (clubs.models.Division). It is fixed
    when charged: a later change to the fee doesn't rewrite what the Team owes.
    """
    team = _lock_team(team)
    if _league_fee_charged(team):
        return None
    fee = team.division.effective_league_fee
    if fee is None:
        raise Conflict(NO_LEAGUE_FEE)
    if fee == 0:
        return None  # A free league: nothing is owed, and an entry is never R 0.
    return charge(
        club=team.club,
        amount=fee,
        category=Category.LEAGUE,
        reason=f"League fee, {team.season.name}",
        recorded_by=recorded_by,
        team=team,
    )


@transaction.atomic
def record_payment(
    *,
    team: Team,
    amount,
    method: str,
    recorded_by: User | None,
    player: User | None = None,
    category: str = Category.LEAGUE,
    reason: str = "",
    fixture: Fixture | None = None,
    money_taken: bool = False,
) -> LedgerEntry:
    """Card or cash paid towards what a Team owes, by one Player or for the whole Team.

    `money_taken`: the gateway has already taken the money (a confirmed card payment), so
    it is recorded even if the Player has left the Team since they started paying.
    """
    if method not in (Method.CARD, Method.CASH):
        raise ValueError("Payments are by card or cash. Credit is spent with spend_credit.")
    team = _lock_team(team)
    if not money_taken:
        _active(team)
    _same_club(team.club, fixture)
    if player is not None and not money_taken and not _is_member(team, player):
        raise Conflict("That Player isn't in this Team.")
    return LedgerEntry.objects.create(
        club=team.club,
        kind=Kind.PAYMENT,
        method=method,
        category=category,
        amount=_money(amount),
        subject=Subject.TEAM if player is None else Subject.PLAYER,
        team=team,
        user=player,
        fixture=fixture,
        reason=(reason or "").strip(),
        recorded_by=recorded_by,
    )


@transaction.atomic
def issue_credit(
    *,
    club: Club,
    amount,
    reason: str,
    recorded_by: User | None,
    team: Team | None = None,
    user: User | None = None,
    subject: str | None = None,
    category: str = Category.LEAGUE,
    fixture: Fixture | None = None,
    source: LedgerEntry | None = None,
) -> LedgerEntry:
    """Credit to a Player's, Booking User's or Team's wallet, with a reason (FR-50)."""
    subject = _subject_of(team, user, subject)
    _same_club(club, team, fixture, source)
    amount = _money(amount)
    # Locks in the same order as reverse(): the payment, then the holder.
    if source is not None:
        source = LedgerEntry.objects.select_for_update().get(pk=source.pk)
        payer = (
            source.subject,
            source.team_id if source.subject == Subject.TEAM else source.user_id,
        )
        holder = (subject, team.pk if subject == Subject.TEAM else user.pk)
        if source.kind != Kind.PAYMENT or payer != holder:
            raise ValueError("Credit from a payment goes back to whoever paid it.")
        # Checked under the lock, so a payment reversed meanwhile isn't also returned.
        if LedgerEntry.objects.filter(reverses=source).exists():
            raise Conflict(ALREADY_REVERSED)
        if amount > _credit_left_of(source):
            raise Conflict(MORE_THAN_PAID)
    if subject == Subject.TEAM:
        _lock_team(team)
    else:
        _lock_user(user)
    return LedgerEntry.objects.create(
        club=club,
        kind=Kind.CREDIT,
        category=category,
        amount=amount,
        subject=subject,
        team=team if subject == Subject.TEAM else None,
        user=None if subject == Subject.TEAM else user,
        fixture=fixture,
        source=source,
        reason=_reason(reason),
        recorded_by=recorded_by,
    )


def return_as_credit(
    payment: LedgerEntry,
    *,
    reason: str,
    recorded_by: User | None,
    amount=None,
    fixture: Fixture | None = None,
) -> LedgerEntry:
    """Returns (part of) a payment as credit to whoever paid it (FR-43, FR-52).

    A Player's own payment becomes that Player's credit; a payment for the whole Team
    becomes Team credit. No more than the payment can be returned, in total. A reversed
    payment is refused (issue_credit checks it under the payment's lock).
    """
    if payment.kind != Kind.PAYMENT:
        raise ValueError("Only a payment can be returned as credit.")
    return issue_credit(
        club=payment.club,
        amount=payment.amount if amount is None else amount,
        reason=reason,
        recorded_by=recorded_by,
        team=payment.team if payment.subject == Subject.TEAM else None,
        user=payment.user,
        subject=payment.subject,
        category=payment.category,
        fixture=fixture or payment.fixture,
        source=payment,
    )


@transaction.atomic
def spend_credit(
    *,
    team: Team,
    amount,
    spent_by: User,
    player: User | None = None,
    reason: str = "",
    fixture: Fixture | None = None,
) -> LedgerEntry:
    """Pays towards what a Team owes from credit: a payment with method credit.

    With `player`, it is that Player's credit, spent by the Player on a Team they are in.
    Without, it is the Team's credit, spent by its Captain. Never more than the credit held
    or than the Team still owes.
    """
    amount = _money(amount)
    team = _lock_team(team)
    _active(team)
    _same_club(team.club, fixture)
    if player is None:
        if spent_by is None or team.captain_id != spent_by.pk:
            raise Conflict("Only the Team's Captain can spend its credit.")
        held = team_credit(team)
    else:
        if spent_by is None or spent_by.pk != player.pk:
            raise Conflict("Only the Player can spend their credit.")
        if not _is_member(team, player):
            raise Conflict("That Player isn't in this Team.")
        _lock_user(player)
        held = player_credit(team.club, player)
    if amount > held:
        raise Conflict(NOT_ENOUGH_CREDIT)
    if amount > team_balance(team).outstanding:
        raise Conflict(MORE_THAN_OUTSTANDING)
    return LedgerEntry.objects.create(
        club=team.club,
        kind=Kind.PAYMENT,
        method=Method.CREDIT,
        category=Category.LEAGUE,
        amount=amount,
        subject=Subject.TEAM if player is None else Subject.PLAYER,
        team=team,
        user=player,
        fixture=fixture,
        reason=(reason or "").strip(),
        recorded_by=spent_by,
    )


def _wallet_credit(entry: LedgerEntry) -> Decimal:
    if entry.subject == Subject.TEAM:
        return team_credit(entry.team)
    return user_credit(entry.club, entry.user, entry.subject)


@transaction.atomic
def reverse(entry: LedgerEntry, *, reason: str, recorded_by: User | None) -> LedgerEntry:
    """Undoes an entry with a reversal entry. The entry itself stays as it is (FR-50)."""
    reason = _reason(reason)
    entry = LedgerEntry.objects.select_for_update().get(pk=entry.pk)
    if entry.kind == Kind.REVERSAL:
        raise Conflict(NO_REVERSING_A_REVERSAL)
    if LedgerEntry.objects.filter(reverses=entry).exists():
        raise Conflict(ALREADY_REVERSED)
    if entry.team_id is not None:
        _lock_team(entry.team)
    if entry.user_id is not None:
        _lock_user(entry.user)
    if entry.kind == Kind.CREDIT and entry.amount > _wallet_credit(entry):
        raise Conflict(CREDIT_ALREADY_SPENT)
    if entry.kind == Kind.PAYMENT and _credit_left_of(entry) < entry.amount:
        raise Conflict(CREDIT_RETURNED)
    try:
        with transaction.atomic():
            return LedgerEntry.objects.create(
                club=entry.club,
                kind=Kind.REVERSAL,
                method=entry.method,
                category=entry.category,
                amount=entry.amount,
                subject=entry.subject,
                team=entry.team,
                user=entry.user,
                fixture=entry.fixture,
                source=entry.source,
                reverses=entry,
                reason=reason,
                recorded_by=recorded_by,
            )
    except IntegrityError as error:
        raise Conflict(ALREADY_REVERSED) from error


# Friendlies (FR-24, FR-49)


@transaction.atomic
def record_friendly_payment(
    *,
    fixture: Fixture,
    player: User,
    amount,
    method: str,
    recorded_by: User | None,
    reason: str = "",
) -> LedgerEntry:
    """A Player's payment towards a friendly's fee: its own `friendly` category, for the
    Fixture, on no Team's account, so no Team's league balance or Barcode changes.
    Who may pay and how much is checked by fixtures/friendlies.py."""
    if method not in (Method.CARD, Method.CASH):
        raise ValueError("Friendly payments are by card or cash.")
    _lock_user(player)
    return LedgerEntry.objects.create(
        club=fixture.club,
        kind=Kind.PAYMENT,
        method=method,
        category=Category.FRIENDLY,
        amount=_money(amount),
        subject=_subject_of(None, player, Subject.PLAYER),
        team=None,
        user=player,
        fixture=fixture,
        reason=(reason or "").strip(),
        recorded_by=recorded_by,
    )


def friendly_payments(fixture: Fixture) -> QuerySet[LedgerEntry]:
    """The friendly fee payments for one match, and their reversals, oldest first."""
    payments = Q(kind=Kind.PAYMENT) | Q(kind=Kind.REVERSAL, reverses__kind=Kind.PAYMENT)
    return LedgerEntry.objects.filter(
        payments, fixture=fixture, category=Category.FRIENDLY, team__isnull=True
    ).order_by("created_at", "pk")


def friendly_paid(fixture: Fixture) -> Decimal:
    """What has been paid towards a friendly's fee, less reversals and less what was
    returned as credit (a cancelled friendly)."""
    entries = LedgerEntry.objects.filter(
        fixture=fixture, category=Category.FRIENDLY, team__isnull=True
    )
    paid = _net(entries, Kind.PAYMENT)
    returned = _net(entries.filter(source__isnull=False), Kind.CREDIT)
    return paid - returned


def fixture_payments(fixture: Fixture) -> QuerySet[LedgerEntry]:
    """The payments recorded for one match (card, cash or credit), oldest first."""
    return LedgerEntry.objects.filter(fixture=fixture, kind=Kind.PAYMENT).order_by(
        "created_at", "pk"
    )


@transaction.atomic
def return_fixture_payments(
    fixture: Fixture, *, reason: str, recorded_by: User | None
) -> list[LedgerEntry]:
    """A paid match is cancelled: each payment for it becomes credit to whoever paid
    (FR-43, FR-52). A Player's own payment becomes Player credit, a payment for the whole
    Team becomes Team credit. Only what is left of each payment is returned, and a reversed
    payment is skipped, so running it again adds nothing. No card refund is issued.
    """
    reason = _reason(reason)
    credits = []
    for payment in fixture_payments(fixture):
        payment = LedgerEntry.objects.select_for_update().get(pk=payment.pk)
        if LedgerEntry.objects.filter(reverses=payment).exists():
            continue
        left = _credit_left_of(payment)
        if left <= 0:
            continue
        credits.append(
            return_as_credit(
                payment, reason=reason, recorded_by=recorded_by, amount=left, fixture=fixture
            )
        )
    return credits


def fixture_credit_returned(fixture: Fixture) -> tuple[Decimal, int]:
    """The credit returned from this match's payments, less any reversed, and how many
    credit entries still stand."""
    entries = LedgerEntry.objects.filter(fixture=fixture, source__isnull=False)
    total = _net(entries, Kind.CREDIT)
    standing = entries.filter(kind=Kind.CREDIT, reversed_by__isnull=True).count()
    return total, standing
