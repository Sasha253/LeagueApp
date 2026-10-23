# Chunk 13: T-6h readiness

Unattended run, 2026-10-23. PRD: FR-5, FR-6 and the match lifecycle. Builds on the chunk 7
lifecycle (`fixtures/lifecycle.py`), the chunk 8 ledger (`ledger.services.team_balance`),
the chunk 11 checkpoints (`fixtures/checkpoints.py`) and the chunk 12 answers
(`confirmations.confirmed_count`).

## Plan

Models (fixtures app):
- `Fixture.Status.BOTH_TEAMS_OUT` ("Both teams out"). Moves: scheduled or confirming to
  both teams out; both teams out to friendly or cancelled (chunk 15 decides which). Also
  scheduled to ready, for a match whose Confirmations never went out and that the Admin
  lets go ahead. Friendly-eligible can still change while both teams are out.
- `FixtureCheckpoint.Kind.READINESS` ("Readiness checked (T-6h)"), so the check runs exactly
  once per Fixture and kick-off, like the other checkpoints.
- `TeamReadiness`: one per Fixture, Team and kick-off. What the check saw (confirmed, the
  Division minimum, what the Team still owed), the outcome (waiting for the Admin, playing,
  out), why (below the minimum, unpaid, no Confirmations went out), and the Admin's decision
  (who, when, note). A decision is made once and never changed.

Service (`backend/fixtures/readiness.py`):
- `check(fixture_id, now)`: the T-6h checkpoint, run in the same pass before the Reminder
  (so a match that is out isn't reminded). For each Team of a `confirming` Fixture:
  - fewer confirmed than the Division minimum: out (FR-5), automatically;
  - else owes anything on the ledger (outstanding above R 0): waiting for the Admin (FR-6);
  - else playing.
  A Fixture still `scheduled` (its Confirmations never went out, so no one could answer):
  both Teams wait for the Admin; nothing is ruled out by a count no one could change.
- `decide(readiness, admin, play|out, note)`: the Admin's ruling on a waiting Team. 409 when
  it is already decided or the match has moved on.
- When no Team is waiting, the Fixture moves: both playing to `ready`, one out to
  `one_team_out`, both out to `both_teams_out`; and `readiness_settled` (a signal) is sent
  with the Fixture and the Teams out. Chunks 14 and 15 connect to it; nothing listens yet.

Endpoints (club Admin only, that Club's records only):
- `GET /api/v1/clubs/{club_id}/tonight/`: today's Fixtures (South African date) and any
  Fixture still waiting for a ruling; each Team's confirmed count against the minimum, what
  is due, paid and outstanding, and its readiness; `at_risk` decided in the backend.
- `POST /api/v1/clubs/{club_id}/readiness/{id}/decide/` `{decision: play|out, note}`.

Screen: Tonight (`/clubs/:clubId/tonight`, f11-tonight design): "At risk" cards on top with
each Team's line (confirmed, paid or "R x of R y") and, for a Team waiting for the Admin,
"Let them play" and "Rule out" (asks once more); then the rest by pitch and time. Linked
from Profile next to Fixtures.

Tests: pytest for each rule (short is out, unpaid waits, paid and full is ready, both out,
scheduled waits, exactly once, run order before the Reminder, late and too-late runs,
decide play/out and the status it settles to, decide twice 409, other club 404, not an
Admin 403, signal sent once). Vitest for Tonight.

Later (not in this chunk):
- Notifications for a Team that is out, the replacement search and the friendly or
  cancellation: chunks 14 and 15 (connect to `readiness_settled`).
- Recording the cash itself ("Mark paid (cash)" in the design): the payments chunks; here
  the Admin only rules "play".
- Payment Barcodes as the proof of payment (FR-6, FR-23): chunk 20; until then "paid" is
  the chunk 8 ledger balance.
- The money summary row on Tonight (Finances), the Referee's Tonight: later chunks.
- A replacement Team accepted after T-6h (chunk 14) gets no readiness row of its own.

## Result

Built:
- `Fixture.Status.BOTH_TEAMS_OUT` and the new moves (scheduled or confirming to both teams
  out; both teams out to friendly or cancelled; scheduled to ready); friendly-eligible can
  still change while both teams are out. `FixtureCheckpoint.Kind.READINESS`.
  `TeamReadiness` (migration 0004), shown read-only in the Django admin under each Fixture.
- `backend/fixtures/readiness.py`: `assess()` (FR-5 short is out, FR-6 unpaid waits, no
  Confirmations sent waits), `decide()` (the Admin's play/out ruling, once, 409 otherwise),
  the single status move once every Team is decided, the `readiness_settled` signal for
  chunks 14 and 15, and `tonight()`.
- `checkpoints.check_readiness`, run once per Fixture and kick-off at T-6h (late only
  before kick-off), before the Reminder in the same pass.
- `GET /api/v1/clubs/{club_id}/tonight/` and
  `POST /api/v1/clubs/{club_id}/readiness/{id}/decide/` (club Admins only); schema and
  `frontend/src/api/schema.d.ts` regenerated.
- Tonight screen (`/clubs/:clubId/tonight`, f11 design): at-risk cards with each Team's
  line and the ruling buttons ("Let {Team} play", "Rule {Team} out" which asks once more),
  then the rest by pitch and time. Linked from Profile. "Both teams out" status label.
- Tests: 32 new pytest tests (`fixtures/tests/test_readiness.py`) on a frozen clock;
  chunk 7 and 11 tests updated for the new moves and the readiness checkpoint. 7 new
  Vitest tests (`TonightPage.test.tsx`) and a Profile link assertion.

Not built: the Later list above.

By hand: run `make migrate` (new table, new statuses).

Checks: make test (505 passed), make lint (passed), npm test (178 passed), npm run build
(passed).
