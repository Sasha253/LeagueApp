"""Paying what a Team owes: card through PayFast, credit first, cash by an Admin (FR-19 to
FR-22), and the ITN checks (NFR Security)."""

from decimal import Decimal as D
from urllib.parse import urlencode

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import ClubRole
from clubs.models import PaymentMode
from core.exceptions import Conflict
from ledger import services as ledger
from ledger.models import LedgerEntry
from payments import services
from payments.models import GatewayNotification, Payment

from .conftest import PAYFAST_IP, itn_fields

NOTIFY = reverse("api-v1:payfast-notify")
MY_PAYMENTS = reverse("api-v1:my-payments")


def url(name, team):
    return reverse(f"api-v1:{name}", kwargs={"team_id": team.pk})


def start(team, player, amount, credit="none"):
    return services.start_payment(team=team, player=player, amount=D(amount), credit=credit)


def post_itn(api, fields, ip=PAYFAST_IP, **extra):
    """Posts the ITN form-encoded, in order, as PayFast does."""
    return api.generic(
        "POST",
        NOTIFY,
        urlencode(fields),
        content_type="application/x-www-form-urlencoded",
        REMOTE_ADDR=ip,
        **extra,
    )


def card_entries(team):
    return LedgerEntry.objects.filter(team=team, kind="payment", method="card")


# Payment options


@pytest.mark.django_db
def test_a_player_in_the_team_sees_what_to_pay(owing, people, signed_in):
    answer = signed_in(people["sipho"]).get(url("team-payment-options", owing))

    assert answer.status_code == 200
    assert answer.json() == {
        "team": {"id": owing.pk, "name": "Red Lions"},
        "due": "350.00",
        "outstanding": "350.00",
        "is_paid": False,
        "card_enabled": True,
        "minimum_card_amount": "5.00",
        "suggested_amount": "175.00",
        "my_credit": "0.00",
        "team_credit": None,
    }


@pytest.mark.django_db
def test_only_the_captain_sees_the_team_credit(owing, people, signed_in, cashier, club_a):
    ledger.issue_credit(
        club=club_a, amount=D("40"), reason="Goodwill", recorded_by=cashier, team=owing
    )

    answer = signed_in(people["thandi"]).get(url("team-payment-options", owing))

    assert answer.json()["team_credit"] == "40.00"


@pytest.mark.django_db
def test_a_cash_only_club_shows_no_card(owing, people, signed_in, club_a):
    club_a.settings.payment_mode = PaymentMode.CASH_ONLY
    club_a.settings.save()

    data = signed_in(people["sipho"]).get(url("team-payment-options", owing)).json()

    assert data["card_enabled"] is False
    assert data["minimum_card_amount"] is None


@pytest.mark.django_db
def test_someone_not_in_the_team_gets_404(owing, people, signed_in):
    client = signed_in(people["lerato"])

    assert client.get(url("team-payment-options", owing)).status_code == 404
    assert client.post(url("team-payments", owing), {"amount": "50"}).status_code == 404


# Starting a payment


@pytest.mark.django_db
def test_a_player_starts_a_card_payment_for_their_contribution(owing, people, signed_in):
    answer = signed_in(people["sipho"]).post(url("team-payments", owing), {"amount": "120.50"})

    assert answer.status_code == 201
    data = answer.json()
    assert data["amount"] == "120.50"
    assert data["card_amount"] == "120.50"
    assert data["credit_amount"] == "0.00"
    assert data["status"] == "pending"
    assert data["checkout"]["action"] == "https://sandbox.payfast.co.za/eng/process"
    fields = {f["name"]: f["value"] for f in data["checkout"]["form_fields"]}
    assert fields["amount"] == "120.50"
    assert fields["m_payment_id"] == data["reference"]
    # Nothing is recorded until PayFast confirms it.
    assert not card_entries(owing).exists()
    assert ledger.team_balance(owing).outstanding == D("350.00")


@pytest.mark.django_db
def test_the_amount_is_checked_by_the_backend(owing, people, signed_in):
    client = signed_in(people["sipho"])

    assert client.post(url("team-payments", owing), {"amount": "0"}).status_code == 400
    assert client.post(url("team-payments", owing), {"amount": "1.005"}).status_code == 400
    answer = client.post(url("team-payments", owing), {"amount": "350.01"})
    assert answer.status_code == 409
    assert answer.json()["detail"] == "That is more than the Team still owes."


@pytest.mark.django_db
def test_a_card_part_under_the_gateway_minimum_is_refused(owing, people):
    with pytest.raises(Conflict, match="at least R 5 by card"):
        start(owing, people["sipho"], "4.99")


@pytest.mark.django_db
def test_nothing_to_pay_when_the_team_owes_nothing(lions, people):
    with pytest.raises(Conflict, match="nothing left to pay"):
        start(lions, people["sipho"], "10")


@pytest.mark.django_db
def test_a_cash_only_club_takes_no_card(owing, people, club_a):
    club_a.settings.payment_mode = PaymentMode.CASH_ONLY
    club_a.settings.save()

    with pytest.raises(Conflict, match="cash only"):
        start(owing, people["sipho"], "50")


@pytest.mark.django_db
def test_no_card_payment_until_payfast_is_set_up(owing, people, settings):
    settings.PAYFAST_MERCHANT_KEY = ""

    with pytest.raises(Conflict, match="aren't set up"):
        start(owing, people["sipho"], "50")


@pytest.mark.django_db
def test_an_inactive_team_takes_no_payment(owing, people):
    owing.status = "requested"
    owing.save()

    with pytest.raises(Conflict, match="isn't active"):
        start(owing, people["sipho"], "50")


# Credit first


@pytest.fixture
def sipho_credit(owing, people, club_a, cashier):
    ledger.issue_credit(
        club=club_a,
        amount=D("80"),
        reason="Match cancelled",
        recorded_by=cashier,
        user=people["sipho"],
    )


@pytest.mark.django_db
def test_player_credit_is_spent_first_and_the_rest_goes_to_card(owing, people, sipho_credit):
    payment = start(owing, people["sipho"], "100", credit="player")

    assert payment.credit_amount == D("80.00")
    assert payment.card_amount == D("20.00")
    assert payment.status == Payment.Status.PENDING
    assert payment.credit_entry.method == "credit"
    assert payment.credit_entry.user == people["sipho"]
    assert ledger.player_credit(owing.club, people["sipho"]) == D("0.00")
    assert ledger.team_balance(owing).outstanding == D("270.00")


@pytest.mark.django_db
def test_credit_covering_it_all_completes_with_no_card(owing, people, sipho_credit, signed_in):
    answer = signed_in(people["sipho"]).post(
        url("team-payments", owing), {"amount": "50", "credit": "player"}
    )

    data = answer.json()
    assert data["status"] == "complete"
    assert data["card_amount"] == "0.00"
    assert data["checkout"] is None
    assert ledger.player_credit(owing.club, people["sipho"]) == D("30.00")


@pytest.mark.django_db
def test_credit_works_in_a_cash_only_club(owing, people, sipho_credit, club_a):
    club_a.settings.payment_mode = PaymentMode.CASH_ONLY
    club_a.settings.save()

    assert start(owing, people["sipho"], "50", credit="player").status == "complete"


@pytest.mark.django_db
def test_asking_for_credit_without_any_is_refused(owing, people):
    with pytest.raises(Conflict, match="no credit"):
        start(owing, people["sipho"], "50", credit="player")


@pytest.mark.django_db
def test_only_the_captain_spends_team_credit(owing, people, club_a, cashier):
    ledger.issue_credit(
        club=club_a, amount=D("60"), reason="Goodwill", recorded_by=cashier, team=owing
    )

    with pytest.raises(Conflict, match="Only the Team's Captain"):
        start(owing, people["sipho"], "100", credit="team")
    payment = start(owing, people["thandi"], "100", credit="team")

    assert payment.credit_amount == D("60.00")
    assert payment.credit_entry.subject == "team"
    assert ledger.team_credit(owing) == D("0.00")


# The ITN


@pytest.mark.django_db
def test_a_valid_itn_records_the_card_payment_once(api, owing, people, payfast_server):
    payment = start(owing, people["sipho"], "100")

    answer = post_itn(api, itn_fields(payment))

    assert answer.status_code == 200
    payment.refresh_from_db()
    assert payment.status == "complete"
    assert payment.gateway_payment_id == "1089250"
    assert payment.completed_at is not None
    entry = payment.card_entry
    assert (entry.kind, entry.method, entry.amount) == ("payment", "card", D("100.00"))
    assert entry.user == people["sipho"]
    assert entry.team == owing
    assert entry.recorded_by is None
    assert ledger.team_balance(owing).outstanding == D("250.00")
    # Server-side validation posted the ITN back without the signature.
    [posted] = payfast_server.posted
    assert posted.startswith(f"m_payment_id={payment.reference}&")
    assert "signature=" not in posted
    assert GatewayNotification.objects.get().outcome == "accepted"


@pytest.mark.django_db
def test_a_repeated_itn_records_nothing_more(api, owing, people):
    payment = start(owing, people["sipho"], "100")
    fields = itn_fields(payment)

    assert post_itn(api, fields).status_code == 200
    assert post_itn(api, fields).status_code == 200

    assert card_entries(owing).count() == 1
    assert [n.outcome for n in GatewayNotification.objects.order_by("pk")] == [
        "accepted",
        "repeat",
    ]


@pytest.mark.django_db
def test_paying_the_rest_marks_the_team_paid(api, owing, people, paid_signals):
    first = start(owing, people["sipho"], "150")
    post_itn(api, itn_fields(first, pf_payment_id="1"))
    assert paid_signals == []
    second = start(owing, people["thandi"], "200")

    post_itn(api, itn_fields(second, pf_payment_id="2"))

    assert paid_signals == ["Red Lions"]
    balance = ledger.team_balance(owing)
    assert (balance.outstanding, balance.is_paid) == (D("0.00"), True)


@pytest.mark.django_db
def test_two_payments_started_together_can_overpay_and_both_are_recorded(api, owing, people):
    first = start(owing, people["sipho"], "300")
    second = start(owing, people["thandi"], "300")

    post_itn(api, itn_fields(first, pf_payment_id="1"))
    post_itn(api, itn_fields(second, pf_payment_id="2"))

    # The money was taken, so both are recorded; the Team shows it overpaid.
    assert ledger.team_balance(owing).outstanding == D("-250.00")


@pytest.mark.django_db
def test_a_card_payment_is_recorded_even_if_the_player_left_the_team(api, owing, people):
    payment = start(owing, people["sipho"], "100")
    owing.current_memberships().filter(player=people["sipho"]).update(left_at=timezone.now())

    assert post_itn(api, itn_fields(payment)).status_code == 200

    assert card_entries(owing).get().user == people["sipho"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("case", "detail"),
    [
        ("source", "networks"),
        ("signature", "signature"),
        ("passphrase", "signature"),
        ("merchant", "another merchant"),
        ("amount", "amount"),
        ("server", "didn't confirm"),
        ("reference", "No such payment"),
        ("status", "Unknown payment status"),
    ],
)
def test_an_itn_failing_any_check_records_nothing(api, owing, people, payfast_server, case, detail):
    payment = start(owing, people["sipho"], "100")
    fields = itn_fields(payment)
    ip = PAYFAST_IP
    if case == "source":
        ip = "8.8.8.8"
    elif case == "signature":
        fields = [(n, "999.00" if n == "amount_gross" else v) for n, v in fields]
    elif case == "passphrase":
        fields = itn_fields(payment, passphrase="guessed")
    elif case == "merchant":
        fields = itn_fields(payment, merchant_id="10000999")
    elif case == "amount":
        fields = itn_fields(payment, amount="1.00")
    elif case == "server":
        payfast_server.valid = False
    elif case == "reference":
        fields = itn_fields(payment, m_payment_id="not-ours")
    elif case == "status":
        fields = itn_fields(payment, status="MAYBE")

    answer = post_itn(api, fields, ip=ip)

    assert answer.status_code == 400
    payment.refresh_from_db()
    assert payment.status == "pending"
    assert not card_entries(owing).exists()
    logged = GatewayNotification.objects.get()
    assert logged.outcome == "rejected"
    assert detail in logged.detail
    assert logged.source_ip == ip


@pytest.mark.django_db
def test_the_itn_source_is_read_through_trusted_proxies(api, owing, people, settings):
    settings.PAYFAST_TRUSTED_PROXIES = 1
    payment = start(owing, people["sipho"], "100")

    spoofed = post_itn(
        api, itn_fields(payment), ip="10.0.0.1", HTTP_X_FORWARDED_FOR=f"{PAYFAST_IP}, 8.8.8.8"
    )
    real = post_itn(
        api, itn_fields(payment), ip="10.0.0.1", HTTP_X_FORWARDED_FOR=f"8.8.8.8, {PAYFAST_IP}"
    )

    assert (spoofed.status_code, real.status_code) == (400, 200)


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["FAILED", "CANCELLED"])
def test_a_failed_or_cancelled_itn_marks_the_payment(api, owing, people, status):
    payment = start(owing, people["sipho"], "100")

    assert post_itn(api, itn_fields(payment, status=status)).status_code == 200

    payment.refresh_from_db()
    assert payment.status == status.lower()
    assert not card_entries(owing).exists()


@pytest.mark.django_db
def test_a_complete_payment_never_goes_back_to_failed(api, owing, people):
    payment = start(owing, people["sipho"], "100")
    post_itn(api, itn_fields(payment))

    post_itn(api, itn_fields(payment, status="FAILED"))

    payment.refresh_from_db()
    assert payment.status == "complete"
    assert GatewayNotification.objects.order_by("pk").last().outcome == "repeat"


@pytest.mark.django_db
def test_a_pending_itn_changes_nothing(api, owing, people):
    payment = start(owing, people["sipho"], "100")

    assert post_itn(api, itn_fields(payment, status="PENDING")).status_code == 200

    payment.refresh_from_db()
    assert payment.status == "pending"


@pytest.mark.django_db
def test_an_itn_after_the_player_cancelled_is_still_recorded(api, owing, people):
    """PayFast took the money, so it is recorded whatever we thought before."""
    payment = start(owing, people["sipho"], "100")
    post_itn(api, itn_fields(payment, status="CANCELLED"))

    post_itn(api, itn_fields(payment))

    payment.refresh_from_db()
    assert payment.status == "complete"
    assert card_entries(owing).count() == 1


@pytest.mark.django_db
def test_an_itn_for_a_credit_only_payment_is_refused(api, owing, people, sipho_credit):
    payment = start(owing, people["sipho"], "50", credit="player")

    assert post_itn(api, itn_fields(payment, amount="50.00")).status_code == 400


@pytest.mark.django_db
def test_one_gateway_payment_id_is_never_recorded_twice(api, owing, people):
    first = start(owing, people["sipho"], "100")
    second = start(owing, people["thandi"], "100")
    post_itn(api, itn_fields(first, pf_payment_id="777"))

    answer = post_itn(api, itn_fields(second, pf_payment_id="777"))

    assert answer.status_code == 400
    assert card_entries(owing).count() == 1
    second.refresh_from_db()
    assert second.status == "pending"


@pytest.mark.django_db
def test_the_webhook_needs_no_login_and_takes_no_json(api, owing, people):
    payment = start(owing, people["sipho"], "100")

    answer = api.post(NOTIFY, dict(itn_fields(payment)), format="json", REMOTE_ADDR=PAYFAST_IP)

    assert answer.status_code == 415


# Seeing payments


@pytest.mark.django_db
def test_a_player_sees_only_their_own_payments(owing, people, signed_in):
    mine = start(owing, people["sipho"], "100")
    start(owing, people["thandi"], "50")

    listed = signed_in(people["sipho"]).get(MY_PAYMENTS).json()
    detail = reverse("api-v1:payment", kwargs={"reference": mine.reference})

    assert [p["reference"] for p in listed] == [str(mine.reference)]
    assert signed_in(people["sipho"]).get(detail).json()["status"] == "pending"
    assert signed_in(people["thandi"]).get(detail).status_code == 404


@pytest.mark.django_db
def test_a_payment_and_its_notifications_are_never_deleted(owing, people, api):
    payment = start(owing, people["sipho"], "100")
    post_itn(api, itn_fields(payment))

    with pytest.raises(ValueError):
        payment.delete()
    logged = GatewayNotification.objects.get()
    with pytest.raises(ValueError):
        logged.delete()
    with pytest.raises(ValueError):
        logged.save()


# Cash (FR-22)


@pytest.mark.django_db
def test_an_admin_records_cash_for_a_player(owing, people, cashier, signed_in, paid_signals):
    answer = signed_in(cashier).post(
        url("team-cash-payments", owing),
        {"amount": "350", "player_id": people["sipho"].pk, "reason": "Paid at the bar"},
    )

    assert answer.status_code == 201
    data = answer.json()
    assert (data["method"], data["amount"], data["reason"]) == ("cash", "350.00", "Paid at the bar")
    assert data["player"]["id"] == people["sipho"].pk
    assert data["recorded_by_name"] == "Cash Admin"
    assert paid_signals == ["Red Lions"]
    assert ledger.team_balance(owing).is_paid


@pytest.mark.django_db
def test_cash_for_the_whole_team(owing, cashier, signed_in):
    answer = signed_in(cashier).post(url("team-cash-payments", owing), {"amount": "100"})

    assert answer.json()["subject"] == "team"
    assert answer.json()["reason"] == "Cash paid to the club"


@pytest.mark.django_db
def test_cash_is_recorded_in_a_cash_only_club(owing, cashier, signed_in, club_a):
    club_a.settings.payment_mode = PaymentMode.CASH_ONLY
    club_a.settings.save()

    assert (
        signed_in(cashier).post(url("team-cash-payments", owing), {"amount": "50"}).status_code
        == 201
    )


@pytest.mark.django_db
def test_cash_checks(owing, people, cashier, signed_in):
    client = signed_in(cashier)
    cash = url("team-cash-payments", owing)

    assert client.post(cash, {"amount": "351"}).status_code == 409
    assert client.post(cash, {"amount": "-1"}).status_code == 400
    outsider = client.post(cash, {"amount": "10", "player_id": people["lerato"].pk})
    assert outsider.status_code == 400


@pytest.mark.django_db
def test_only_the_teams_club_admins_record_cash(
    owing, people, signed_in, admin_of, club_b, make_user, give_role, club_a
):
    other_admin = admin_of(club_b)
    referee = make_user("ref@example.com")
    give_role(referee, club_a, ClubRole.Role.REFEREE)
    cash = url("team-cash-payments", owing)

    assert other_admin.post(cash, {"amount": "10"}).status_code == 404
    assert signed_in(people["thandi"]).post(cash, {"amount": "10"}).status_code == 404
    assert signed_in(referee).post(cash, {"amount": "10"}).status_code == 404
    assert not LedgerEntry.objects.filter(kind="payment").exists()


# Which Teams have paid (FR-21)


@pytest.mark.django_db
def test_admins_see_which_teams_have_paid(
    owing, make_team, make_user, cashier, signed_in, club_a, season
):
    tigers = make_team("Blue Tigers", make_user("t@example.com", position="outfield"))
    ledger.charge_league_fee(tigers)
    services.record_cash(team=tigers, admin=cashier, amount=D("350"))
    services.record_cash(team=owing, admin=cashier, amount=D("100"))

    answer = signed_in(cashier).get(
        reverse("api-v1:club-team-payments", kwargs={"club_id": club_a.pk})
    )

    assert answer.status_code == 200
    rows = answer.json()
    assert [(r["team"]["name"], r["outstanding"], r["is_paid"]) for r in rows] == [
        ("Red Lions", "250.00", False),
        ("Blue Tigers", "0.00", True),
    ]
    assert rows[0]["season"]["id"] == season.pk
    filtered = signed_in(cashier).get(
        reverse("api-v1:club-team-payments", kwargs={"club_id": club_a.pk}),
        {"season": season.pk + 1},
    )
    assert filtered.json() == []


@pytest.mark.django_db
def test_other_clubs_and_players_cannot_see_which_teams_have_paid(
    owing, people, admin_of, club_b, signed_in, club_a
):
    path = reverse("api-v1:club-team-payments", kwargs={"club_id": club_a.pk})

    assert admin_of(club_b).get(path).status_code == 403
    assert signed_in(people["thandi"]).get(path).status_code == 403


# Review fixes (chunk 18 review)


@pytest.mark.django_db
def test_a_non_ascii_signature_is_rejected_not_a_server_error(api, owing, people):
    payment = start(owing, people["sipho"], "100")
    fields = [(n, "é" * 32 if n == "signature" else v) for n, v in itn_fields(payment)]

    answer = post_itn(api, fields)

    assert answer.status_code == 400
    assert card_entries(owing).count() == 0
    assert GatewayNotification.objects.get().outcome == "rejected"


@pytest.mark.django_db
def test_a_pending_payment_whose_merchant_is_gone_lists_without_checkout(
    owing, people, signed_in, settings
):
    payment = start(owing, people["sipho"], "100")
    settings.PAYFAST_MERCHANT_ID = "99999999"  # The account it was made with is removed.

    answer = signed_in(people["sipho"]).get(MY_PAYMENTS)

    assert answer.status_code == 200
    [listed] = answer.json()
    assert listed["reference"] == str(payment.reference)
    assert listed["checkout"] is None
