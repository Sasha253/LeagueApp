from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from ledger import services as ledger
from ledger.tests import conftest as ledger_fixtures
from payments import payfast
from payments.signals import team_paid

season = ledger_fixtures.season
division = ledger_fixtures.division
player = ledger_fixtures.player
make_team = ledger_fixtures.make_team
people = ledger_fixtures.people
lions = ledger_fixtures.lions
cashier = ledger_fixtures.cashier

MERCHANT_ID = "10000100"
MERCHANT_KEY = "46f0cd694581a"
PASSPHRASE = "jt7NOE43FZPn"
PAYFAST_IP = "197.97.145.145"


@pytest.fixture(autouse=True)
def payfast_settings(settings):
    """PayFast's public sandbox account, and the ITN checked by a fake PayFast server."""
    settings.PAYFAST_SANDBOX = True
    settings.PAYFAST_MERCHANT_ID = MERCHANT_ID
    settings.PAYFAST_MERCHANT_KEY = MERCHANT_KEY
    settings.PAYFAST_PASSPHRASE = PASSPHRASE
    settings.PAYFAST_CLUB_ACCOUNTS = {}
    settings.PAYFAST_NOTIFY_URL = "https://api.example.com/api/v1/payments/payfast/notify/"
    settings.PAYMENT_RETURN_URL = "https://app.example.com/payments/done"
    settings.PAYMENT_CANCEL_URL = "https://app.example.com/payments/cancelled"
    settings.PAYFAST_TRUSTED_PROXIES = 0
    return settings


@pytest.fixture(autouse=True)
def payfast_server(monkeypatch):
    """PayFast's validate endpoint: answers VALID unless `payfast_server.valid` is False.
    `payfast_server.posted` lists what was posted back."""

    class Server:
        valid = True
        posted: list[str] = []

    server = Server()
    server.posted = []

    def confirms(self, data):
        server.posted.append(data)
        return server.valid

    monkeypatch.setattr(payfast.PayFastGateway, "server_confirms", confirms)
    return server


@pytest.fixture
def owing(lions):
    """Red Lions owe their R 350 league fee."""
    ledger.charge_league_fee(lions)
    return lions


@pytest.fixture
def signed_in():
    def make(user):
        client = APIClient()
        client.force_authenticate(user)
        client.user = user
        return client

    return make


@pytest.fixture
def paid_signals():
    """The Teams `team_paid` was sent for."""
    sent = []

    def receiver(sender, team, **kwargs):
        sent.append(team.name)

    team_paid.connect(receiver, dispatch_uid="test-team-paid")
    yield sent
    team_paid.disconnect(dispatch_uid="test-team-paid")


def itn_fields(payment, *, status="COMPLETE", amount=None, pf_payment_id="1089250", **changes):
    """An ITN for `payment` as PayFast sends it, signed with our passphrase."""
    gross = Decimal(payment.card_amount if amount is None else amount)
    fields = [
        ("m_payment_id", str(payment.reference)),
        ("pf_payment_id", pf_payment_id),
        ("payment_status", status),
        ("item_name", payfast.item_name(payment)),
        ("item_description", ""),
        ("amount_gross", f"{gross:.2f}"),
        ("amount_fee", "-2.30"),
        ("amount_net", f"{gross - Decimal('2.30'):.2f}"),
        ("custom_str1", ""),
        ("name_first", "Sipho"),
        ("name_last", ""),
        ("email_address", payment.player.email),
        ("merchant_id", MERCHANT_ID),
    ]
    fields = [(name, changes.pop(name, value)) for name, value in fields]
    passphrase = changes.pop("passphrase", PASSPHRASE)
    fields.append(("signature", payfast.signature(fields, passphrase, skip_blank=False)))
    assert not changes, f"Unknown ITN fields: {changes}"
    return fields
