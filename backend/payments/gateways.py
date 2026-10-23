"""The payment gateway interface. PayFast now; Peach Payments and Yoco later.

A Club picks its provider in setup (`ClubSettings.payment_provider`); `gateway_for` gives
the implementation. Every gateway takes card details on its own hosted page, so they never
reach this app (NFR Security), and confirms payments by a server-to-server notification
that the gateway implementation verifies before anything is recorded.

Credentials come from the environment (Django settings), never from the database.
"""

import ipaddress
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from django.utils.module_loading import import_string

from clubs.models import Club, PaymentProvider


class NotificationRejected(Exception):
    """A gateway notification failed a check; nothing is recorded from it."""


@dataclass(frozen=True)
class Checkout:
    """Where the payer's browser goes to pay: a link, or the same as a form to post."""

    url: str
    action: str
    fields: list[tuple[str, str]]


@dataclass(frozen=True)
class Confirmation:
    """What a verified gateway notification says about one of our payments."""

    status: str  # One of Payment.Status: complete, failed, cancelled or pending.
    gateway_payment_id: str
    amount: Decimal


class PaymentGateway(ABC):
    provider: str
    # The smallest card amount the gateway takes, in rand.
    minimum_amount: Decimal

    @abstractmethod
    def merchant_id_for(self, club: Club) -> str | None:
        """The merchant account the Club's card payments go to; None if not set up."""

    @abstractmethod
    def checkout(self, payment) -> Checkout:
        """The hosted payment page for a pending Payment's card part."""

    @abstractmethod
    def source_allowed(self, ip: str | None) -> bool:
        """Whether a notification may come from this address."""

    @abstractmethod
    def reference_of(self, fields: list[tuple[str, str]]) -> str:
        """Our Payment reference named in a notification."""

    @abstractmethod
    def verify(self, payment, fields: list[tuple[str, str]]) -> Confirmation:
        """Checks a notification for `payment`; raises NotificationRejected if any fails."""


GATEWAYS = {PaymentProvider.PAYFAST: "payments.payfast.PayFastGateway"}


def gateway_for(provider: str) -> PaymentGateway:
    try:
        return import_string(GATEWAYS[provider])()
    except KeyError:
        raise ValueError(f"No payment gateway for {provider!r}.") from None


def in_networks(ip: str | None, networks: list[str]) -> bool:
    if not ip:
        return False
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(address in ipaddress.ip_network(network, strict=False) for network in networks)


def client_ip(request, trusted_proxies: int) -> str | None:
    """The address a request came from. Behind `trusted_proxies` reverse proxies, it is
    the one the outermost trusted proxy saw, read from the right of X-Forwarded-For, so a
    caller can't put in an address of their own."""
    if trusted_proxies <= 0:
        return request.META.get("REMOTE_ADDR")
    forwarded = [
        part.strip()
        for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
        if part.strip()
    ]
    if len(forwarded) < trusted_proxies:
        return None
    return forwarded[-trusted_proxies]
