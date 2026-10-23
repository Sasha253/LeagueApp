# Chunk 12: Answering Confirmations

Unattended run, 2026-10-23. PRD: FR-3, FR-38 (and FR-1, FR-5 for context). Builds on the
chunk 9 Notification answers (`notifications/services.answer`), the chunk 11 checkpoints
(`fixtures/checkpoints.py`, cutoff = kick-off minus `readiness_hours_before`) and the
Division's `min_players` (chunk 3).

## Plan

Model (fixtures app):
- `ConfirmationAnswer`: Fixture, Team, Player, the kick-off it answers for, answer
  (confirm or decline), answered at, how it was given (notification or fixture screen).
  Unique per Fixture, Player and kick-off, so a Player has one current answer per match and
  a reschedule (chunk 16) starts with no answers. Changed in place until the cutoff (FR-3).
  This is the record the T-6h readiness check (chunk 13) counts, so a Player who didn't
  opt into the Night's notifications (and got no Confirmation) can still answer.

Service (`backend/fixtures/confirmations.py`):
- `answer(fixture, player, value, via)`: locks the Fixture, checks it is `confirming`, that
  now is before the cutoff (from the Club's settings, never from the app), and that the
  Player is in one of its Teams now. Saves the answer and copies it onto the Player's
  Confirmation Notification for this Fixture, so the inbox and the resend (FR-2) agree.
- A receiver for `notification_answered`: answering the Confirmation Notification records
  the same answer through `answer()`; a refusal rolls the Notification answer back.
- `notifications.services.answer()` locks the Fixture before the Notification, the same
  order as the fixture screen and the resend, so the two paths can't deadlock.
- `squad(fixture, team)`: every Player in the Team now with their answer (or none), the
  counts, the Division minimum, and whether the Team is below it (FR-38, FR-5).

Endpoints:
- `GET /api/v1/fixtures/{id}/squad/`: my Team's replies for the match (only Players in one
  of its Teams; the other Team's replies are not shown).
- `POST /api/v1/fixtures/{id}/answer/` `{answer: confirm|decline}`: answer or change it;
  409 after the cutoff or when replies aren't open; answers with the squad.

Screens:
- Match detail (FixturePage): SquadProgress (`la-progress`) with confirmed against the
  Division minimum and a "Short n" / "Ready" chip; the squad list grouped Confirmed,
  Waiting, Declined (f06-short design); your reply as ConfirmationCard buttons, collapsing
  into a chip with "Change" until the cutoff (f02 design).
- Notification detail: after answering a Confirmation, show the same SquadProgress for
  the match.

Tests: pytest for every rule (cutoff, status, membership, change answer, sync both ways,
other club / other team 404, squad counts and minimum, left Players excluded, reschedule
kick-off). Vitest for the Match detail and Notification screens.

Later (not in this chunk):
- The T-6h readiness check counting these answers: chunk 13 (`confirmations.confirmed_count`).
- Sending a Confirmation to a Player who joins a `confirming` match, and FR-9 reschedules:
  chunk 16 / later; such a Player answers on the match screen.
- Admin view of both Teams' replies (Tonight screen): chunk 13.
- Borrowed Players (FR-37) counting towards the squad: chunk 17.

## Result

Built:
- `ConfirmationAnswer` (fixtures app, migration 0003), shown read-only in the Django admin
  under each Fixture.
- `backend/fixtures/confirmations.py`: `answer()` (status `confirming`, before the Club's
  cutoff, Player in a Team of the match now; keeps the Confirmation Notification in step),
  the `notification_answered` receiver (answering in the inbox records the same answer, and
  a refusal rolls the inbox answer back), `squad()` and `confirmed_count()` for chunk 13.
- `notifications.services.answer()` now locks the Fixture before the Notification, the same
  order as the match screen and the resend.
- `GET /api/v1/fixtures/{id}/squad/` and `POST /api/v1/fixtures/{id}/answer/`; schema and
  `frontend/src/api/schema.d.ts` regenerated (`ConfirmationAnswerEnum`).
- Match detail (`FixturePage`): SquadProgress, Are you playing? (I'm in / Can't make it,
  then the answer with Change until the cutoff), and the squad list. Notification detail:
  SquadProgress for a Confirmation, refreshed after answering. `frontend/src/pages/fixtures/squad.tsx`.
- Tests: 24 pytest tests (`fixtures/tests/test_confirmations.py`) on a frozen clock; two
  chunk 9 tests now answer a Confirmation of a `confirming` match. 8 new Vitest tests.

Not built: the Later list above.

By hand: run `make migrate` (new table).

Checks: make test (448 passed), make lint (passed), npm test (171 passed), npm run build
(passed).

## Review (independent, 2026-10-23)

Plan: compare 3c1e870 with the chunk 12 prompt and the CLAUDE.md rules, run all four checks,
fix real defects only.

Checked and fine:
- Rules live in the backend: status `confirming`, the cutoff from the Club's
  `readiness_hours_before`, membership now; the app only draws `replies_open`, `answer_by`
  and `below_minimum`. The Division minimum is data (`Division.min_players`).
- Access: squad and answer go through FixtureViewSet, which only finds Fixtures of the
  Player's active Teams (404 otherwise); only the Player's own Team's replies are returned.
  No money or ledger in this chunk. Notification targeting unchanged.
- Locking order (Fixture, then Notification) is the same in every path; a refused inbox
  answer rolls back in the same transaction.
- UI uses `la-` components and tokens only (`la-progress`, `la-group`, `la-disc`, chips);
  schema.d.ts matches the endpoints. Nothing from chunk 13+ was built.

Fixed:
- An answer was counted for whichever Team the Player is in now, not the Team it was given
  for. A Player who confirmed for the home Team and then moved to the away Team of the same
  match counted as confirmed for the away Team (`confirmed_count`, `squad`), which chunk 13
  would use to decide who is out at T-6h. Both now filter on the answer's Team; new test
  `test_an_answer_for_the_other_team_does_not_count_after_a_move`. Logged in
  OPEN_QUESTIONS.md and DECISIONS.md (provisional).

Noted, not changed:
- After such a move the Player's Confirmation Notification still shows the old answer, and
  answering it with the same value is a no-op (`notifications.services.answer` returns
  early), so they must re-answer on the match screen. Rare; left for chunk 16 (Team and
  fixture changes).

Checks after the fix: make test 449 passed, make lint passed, npm test 171 passed, npm run build passed.
