"""The ledger's money rules: charges, payments, credit (FR-43, FR-52) and reversals (FR-50)."""

from decimal import Decimal

import pytest

from core.exceptions import Conflict
from ledger import services
from ledger.models import LedgerEntry
from teams.models import Team

D = Decimal
Kind = LedgerEntry.Kind
Method = LedgerEntry.Method
Subject = LedgerEntry.Subject


def league_fee(team):
    return services.charge_league_fee(team)


def pay(team, amount, by, player=None, method=Method.CASH):
    return services.record_payment(
        team=team, amount=D(amount), method=method, recorded_by=by, player=player
    )


# Amounts


@pytest.mark.django_db
def test_money_is_never_a_float(club_a, lions):
    with pytest.raises(TypeError):
        services.charge(club=club_a, amount=350.0, category="league", reason="Fee", team=lions)


@pytest.mark.django_db
@pytest.mark.parametrize("amount", ["0", "-10", "10.005"])
def test_amounts_are_above_zero_and_to_the_cent(club_a, lions, amount):
    with pytest.raises(ValueError):
        services.charge(club=club_a, amount=D(amount), category="league", reason="Fee", team=lions)


@pytest.mark.django_db
def test_the_database_refuses_an_amount_of_zero(club_a, lions):
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        LedgerEntry.objects.create(
            club=club_a, kind="charge", category="league", amount=D("0"), subject="team", team=lions
        )


# The league fee


@pytest.mark.django_db
def test_league_fee_is_charged_once_from_the_clubs_fee(lions):
    first = league_fee(lions)
    again = league_fee(lions)

    assert first.amount == D("350.00")
    assert first.reason == "League fee, Spring"
    assert again is None
    assert services.team_balance(lions).due == D("350.00")


@pytest.mark.django_db
def test_a_divisions_own_fee_overrides_the_clubs(lions, division):
    division.league_fee = D("420")
    division.save()

    assert league_fee(lions).amount == D("420.00")


@pytest.mark.django_db
def test_no_league_fee_means_no_charge(lions, club_a):
    club_a.settings.league_fee = None
    club_a.settings.save()

    with pytest.raises(Conflict):
        league_fee(lions)


@pytest.mark.django_db
def test_a_reversed_league_fee_can_be_charged_again(lions, cashier):
    first = league_fee(lions)
    services.reverse(first, reason="Wrong fee", recorded_by=cashier)

    assert services.team_balance(lions).due == D("0.00")
    assert league_fee(lions) is not None


@pytest.mark.django_db
def test_admin_confirming_a_team_charges_its_league_fee(make_team, people, cashier):
    team = make_team("Old Boys", people["lerato"], status=Team.Status.REQUESTED)
    from teams import rules

    rules.confirm_team(team, cashier)

    charge = LedgerEntry.objects.get(team=team)
    assert (charge.kind, charge.amount, charge.recorded_by) == ("charge", D("350.00"), cashier)


@pytest.mark.django_db
def test_a_team_cannot_be_confirmed_without_a_league_fee(make_team, people, cashier, club_a):
    team = make_team("Old Boys", people["lerato"], status=Team.Status.REQUESTED)
    club_a.settings.league_fee = None
    club_a.settings.save()
    from teams import rules

    with pytest.raises(Conflict):
        rules.confirm_team(team, cashier)

    team.refresh_from_db()
    assert team.status == Team.Status.REQUESTED


# Payments and the balance


@pytest.mark.django_db
def test_balance_is_due_less_paid_split_by_method(lions, people, cashier):
    league_fee(lions)
    pay(lions, "100", cashier, player=people["sipho"], method=Method.CARD)
    pay(lions, "50", cashier)

    balance = services.team_balance(lions)

    assert (balance.due, balance.paid, balance.outstanding) == (D("350"), D("150"), D("200"))
    assert balance.paid_by_method == {"card": D("100"), "cash": D("50"), "credit": D("0")}


@pytest.mark.django_db
def test_a_player_payment_names_the_player_and_the_team(lions, people, cashier):
    entry = pay(lions, "100", cashier, player=people["sipho"])

    assert (entry.subject, entry.user, entry.team) == ("player", people["sipho"], lions)


@pytest.mark.django_db
def test_only_a_player_in_the_team_pays_for_it(lions, people, cashier):
    with pytest.raises(Conflict):
        pay(lions, "100", cashier, player=people["lerato"])


@pytest.mark.django_db
def test_payments_are_card_or_cash(lions, cashier):
    with pytest.raises(ValueError):
        pay(lions, "100", cashier, method=Method.CREDIT)


@pytest.mark.django_db
def test_no_payment_for_a_team_that_isnt_active(make_team, people, cashier):
    team = make_team("Old Boys", people["lerato"], status=Team.Status.REQUESTED)

    with pytest.raises(Conflict):
        pay(team, "100", cashier)


# Credit goes back to whoever paid (FR-52)


@pytest.mark.django_db
def test_a_players_payment_returns_as_player_credit(lions, people, cashier, club_a):
    payment = pay(lions, "100", cashier, player=people["sipho"])

    credit = services.return_as_credit(payment, reason="Match cancelled", recorded_by=None)

    assert (credit.subject, credit.user, credit.team, credit.source) == (
        "player",
        people["sipho"],
        None,
        payment,
    )
    assert services.player_credit(club_a, people["sipho"]) == D("100")
    assert services.team_credit(lions) == D("0")


@pytest.mark.django_db
def test_a_whole_team_payment_returns_as_team_credit(lions, people, cashier, club_a):
    payment = pay(lions, "350", cashier)

    services.return_as_credit(payment, amount=D("50"), reason="Match cancelled", recorded_by=None)

    assert services.team_credit(lions) == D("50")
    assert services.player_credit(club_a, people["thandi"]) == D("0")


@pytest.mark.django_db
def test_no_more_credit_than_the_payment(lions, people, cashier):
    payment = pay(lions, "100", cashier, player=people["sipho"])
    services.return_as_credit(payment, amount=D("60"), reason="Cancelled", recorded_by=None)

    with pytest.raises(Conflict):
        services.return_as_credit(payment, amount=D("41"), reason="Cancelled", recorded_by=None)
    services.return_as_credit(payment, amount=D("40"), reason="Cancelled", recorded_by=None)


@pytest.mark.django_db
def test_credit_from_a_payment_cannot_go_to_someone_else(lions, people, cashier, club_a):
    payment = pay(lions, "100", cashier, player=people["sipho"])

    with pytest.raises(ValueError):
        services.issue_credit(
            club=club_a,
            amount=D("100"),
            reason="Cancelled",
            recorded_by=None,
            user=people["thandi"],
            source=payment,
        )


@pytest.mark.django_db
def test_credit_needs_a_reason(lions, club_a, people):
    with pytest.raises(ValueError):
        services.issue_credit(
            club=club_a, amount=D("10"), reason="  ", recorded_by=None, user=people["sipho"]
        )


# Spending credit


def give_player_credit(club, player, amount="100"):
    return services.issue_credit(
        club=club, amount=D(amount), reason="Goodwill", recorded_by=None, user=player
    )


@pytest.mark.django_db
def test_a_player_spends_their_credit_on_a_team_they_are_in(lions, people, club_a):
    league_fee(lions)
    give_player_credit(club_a, people["sipho"])

    entry = services.spend_credit(
        team=lions, amount=D("80"), spent_by=people["sipho"], player=people["sipho"]
    )

    assert (entry.kind, entry.method, entry.subject) == ("payment", "credit", "player")
    assert services.player_credit(club_a, people["sipho"]) == D("20")
    assert services.team_balance(lions).paid_by_method["credit"] == D("80")


@pytest.mark.django_db
def test_player_credit_moves_with_the_player_between_teams(
    make_team, people, club_a, lions, friday_division
):
    other = make_team("Night Owls", people["lerato"], people["sipho"], division=friday_division)
    league_fee(other)
    give_player_credit(club_a, people["sipho"])

    services.spend_credit(
        team=other, amount=D("100"), spent_by=people["sipho"], player=people["sipho"]
    )

    assert services.player_credit(club_a, people["sipho"]) == D("0")


@pytest.mark.django_db
def test_player_credit_is_not_spent_on_a_team_they_are_not_in(lions, people, club_a):
    league_fee(lions)
    give_player_credit(club_a, people["lerato"])

    with pytest.raises(Conflict):
        services.spend_credit(
            team=lions, amount=D("10"), spent_by=people["lerato"], player=people["lerato"]
        )


@pytest.mark.django_db
def test_only_the_player_spends_their_credit(lions, people, club_a):
    league_fee(lions)
    give_player_credit(club_a, people["sipho"])

    with pytest.raises(Conflict):
        services.spend_credit(
            team=lions, amount=D("10"), spent_by=people["thandi"], player=people["sipho"]
        )


@pytest.mark.django_db
def test_player_credit_is_spent_only_at_its_club(people, club_a, club_b, lions):
    """Credit issued at Club B can't pay a Club A Team (docs/DECISIONS.md, provisional)."""
    league_fee(lions)
    give_player_credit(club_b, people["sipho"])

    with pytest.raises(Conflict):
        services.spend_credit(
            team=lions, amount=D("10"), spent_by=people["sipho"], player=people["sipho"]
        )


@pytest.mark.django_db
def test_no_spending_more_credit_than_held(lions, people, club_a):
    league_fee(lions)
    give_player_credit(club_a, people["sipho"], "50")

    with pytest.raises(Conflict):
        services.spend_credit(
            team=lions, amount=D("50.01"), spent_by=people["sipho"], player=people["sipho"]
        )


@pytest.mark.django_db
def test_no_spending_more_credit_than_the_team_owes(lions, people, club_a):
    league_fee(lions)
    give_player_credit(club_a, people["sipho"], "500")

    with pytest.raises(Conflict):
        services.spend_credit(
            team=lions, amount=D("351"), spent_by=people["sipho"], player=people["sipho"]
        )


@pytest.mark.django_db
def test_only_the_captain_spends_team_credit(lions, people, club_a):
    league_fee(lions)
    services.issue_credit(
        club=club_a, amount=D("100"), reason="Goodwill", recorded_by=None, team=lions
    )

    with pytest.raises(Conflict):
        services.spend_credit(team=lions, amount=D("10"), spent_by=people["sipho"])
    services.spend_credit(team=lions, amount=D("100"), spent_by=people["thandi"])

    assert services.team_credit(lions) == D("0")
    assert services.team_balance(lions).outstanding == D("250")


# Reversals (FR-50)


@pytest.mark.django_db
def test_a_reversal_undoes_an_entry_and_leaves_it_as_it_was(lions, cashier):
    league_fee(lions)
    payment = pay(lions, "100", cashier)

    reversal = services.reverse(payment, reason="Recorded twice", recorded_by=cashier)

    assert (reversal.kind, reversal.reverses, reversal.amount) == ("reversal", payment, D("100"))
    assert LedgerEntry.objects.get(pk=payment.pk).amount == D("100")
    assert services.team_balance(lions).paid == D("0")


@pytest.mark.django_db
def test_an_entry_is_reversed_once(lions, cashier):
    payment = pay(lions, "100", cashier)
    services.reverse(payment, reason="Mistake", recorded_by=cashier)

    with pytest.raises(Conflict):
        services.reverse(payment, reason="Mistake", recorded_by=cashier)


@pytest.mark.django_db
def test_a_reversal_is_not_reversed(lions, cashier):
    payment = pay(lions, "100", cashier)
    reversal = services.reverse(payment, reason="Mistake", recorded_by=cashier)

    with pytest.raises(Conflict):
        services.reverse(reversal, reason="Mistake", recorded_by=cashier)


@pytest.mark.django_db
def test_a_reversal_needs_a_reason(lions, cashier):
    payment = pay(lions, "100", cashier)

    with pytest.raises(ValueError):
        services.reverse(payment, reason="", recorded_by=cashier)


@pytest.mark.django_db
def test_spent_credit_cannot_be_reversed(lions, people, club_a, cashier):
    league_fee(lions)
    credit = give_player_credit(club_a, people["sipho"])
    services.spend_credit(
        team=lions, amount=D("30"), spent_by=people["sipho"], player=people["sipho"]
    )

    with pytest.raises(Conflict):
        services.reverse(credit, reason="Mistake", recorded_by=cashier)


@pytest.mark.django_db
def test_reversing_spent_credit_gives_the_credit_back(lions, people, club_a, cashier):
    league_fee(lions)
    give_player_credit(club_a, people["sipho"])
    spent = services.spend_credit(
        team=lions, amount=D("30"), spent_by=people["sipho"], player=people["sipho"]
    )

    services.reverse(spent, reason="Paid by card instead", recorded_by=cashier)

    assert services.player_credit(club_a, people["sipho"]) == D("100")
    assert services.team_balance(lions).outstanding == D("350")


@pytest.mark.django_db
def test_a_payment_returned_as_credit_is_not_reversed_first(lions, people, cashier):
    payment = pay(lions, "100", cashier, player=people["sipho"])
    credit = services.return_as_credit(payment, reason="Cancelled", recorded_by=None)

    with pytest.raises(Conflict):
        services.reverse(payment, reason="Mistake", recorded_by=cashier)
    services.reverse(credit, reason="Mistake", recorded_by=cashier)
    services.reverse(payment, reason="Mistake", recorded_by=cashier)


@pytest.mark.django_db
def test_a_reversed_payment_is_not_returned_as_credit(lions, people, cashier):
    payment = pay(lions, "100", cashier, player=people["sipho"])
    services.reverse(payment, reason="Mistake", recorded_by=cashier)

    with pytest.raises(Conflict):
        services.return_as_credit(payment, reason="Cancelled", recorded_by=None)


# Club isolation


@pytest.mark.django_db
def test_entries_never_mix_clubs(lions, club_b):
    with pytest.raises(ValueError):
        services.charge(club=club_b, amount=D("10"), category="league", reason="Fee", team=lions)
