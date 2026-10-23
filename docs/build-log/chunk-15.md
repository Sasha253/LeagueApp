# Chunk 15: Friendly fallback or cancellation

Unattended run, 2026-10-23. PRD: FR-10 to FR-12, FR-17, FR-43 (and FR-52 for who gets the
credit). Builds on the chunk 13 `readiness_settled` signal (both Teams out), the chunk 14
`replacement_lapsed` signal (no Team took the slot), the chunk 7 lifecycle and
friendly-eligible flag, the chunk 9 notifications and targeting, and the chunk 8 ledger.

## Plan

Models (fixtures app):
- `FixtureFallback`: what happened to a match that couldn't go ahead as a league match.
  Fixture (one per Fixture), kick-off, cause (both Teams out, or no replacement found), the
  remaining Team (none when both were out), outcome (friendly or cancelled), decided at.
  Never deleted.
- `FriendlyInvite`: one per Player invited to join the friendly, with their
  Confirmation-kind Notification. Their answer on it is whether they join. Never deleted.

Service (`backend/fixtures/fallbacks.py`):
- `fall_back(fixture, cause, actor)`: connected to `readiness_settled` (both Teams out) and
  `replacement_lapsed`. Friendly-eligible and kick-off still to come: `open_friendly`;
  otherwise `cancel`.
- `open_friendly`: moves the Fixture to `friendly`. Both Teams out (FR-10 to FR-12):
  General with "Find a match" to both Teams' Players, Confirmation ("free to join") to
  Players outside both Teams, Update to the Night's Admins and the pitch's Referee. No
  replacement (FR-17): General to the out Team's Players, Confirmation to every Player
  outside the out Team (the remaining Team and everyone else), Update to the officials.
  Players only for the Nights they opted into. Invites are answerable until kick-off.
- `cancel_match(fixture, actor, note)`: moves the Fixture to `cancelled`, closes its
  open answerable Notifications, and returns every payment recorded for the match as
  credit to whoever paid (FR-43, FR-52) through a new `ledger.services.return_fixture_payments`
  (calls `return_as_credit`; only what is left of each payment, so running it twice adds
  nothing). Notifications: General with "Find a match" to the out Team(s), Update to the
  remaining Team, Update to the officials.
- Joining: the invited Player's "Confirm" on the invite joins, "Decline" doesn't; they can
  change it until kick-off while the match is still a friendly for that kick-off (409
  otherwise). The chunk 12 Confirmation receiver ignores invites.

Endpoints: no new endpoint. The Admin's fixture detail
(`GET /api/v1/clubs/{club_id}/fixtures/{id}/`) gains `fallback`: cause, outcome, decided
at, remaining Team, how many were invited, who joined (name, position), and the credit
returned (rand, how many entries).

Screens: Club fixture shows "Friendly" (why, invited, who joined) or "Cancelled" (why,
credit returned). Joining uses the existing Notification screen.

Tests: pytest for each path (both out friendly, both out cancelled, lapse friendly, lapse
cancelled, lapse at open with no Team, kick-off passed, notification targeting and Night
opt-ins, credit to Player and Team, partially returned and reversed payments, payments of
other Fixtures untouched, idempotent credit, joining and its 409s, Confirmation receiver
skipping invites, admin serializer). Vitest for Club fixture.

Later (not in this chunk):
- Friendly fees, who pays them and the friendly Captain and Barcode (FR-24): chunk 22.
- Captain cancellation requests (FR-18) and Admin reschedules: chunk 16, which can call
  `fallbacks.cancel_match`.
- A screen of "games you can join" for "Find a match": Player Requests chunk.
- Cancelling a friendly that gets too few Players: not in the PRD.

## Result

Built:
- `FixtureFallback` and `FriendlyInvite` (fixtures migration 0006), shown read-only in the
  Django admin under each Fixture; never changed or deleted.
- `backend/fixtures/fallbacks.py`: `fall_back()` (connected to `readiness_settled` for both
  Teams out and to `replacement_lapsed`), the friendly with FR-10 to FR-12 / FR-17
  notifications and invites answerable until kick-off, `cancel_match()` (reusable by chunk
  16), `invite_answered` (409 once the match is no longer a friendly for that kick-off) and
  `joined()`. The chunk 12 Confirmation receiver ignores friendly invites.
- `ledger.services.return_fixture_payments()` (each payment for the Fixture back as credit
  to whoever paid, FR-43/FR-52; only what is left, reversed payments skipped, never twice)
  and `fixture_credit_returned()`.
- `GET /api/v1/clubs/{club_id}/fixtures/{id}/` gains `fallback` (cause, outcome, remaining
  Team, decided at, invited, joined Players, credit returned and how many entries).
  Enum names pinned (`CauseEnum` kept, `FallbackCauseEnum`, `FallbackOutcomeEnum`);
  schema.d.ts regenerated.
- Club fixture screen: a "Friendly" or "Cancelled" section (why, who joined, or the credit
  returned in "R 18,550" form).
- Tests: 22 new pytest tests (`test_fallbacks.py`); chunk 13 and 14 tests use a new
  `without_fallbacks` fixture so they still see the status they leave the match in.
  4 new Vitest tests (Club fixture).

Not built: the Later list above. Joining a friendly uses the existing Notification screen;
its "Open the match" link doesn't work for a Player outside both Teams (they can't open
that match), as noted in chunk 14.

By hand: run `make migrate` (one new migration).

Checks: make test (561 passed), make lint (passed), npm test (185 passed), npm run build
(passed).
