"""The privacy policy, kept in one place.

The app shows it from GET /api/v1/legal/privacy/ and the store listings link to the plain
page at /privacy/; both read `privacy_policy()`. It describes what this app actually keeps
(accounts, profiles, replies, payments, Barcodes, bookings, ledger entries, push tokens)
and is written for South Africa's Protection of Personal Information Act (POPIA).

Change the text here, and move UPDATED_ON, whenever what the app collects or shares
changes; the App Store privacy labels and the Google Play Data safety form must then be
updated too (docs/STORE_RELEASE.md).
"""

from dataclasses import dataclass
from datetime import date

from django.conf import settings

UPDATED_ON = date(2026, 10, 24)

# When the environment names no operator: still true, and never a club's name.
DEFAULT_OPERATOR = "The business that runs League App"


@dataclass(frozen=True)
class Section:
    heading: str
    paragraphs: tuple[str, ...]


@dataclass(frozen=True)
class PrivacyPolicy:
    title: str
    updated_on: date
    operator: str
    contact_email: str
    sections: tuple[Section, ...]


def _contact(email: str) -> str:
    if email:
        return f"Write to {email} with any question or request about your personal information."
    return "Ask your Club's Admin, who will pass your question or request on to us."


def privacy_policy() -> PrivacyPolicy:
    operator = settings.PRIVACY_OPERATOR_NAME.strip() or DEFAULT_OPERATOR
    email = settings.PRIVACY_CONTACT_EMAIL.strip()
    sections = (
        Section(
            "Who we are",
            (
                f"{operator} runs League App, one app for the social football clubs that use "
                "it. Each Club runs its own leagues, Nights and fields in the app.",
                "We and your Club are both responsible for your personal information under "
                "South Africa's Protection of Personal Information Act (POPIA). " + _contact(email),
            ),
        ),
        Section(
            "What we keep",
            (
                "Your account: name, email address, phone number and a password, which we "
                "store only as a one-way hash.",
                "Your Player profile: whether you play outfield, in goal or both, and the "
                "Nights you want notifications for.",
                "Your football: the Teams you belong to or captain, your replies to match "
                "Confirmations, Player and Goalkeeper Requests, and the fixtures you play.",
                "Payments and bookings: what you paid, when and how, the payment reference, "
                "your Payment Barcodes and when they were scanned at the gate, field bookings, "
                "and your Club's ledger entries (charges, payments, credits and refunds).",
                "Notifications: the messages the app sent you and, if you allow push "
                "notifications, a push token for your phone.",
            ),
        ),
        Section(
            "What we never keep",
            (
                "Card details. Card payments go straight to PayFast, a PCI-compliant payment "
                "gateway. The app never sees or stores your card number.",
                "Camera images. Admins and Referees use the camera only to read Payment "
                "Barcodes at the gate. Nothing the camera sees is saved or sent anywhere.",
                "Your location, contacts or photos. The app does not ask for them.",
            ),
        ),
        Section(
            "Why we use it",
            (
                "To run your league: sign-up, fixtures, match confirmations, cancellations, "
                "replacements and friendlies, and finding Players and Goalkeepers.",
                "To take and prove payments, and to keep your Club's financial records.",
                "To send you the notifications the app is built on, only for the Nights you "
                "opted into and the roles you hold.",
            ),
        ),
        Section(
            "Who sees it",
            (
                "Your Club's Admins and Referees see what they need to run their Club: your "
                "name, Team, replies, payments and Barcodes. Another Club never sees them.",
                "Your Captain and Team see your name and your replies for their matches.",
                "Service providers that run parts of the app for us: PayFast (card payments), "
                "Google Firebase Cloud Messaging (push notifications) and our hosting "
                "provider. They use your information only to provide that service.",
                "Your Club's accountant, when the Club exports its ledger.",
                "We do not sell your information, show advertising or track you across "
                "other apps and websites.",
            ),
        ),
        Section(
            "How long we keep it",
            (
                "Your account and profile for as long as you use the app.",
                "Payments and ledger entries for as long as the law requires a business to "
                "keep its financial records, even after you leave.",
            ),
        ),
        Section(
            "Your rights",
            (
                "You can see and correct your profile in the app at any time.",
                "You can ask what we hold about you, ask us to correct or delete it, or "
                "object to how we use it. " + _contact(email),
                "You can complain to South Africa's Information Regulator "
                "(https://inforegulator.org.za).",
            ),
        ),
        Section(
            "Children",
            (
                "League App is for adults. A Club that signs up a Player under 18 needs the "
                "consent of a parent or guardian first.",
            ),
        ),
        Section(
            "Security",
            (
                "The app talks to us only over encrypted connections (HTTPS) and signs you in "
                "with a token, never a password kept on your phone. Payment Barcodes are "
                "signed so they cannot be copied to another Team or forged.",
            ),
        ),
        Section(
            "Changes",
            (
                "When this policy changes we update the date at the top and, for a change "
                "that matters, let you know before it applies.",
            ),
        ),
    )
    return PrivacyPolicy(
        title="Privacy policy",
        updated_on=UPDATED_ON,
        operator=operator,
        contact_email=email,
        sections=sections,
    )
