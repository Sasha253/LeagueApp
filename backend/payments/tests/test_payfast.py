"""The PayFast gateway: signatures, the hosted page, accounts and where ITNs come from."""

import hashlib
from decimal import Decimal
from urllib.parse import parse_qsl, urlsplit

import pytest
from django.test import RequestFactory

from clubs.models import PaymentProvider
from payments import payfast
from payments.gateways import client_ip, gateway_for, in_networks
from payments.services import start_payment

from .conftest import MERCHANT_ID, MERCHANT_KEY, PASSPHRASE


def md5(text):
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()


def test_signature_is_md5_of_the_encoded_fields_and_passphrase():
    fields = [("merchant_id", "10000100"), ("item_name", "Red Lions ~ fee"), ("amount", "350.00")]

    expected = md5(
        "merchant_id=10000100&item_name=Red+Lions+%7E+fee&amount=350.00&passphrase=jt7NOE43FZPn"
    )

    assert payfast.signature(fields, PASSPHRASE, skip_blank=True) == expected


def test_signature_without_a_passphrase_leaves_it_out():
    fields = [("amount", "5.00")]

    assert payfast.signature(fields, "", skip_blank=True) == md5("amount=5.00")


def test_checkout_signatures_skip_blank_fields_but_itn_signatures_keep_them():
    fields = [("a", "1"), ("b", ""), ("c", " 3 ")]

    assert payfast.signature(fields, "", skip_blank=True) == md5("a=1&c=3")
    assert payfast.signature(fields, "", skip_blank=False) == md5("a=1&b=&c=3")


def test_the_gateway_for_payfast():
    gateway = gateway_for(PaymentProvider.PAYFAST)

    assert isinstance(gateway, payfast.PayFastGateway)
    assert gateway.minimum_amount == Decimal("5.00")
    with pytest.raises(ValueError):
        gateway_for("yoco")


@pytest.mark.django_db
def test_checkout_is_the_signed_hosted_page_in_payfast_order(owing, people):
    payment = start_payment(
        team=owing, player=people["sipho"], amount=Decimal("100"), credit="none"
    )

    checkout = gateway_for("payfast").checkout(payment)

    names = [name for name, _ in checkout.fields]
    assert names == [
        "merchant_id",
        "merchant_key",
        "return_url",
        "cancel_url",
        "notify_url",
        "email_address",
        "m_payment_id",
        "amount",
        "item_name",
        "signature",
    ]
    values = dict(checkout.fields)
    assert values["merchant_id"] == MERCHANT_ID
    assert values["merchant_key"] == MERCHANT_KEY
    assert values["amount"] == "100.00"
    assert values["m_payment_id"] == str(payment.reference)
    assert values["item_name"] == "Red Lions league fee"
    assert values["return_url"].endswith(f"/payments/done?payment={payment.reference}")
    unsigned = [(name, value) for name, value in checkout.fields if name != "signature"]
    assert values["signature"] == payfast.signature(unsigned, PASSPHRASE, skip_blank=True)
    assert checkout.action == "https://sandbox.payfast.co.za/eng/process"
    url = urlsplit(checkout.url)
    assert f"{url.scheme}://{url.netloc}{url.path}" == checkout.action
    assert parse_qsl(url.query) == checkout.fields


@pytest.mark.django_db
def test_live_mode_uses_payfasts_live_host(owing, people, settings):
    settings.PAYFAST_SANDBOX = False
    payment = start_payment(team=owing, player=people["sipho"], amount=Decimal("50"), credit="none")

    assert (
        gateway_for("payfast").checkout(payment).action == "https://www.payfast.co.za/eng/process"
    )


@pytest.mark.django_db
def test_a_club_can_have_its_own_merchant_account(owing, people, settings, club_a):
    settings.PAYFAST_CLUB_ACCOUNTS = {
        str(club_a.pk): {"merchant_id": "222", "merchant_key": "k222", "passphrase": "p222"}
    }

    payment = start_payment(team=owing, player=people["sipho"], amount=Decimal("50"), credit="none")

    assert payment.merchant_id == "222"
    values = dict(gateway_for("payfast").checkout(payment).fields)
    assert values["merchant_key"] == "k222"


@pytest.mark.django_db
def test_other_clubs_use_the_default_account(club_b, settings, club_a):
    settings.PAYFAST_CLUB_ACCOUNTS = {
        str(club_a.pk): {"merchant_id": "222", "merchant_key": "k222", "passphrase": ""}
    }

    assert gateway_for("payfast").merchant_id_for(club_b) == MERCHANT_ID


@pytest.mark.django_db
@pytest.mark.parametrize(
    "missing", ["PAYFAST_MERCHANT_ID", "PAYFAST_MERCHANT_KEY", "PAYFAST_NOTIFY_URL"]
)
def test_without_credentials_or_a_notify_url_cards_are_not_set_up(club_a, settings, missing):
    setattr(settings, missing, "")

    assert gateway_for("payfast").merchant_id_for(club_a) is None


@pytest.mark.parametrize(
    ("ip", "allowed"),
    [
        ("197.97.145.144", True),
        ("197.97.145.159", True),
        ("197.97.145.160", False),
        ("41.74.179.200", True),
        ("102.216.36.130", True),
        ("144.126.193.139", True),
        ("8.8.8.8", False),
        ("not-an-ip", False),
        (None, False),
    ],
)
def test_itns_come_only_from_payfasts_networks(ip, allowed, settings):
    assert gateway_for("payfast").source_allowed(ip) is allowed


def test_in_networks_reads_cidrs():
    assert in_networks("10.0.0.5", ["10.0.0.0/24"])
    assert not in_networks("10.0.1.5", ["10.0.0.0/24"])


def test_client_ip_reads_the_connecting_address_without_proxies():
    request = RequestFactory().post(
        "/", REMOTE_ADDR="10.1.1.1", HTTP_X_FORWARDED_FOR="197.97.145.145"
    )

    assert client_ip(request, 0) == "10.1.1.1"


def test_client_ip_behind_a_proxy_ignores_addresses_the_caller_added():
    request = RequestFactory().post(
        "/", REMOTE_ADDR="10.1.1.1", HTTP_X_FORWARDED_FOR="197.97.145.145, 8.8.8.8"
    )

    assert client_ip(request, 1) == "8.8.8.8"
    assert client_ip(request, 2) == "197.97.145.145"
    assert client_ip(request, 3) is None
