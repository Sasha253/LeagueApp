# Chunk 14: One Team out: replacement opponent

Unattended run, 2026-10-23. PRD: FR-13 to FR-16 (and the hand-off to FR-17). Builds on the
chunk 13 `readiness_settled` signal (`fixtures/readiness.py`), the chunk 7 lifecycle, the
chunk 9 notifications and targeting, the chunk 11 checkpoints and the chunk 12 answers.

## Plan

Models (fixtures app):
- `ReplacementOffer`: one search for a new opponent. Fixture, kick-off, the out Team, the
  remaining Team, the slot (home or away), opened at, closes at, status (open, accepted,
  lapsed: no Team accepted in time, withdrawn: the match moved on), the Team that accepted,
  its Captain, when, and when it ended. At most one open offer per Fixture. Never deleted.
- `ReplacementCandidate`: one per offer and Team offered, with the Captain's offer
  Notification.
- `ClubSettings.replacement_close_hours_before` (and in `SettingsDefaults`): the offer
  closes this many hours before kick-off. Default 2, below the readiness hours. Editable on
  the Club settings screen.
- Lifecycle: new move `replacement_offered -> scheduled` (a Team accepted before the T-36h
  Confirmations).

Service (`backend/fixtures/replacements.py`):
- `open_offer(fixture, out_team, actor)`: connected to `readiness_settled` when one Team is
  out; chunk 16 (Captain cancellation) calls it directly later. Moves the Fixture to
  `replacement_offered`; General Notification to the out Team's Players (with "Find a
  match", FR-13); Update to the remaining Team (FR-14); Confirmation-kind offer to the
  Captain of each eligible Team (FR-15); Update to the Night's Admins and the pitch's Referee
  (FR-16). With no eligible Team, or the close time already passed, it lapses at once.
- Eligible Team (provisional): active, same Club, Season and Division, not either Team of
  the match, owes nothing on the ledger, has no other match that day (South African date,
  not cancelled), and its Captain has opted into the Night (targeting rule).
- `accept(candidate, captain)`: the Captain's "I'm in" on the offer Notification
  (`POST /api/v1/inbox/{id}/answer/`). Locks the Fixture, then the offer, then the Team:
  the first Team wins, a second gets 409 "Another Team took this slot". Rechecks eligibility.
  Swaps the Team into the out Team's slot, moves the Fixture (`scheduled` before T-36h,
  `confirming` before T-6h, `ready` after), closes every offer Notification, sends
  Confirmations to the new Team's Players (FR-15), and Updates to the remaining Team and the
  officials (FR-16).
- `lapse_due(now)`: run with the checkpoints every minute. An open offer past its close time
  lapses and `replacement_lapsed` is sent (chunk 15 connects); one whose match moved on is
  withdrawn. Offer Notifications are closed either way.
- Chunk 12 change: a Team that accepted after T-6h answers its Confirmations until kick-off
  (the match is `ready`); everyone else's cutoff is unchanged.

Endpoints: no new endpoint. The offer is answered through the inbox answer endpoint; the
Admin's fixture detail (`GET /api/v1/clubs/{club_id}/fixtures/{id}/`) gains `replacements`.

Screens: Club fixture shows "Replacement opponent" (offered to, closes, who took it, or
lapsed). Club settings gets the new value. The offer itself uses the existing Notification
screen.

Tests: pytest for each rule (notifications and their targeting on open, eligibility, first
accept wins, second 409, concurrent accepts, recheck on accept, status by time, late
replacement answers until kick-off, lapse and withdraw, signal, settings validation,
admin serializer). Vitest for Club fixture and Club settings.

Later (not in this chunk):
- Friendly or cancellation once no Team accepts (FR-17): chunk 15 connects to
  `replacement_lapsed`. Both Teams out: chunk 15.
- Captain cancellation opening an offer (FR-18): chunk 16 calls `open_offer`.
- A readiness check (minimum, payment) of a Team accepted after T-6h: none.

## Result

Built:
- `ReplacementOffer` and `ReplacementCandidate` (fixtures migration 0005), shown read-only
  in the Django admin under each Fixture; never deleted. At most one open offer per
  Fixture.
- `ClubSettings.replacement_close_hours_before` and `SettingsDefaults` (clubs migration
  0005, existing rows set to 2); the API refuses a value not below the readiness hours;
  on the Club settings screen.
- `backend/fixtures/replacements.py`: `open_offer()` (connected to `readiness_settled` for
  one Team out), `eligible_teams()`, `accept()` (the Captain's "Confirm" on the offer via
  `POST /api/v1/inbox/{id}/answer/`; first wins, 409 otherwise, eligibility rechecked),
  `lapse_due()` / `end_offer()` (run by the `fixtures.run_checkpoints` task) and the
  `replacement_lapsed` signal for chunk 15.
- Notifications: FR-13 General to the out Team, FR-14 Update to the remaining Team, the
  offers to eligible Captains, FR-16 Updates to the Night's Admins and the pitch's Referee
  (on opening and on accept), Confirmations to the new Team's Players (FR-15), an Update
  naming the new opponent. Targeting: `targeting.opted_in_captains()`.
- Lifecycle: new move `replacement_offered -> scheduled`; `lifecycle.lock()` locks a
  Fixture without joins (used by the checkpoints, answers, rulings and replacements),
  since a joined lock found no row once a Team had been swapped in concurrently.
- Chunk 12 change: a Team that took the slot after T-6h answers until kick-off.
- `GET /api/v1/clubs/{club_id}/fixtures/{id}/` gains `replacements`; schema.d.ts
  regenerated. Club fixture screen shows "New opponent" (offered to, until when, who took
  it, or no Team).
- Tests: 30 new pytest tests (`test_replacements.py`, and a threaded two-Captains test in
  `test_replacements_concurrency.py`), settings validation and defaults, chunk 7, 11 and
  13 tests updated. 4 new Vitest tests (Club fixture, Club settings).

Not built: the Later list above. The offer uses the existing Notification screen (its
buttons read "I'm in" / "Can't make it"; "Open the match" opens only once the Team has
taken the slot).

By hand: run `make migrate` (two new migrations).

Checks: make test (539 passed), make lint (passed), npm test (181 passed), npm run build
(passed).

## Review (independent, unattended run)

Compared 284c8b7 with the chunk 14 prompt and the CLAUDE.md rules.

- Money: eligibility uses `team_balance(team).outstanding > 0` (Decimal); no new money
  fields. Ledger untouched.
- Club isolation: candidates are filtered to the Fixture's Club, Season and Division; only
  the candidate Team's current Captain can accept (via the recipient-only inbox answer
  endpoint); the Admin detail goes through the club-scoped `ClubFixtureViewSet`;
  `notify()` refuses a Fixture of another Club.
- Configurable values: `replacement_close_hours_before` is a ClubSettings/SettingsDefaults
  value, validated below the readiness hours and on the Club settings screen.
- Notification targeting: FR-13/FR-14 go to opted-in Players of the out and remaining
  Teams; offers only to opted-in Captains; FR-16 to the Night's Admins and the pitch's
  Referee (`targeting.officials`). Matches the PRD and docs/OPEN_QUESTIONS.md.
- Concurrency: every path locks Fixture, then Notification, then offer, then Team
  (`notifications.services.answer` locks the Fixture first), so no deadlock between an
  accept and the lapse task; a second accept gets 409 and its answer is rolled back.
  The join-free `lifecycle.lock()` is sound. Threaded test present.
- Append-only: offers and candidates are never deleted (PROTECT, `delete()` raises,
  read-only admin inline).
- UI: only `la-` classes, type styles and existing components (StatusChip, Banner).
- Tests cover each rule; `npm run gen:api` reproduces the committed schema.d.ts (no diff).
- Scope: nothing from chunks 15 or 16 (only the `replacement_lapsed` signal and an
  `open_offer()` entry point).

Noted, not changed (not defects of this chunk):
- The Notification screen shows "Open the match" on the FR-13 General Notification and on
  a Captain's offer, but the out Team's Players (after a swap) and a candidate Captain
  cannot open that match; the screen shows its normal error. A later UI chunk could hide
  the link when the Player is not in the match.
- The Captain's continued membership of the candidate Team is not rechecked (only
  `team.captain`); Captains are kept as members by the teams app.

No defects found that needed a code change.

Checks: make test (539 passed), make lint (passed), npm test (181 passed), npm run build
(passed), npm run gen:api (no change).
