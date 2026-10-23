"""A match that can't go ahead: a friendly, or a cancellation (FR-10 to FR-12, FR-17, FR-43).

Two hand-offs end here:

- the T-6h readiness check left both Teams out (`readiness_settled`, fixtures/readiness.py);
- one Team was out and no Team took its slot (`replacement_lapsed`, fixtures/replacements.py).

`fall_back()` then decides, once per Fixture, in the backend:

- The Admin listed the match as friendly-eligible and kick-off is still to come: it becomes
  a friendly (`open_friendly`). Both Teams out (FR-10 to FR-12): a General Notification with
  "Find a match" to both Teams' Players, a Confirmation ("free to join") to the Players
  outside both Teams, and an Update to the Night's Admins and the pitch's Referee. No
  replacement (FR-17): a General Notification to the out Team's Players, a Confirmation to
  every Player outside the out Team (the remaining Team's too), and an Update to the
  officials. Players only for the Nights they opted into (targeting rules).
- Otherwise it is cancelled (`cancel_match`) and every payment recorded for the match
  becomes credit to whoever paid it (FR-43, FR-52; ledger/services.py
  `return_fixture_payments`). The Teams and the officials are told.

Each invited Player's Confirmation is a FriendlyInvite: "Confirm" joins the friendly,
"Decline" doesn't, and they can change it until kick-off while the match is still a
friendly for that kick-off. The answer lives on the Notification.

Friendly fees, who pays them and the friendly's Captain (FR-24) come with chunk 22.

Locks: the Fixture first (callers already hold it), then the ledger rows, in every path.
"""

from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.dispatch import receiver
from django.utils import timezone

from core.exceptions import Conflict
from ledger.services import return_fixture_payments
from notifications import services as notifications
from notifications import targeting
from notifications.models import Answer, Kind, Notification
from notifications.services import match_day, match_time, notification_answered
from teams.models import Team

from . import lifecycle
from .models import Fixture, FixtureFallback, FixtureTransition, FriendlyInvite
from .readiness import readiness_settled
from .replacements import replacement_lapsed

S = Fixture.Status
Cause = FixtureFallback.Cause
Outcome = FixtureFallback.Outcome

RELATED = ("club__settings", "division__night", "pitch", "home_team", "away_team")

NOT_DUE = "A {status} Fixture doesn't fall back to a friendly or a cancellation."
NO_LONGER_FRIENDLY = "This friendly is no longer on, so it can't be joined."


def _when(fixture: Fixture) -> str:
    return f"{match_day(fixture.kick_off)}, {match_time(fixture.kick_off)}, {fixture.pitch.name}"


def _match(fixture: Fixture) -> str:
    return f"{fixture.home_team.name} vs {fixture.away_team.name}"


def _cause_of_move(actor) -> str:
    return FixtureTransition.Cause.ADMIN if actor else FixtureTransition.Cause.SYSTEM


def _rand(amount: Decimal) -> str:
    """ "R 350", "R 18,550" or "R 12.50" (CLAUDE.md)."""
    whole = amount == amount.to_integral_value()
    return f"R {amount:,.0f}" if whole else f"R {amount:,.2f}"


@transaction.atomic
def cancel_match(fixture: Fixture, *, actor=None, note: str, now: datetime | None = None):
    """Cancels the Fixture and returns every payment for it as credit to whoever paid
    (FR-43, FR-52). Its open Notifications stop taking answers. Returns the credits.

    Chunk 16 (Captain and Admin cancellations) calls this too.
    """
    now = now or timezone.now()
    fixture = lifecycle.lock(fixture.pk, *RELATED)
    lifecycle.transition(
        fixture, S.CANCELLED, cause=_cause_of_move(actor), actor=actor, note=note[:300]
    )
    fixture.status = S.CANCELLED
    notifications.close(Notification.objects.filter(fixture=fixture))
    reason = f"Match cancelled: {_match(fixture)}, {match_day(fixture.kick_off)}"
    return return_fixture_payments(fixture, reason=reason[:300], recorded_by=actor)


def _out_teams(fixture: Fixture, remaining: Team | None) -> list[Team]:
    teams = [fixture.home_team, fixture.away_team]
    return [team for team in teams if remaining is None or team.pk != remaining.pk]


def _cancel(fixture, out_teams, remaining, actor, now) -> None:
    why = (
        "Both Teams are out"
        if remaining is None
        else f"{out_teams[0].name} is out and no other Team took the slot"
    )
    credits = cancel_match(fixture, actor=actor, note=f"{why}; the match is cancelled.", now=now)
    club, night, when, match = fixture.club, fixture.night, _when(fixture), _match(fixture)
    credit_line = " Anything paid for this match is now credit." if credits else ""
    for team in out_teams:
        notifications.notify(
            Kind.GENERAL,
            targeting.team_players(team, night),
            club=club,
            title=f"{match} is cancelled"[:120],
            body=f"{when}. Find a match with another Team.{credit_line}",
            fixture=fixture,
        )
    if remaining is not None:
        notifications.notify(
            Kind.UPDATE,
            targeting.team_players(remaining, night),
            club=club,
            title=f"{match} is cancelled"[:120],
            body=f"{when}. No new opponent was found.{credit_line}",
            fixture=fixture,
        )
    total = sum((c.amount for c in credits), Decimal("0.00"))
    money = f" {_rand(total)} returned as credit." if credits else ""
    notifications.notify(
        Kind.UPDATE,
        targeting.officials(fixture),
        club=club,
        title=f"{match} is cancelled"[:120],
        body=f"{when}. {why}.{money}",
        fixture=fixture,
    )


def _friendly_recipients(fixture: Fixture, remaining: Team | None) -> list:
    """FR-11: Players outside both Teams. FR-17: every Player outside the out Team, so the
    remaining Team's Players too. Only those opted into the Night."""
    outside = list(targeting.players_outside(fixture))
    if remaining is None:
        return outside
    return list(targeting.team_players(remaining, fixture.night)) + outside


def _open_friendly(fixture, fallback, out_teams, remaining, actor, now) -> None:
    why = (
        "Both Teams are out"
        if remaining is None
        else f"{out_teams[0].name} is out and no other Team took the slot"
    )
    lifecycle.transition(
        fixture,
        S.FRIENDLY,
        cause=_cause_of_move(actor),
        actor=actor,
        note=f"{why}; it is open as a friendly."[:300],
    )
    fixture.status = S.FRIENDLY
    # The league match's Confirmations and offers no longer apply.
    notifications.close(Notification.objects.filter(fixture=fixture))
    club, night, when, match = fixture.club, fixture.night, _when(fixture), _match(fixture)

    # FR-10, FR-17: the out Team(s), with "Find a match".
    for team in out_teams:
        notifications.notify(
            Kind.GENERAL,
            targeting.team_players(team, night),
            club=club,
            title=f"{match} is off for {team.name}"[:120],
            body=f"{when}. Your Team can't play this match. Find a match with another Team.",
            fixture=fixture,
        )
    # FR-11, FR-17: free to join, until kick-off.
    if remaining is None:
        title, body = "Friendly: free to join", f"{when}. Both Teams are out. Are you playing?"
    else:
        title = f"Friendly with {remaining.name}: free to join"
        body = f"{when}. {out_teams[0].name} is out. Are you playing?"
    sent = notifications.notify(
        Kind.CONFIRMATION,
        _friendly_recipients(fixture, remaining),
        club=club,
        title=title[:120],
        body=body,
        fixture=fixture,
        answer_by=fixture.kick_off,
    )
    FriendlyInvite.objects.bulk_create(
        [FriendlyInvite(fallback=fallback, player_id=n.recipient_id, notification=n) for n in sent]
    )
    # FR-12, FR-17: the Night's Admins and the pitch's Referee.
    invited = f"{len(sent)} Player{'s' if len(sent) != 1 else ''} invited to join."
    notifications.notify(
        Kind.UPDATE,
        targeting.officials(fixture),
        club=club,
        title=f"{match} is now a friendly"[:120],
        body=f"{when}. {why}. {invited}",
        fixture=fixture,
    )


@transaction.atomic
def fall_back(
    fixture: Fixture,
    cause: str,
    *,
    remaining: Team | None = None,
    actor=None,
    now: datetime | None = None,
) -> FixtureFallback:
    """A friendly when the Fixture is friendly-eligible and kick-off is still to come,
    otherwise a cancellation. Once per Fixture: a second call returns the first outcome."""
    now = now or timezone.now()
    fixture = lifecycle.lock(fixture.pk, *RELATED)
    existing = FixtureFallback.objects.filter(fixture=fixture).first()
    if existing is not None:
        return existing
    expected = S.BOTH_TEAMS_OUT if cause == Cause.BOTH_TEAMS_OUT else S.REPLACEMENT_OFFERED
    if fixture.status != expected:
        raise Conflict(NOT_DUE.format(status=S(fixture.status).label.lower()))
    if cause == Cause.BOTH_TEAMS_OUT:
        remaining = None
    elif remaining is None or remaining.pk not in (fixture.home_team_id, fixture.away_team_id):
        raise ValueError("The remaining Team isn't in this Fixture.")
    friendly = fixture.friendly_eligible and now < fixture.kick_off
    fallback = FixtureFallback.objects.create(
        fixture=fixture,
        kick_off=fixture.kick_off,
        cause=cause,
        remaining_team=remaining,
        outcome=Outcome.FRIENDLY if friendly else Outcome.CANCELLED,
        decided_at=now,
    )
    out_teams = _out_teams(fixture, remaining)
    if friendly:
        _open_friendly(fixture, fallback, out_teams, remaining, actor, now)
    else:
        _cancel(fixture, out_teams, remaining, actor, now)
    return fallback


@receiver(readiness_settled, dispatch_uid="fixtures.fallback_on_both_teams_out")
def both_teams_out(sender, fixture: Fixture, out: list, actor=None, **kwargs) -> None:
    """The T-6h check left both Teams out (chunk 13): a friendly or a cancellation."""
    if len(out) == 2 and fixture.status == S.BOTH_TEAMS_OUT:
        fall_back(fixture, Cause.BOTH_TEAMS_OUT, actor=actor)


@receiver(replacement_lapsed, dispatch_uid="fixtures.fallback_on_no_replacement")
def no_replacement(sender, fixture: Fixture, offer, **kwargs) -> None:
    """No Team took the slot (chunk 14): a friendly or a cancellation (FR-17)."""
    fall_back(fixture, Cause.NO_REPLACEMENT, remaining=offer.remaining_team)


# Joining a friendly


def is_invite(notification: Notification) -> bool:
    return FriendlyInvite.objects.filter(notification_id=notification.pk).exists()


@receiver(notification_answered, dispatch_uid="fixtures.friendly_invite_answered")
def invite_answered(sender, notification: Notification, previous: str, **kwargs) -> None:
    """An invited Player's answer joins the friendly (or not). The answer is refused, and
    so not saved, once the match is no longer a friendly for that kick-off. The Fixture is
    already locked (notifications/services.py `answer`)."""
    invite = (
        FriendlyInvite.objects.filter(notification_id=notification.pk)
        .select_related("fallback")
        .first()
    )
    if invite is None:
        return
    fixture = Fixture.objects.get(pk=invite.fallback.fixture_id)
    if fixture.status != S.FRIENDLY or fixture.kick_off != invite.fallback.kick_off:
        raise Conflict(NO_LONGER_FRIENDLY)


def joined(fallback: FixtureFallback):
    """The invited Players who have joined (answered "Confirm"), by name."""
    return (
        FriendlyInvite.objects.filter(fallback=fallback)
        .filter(notification__answer=Answer.CONFIRM)
        .select_related("player__player_profile")
        .order_by("player__name", "player_id")
    )
