"""PayFast: the hosted payment page and the ITN (Instant Transaction Notification).

The payer's browser opens PayFast's own page with our signed fields; PayFast takes the
card there. PayFast then posts an ITN to PAYFAST_NOTIFY_URL. An ITN is believed only
after every check passes, in this order:

1. Source: it comes from one of PayFast's networks (PAYFAST_ITN_NETWORKS).
2. Signature: the MD5 of its fields, in the order received, with our passphrase.
3. Merchant: it names the merchant account the Payment was made with.
4. Amount: the gross amount is the Payment's card amount, to the cent.
5. Server-side validation: posting the fields back to PayFast returns "VALID".

Sandbox or live hosts and the credentials come from the environment (Django settings).
"""

import hashlib
import hmac
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import quote_plus, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.utils import timezone

from clubs.models import Club, PaymentProvider

from .gateways import Checkout, Confirmation, NotificationRejected, PaymentGateway, in_networks

LIVE_HOST = "www.payfast.co.za"
SANDBOX_HOST = "sandbox.payfast.co.za"
VALIDATE_TIMEOUT_SECONDS = 15

STATUSES = {
    "COMPLETE": "complete",
    "FAILED": "failed",
    "CANCELLED": "cancelled",
    "PENDING": "pending",
}


@dataclass(frozen=True)
class Account:
    merchant_id: str
    merchant_key: str
    passphrase: str


def encode(value) -> str:
    """A value encoded the way PayFast's signature expects (PHP urlencode)."""
    return quote_plus(str(value).strip()).replace("~", "%7E")


def param_string(fields: list[tuple[str, str]], *, skip_blank: bool) -> str:
    return "&".join(
        f"{name}={encode(value)}"
        for name, value in fields
        if not (skip_blank and str(value).strip() == "")
    )


def signature(fields: list[tuple[str, str]], passphrase: str, *, skip_blank: bool) -> str:
    """PayFast's signature: MD5 of the fields as a query string, then the passphrase.

    A checkout leaves out blank fields; an ITN is signed over every field it sends.
    """
    text = param_string(fields, skip_blank=skip_blank)
    if passphrase:
        text += f"&passphrase={encode(passphrase)}"
    # MD5 is PayFast's scheme, not our choice; the ITN is also confirmed with PayFast.
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()


def _accounts() -> list[tuple[str | None, Account]]:
    """Every configured account: per Club (keyed by Club id) and the default (None)."""
    accounts = []
    for club_id, values in (settings.PAYFAST_CLUB_ACCOUNTS or {}).items():
        accounts.append(
            (
                str(club_id),
                Account(
                    merchant_id=str(values.get("merchant_id", "")),
                    merchant_key=str(values.get("merchant_key", "")),
                    passphrase=str(values.get("passphrase", "")),
                ),
            )
        )
    accounts.append(
        (
            None,
            Account(
                merchant_id=settings.PAYFAST_MERCHANT_ID,
                merchant_key=settings.PAYFAST_MERCHANT_KEY,
                passphrase=settings.PAYFAST_PASSPHRASE,
            ),
        )
    )
    return [(key, account) for key, account in accounts if account.merchant_id]


def account_for_club(club: Club) -> Account | None:
    accounts = dict(_accounts())
    account = accounts.get(str(club.pk)) or accounts.get(None)
    if account is None or not account.merchant_key:
        return None
    return account


def account_by_merchant(merchant_id: str) -> Account | None:
    for _, account in _accounts():
        if account.merchant_id == merchant_id:
            return account
    return None


def _with_reference(url: str, reference: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url)
    query = f"{parts.query}&" if parts.query else ""
    return urlunsplit(parts._replace(query=query + urlencode({"payment": reference})))


def item_name(payment) -> str:
    """What the payer sees on PayFast's page."""
    if payment.booking_id is not None:
        starts = timezone.localtime(payment.booking.starts_at)
        return f"{payment.booking.field.name} booking, {starts:%a %d %b %H:%M}"
    return f"{payment.team.name} league fee"


class PayFastGateway(PaymentGateway):
    provider = PaymentProvider.PAYFAST
    minimum_amount = Decimal("5.00")  # PayFast takes no card payment under R 5.

    @property
    def host(self) -> str:
        return SANDBOX_HOST if settings.PAYFAST_SANDBOX else LIVE_HOST

    def merchant_id_for(self, club: Club) -> str | None:
        if not settings.PAYFAST_NOTIFY_URL:
            return None  # Without the ITN, no payment could ever be confirmed.
        account = account_for_club(club)
        return account.merchant_id if account else None

    def checkout(self, payment) -> Checkout:
        account = account_by_merchant(payment.merchant_id)
        if account is None:
            raise ValueError("This payment's merchant account is no longer configured.")
        reference = str(payment.reference)
        fields = [
            ("merchant_id", account.merchant_id),
            ("merchant_key", account.merchant_key),
            ("return_url", _with_reference(settings.PAYMENT_RETURN_URL, reference)),
            ("cancel_url", _with_reference(settings.PAYMENT_CANCEL_URL, reference)),
            ("notify_url", settings.PAYFAST_NOTIFY_URL),
            ("email_address", payment.player.email),
            ("m_payment_id", reference),
            ("amount", f"{payment.card_amount:.2f}"),
            ("item_name", item_name(payment)[:100]),
        ]
        fields = [(name, value) for name, value in fields if str(value).strip() != ""]
        fields.append(("signature", signature(fields, account.passphrase, skip_blank=True)))
        action = f"https://{self.host}/eng/process"
        return Checkout(
            url=f"{action}?{param_string(fields, skip_blank=True)}", action=action, fields=fields
        )

    def source_allowed(self, ip: str | None) -> bool:
        return in_networks(ip, settings.PAYFAST_ITN_NETWORKS)

    def reference_of(self, fields: list[tuple[str, str]]) -> str:
        return dict(fields).get("m_payment_id", "")

    def verify(self, payment, fields: list[tuple[str, str]]) -> Confirmation:
        values = dict(fields)
        signed = [(name, value) for name, value in fields if name != "signature"]

        account = account_by_merchant(payment.merchant_id)
        if account is None:
            raise NotificationRejected("The payment's merchant account isn't configured.")
        expected = signature(signed, account.passphrase, skip_blank=False)
        received = values.get("signature", "").encode()
        if not hmac.compare_digest(expected.encode(), received):
            raise NotificationRejected("The signature doesn't match.")
        if values.get("merchant_id") != payment.merchant_id:
            raise NotificationRejected("The ITN names another merchant.")
        try:
            amount = Decimal(values.get("amount_gross", ""))
        except InvalidOperation:
            raise NotificationRejected("The ITN has no amount.") from None
        if amount != payment.card_amount:
            raise NotificationRejected("The amount isn't the payment's card amount.")
        status = STATUSES.get(values.get("payment_status", ""))
        if status is None:
            raise NotificationRejected("Unknown payment status.")
        if not self.server_confirms(param_string(signed, skip_blank=False)):
            raise NotificationRejected("PayFast didn't confirm the ITN.")
        return Confirmation(
            status=status, gateway_payment_id=values.get("pf_payment_id", ""), amount=amount
        )

    def server_confirms(self, data: str) -> bool:
        """Posts the ITN back to PayFast, which answers VALID if it sent it."""
        request = urllib.request.Request(
            f"https://{self.host}/eng/query/validate",
            data=data.encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=VALIDATE_TIMEOUT_SECONDS) as response:  # noqa: S310
                return response.read().decode().strip() == "VALID"
        except OSError:
            return False
