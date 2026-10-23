# Chunk 16: Reschedules and Captain requests

Unattended run, 2026-10-23. PRD: FR-7 to FR-9, FR-18, the targeting rules ("On a
reschedule, only the Admin of the registered Night and the Referee of the affected pitch
are notified"), Screens.md Captain 5 and Admin 2/3. Builds on the chunk 7 lifecycle, the
chunk 9 targeting (`reschedule_players`, `reschedule_officials`), the chunk 11 checkpoints
(Confirmations per kick-off), and the chunk 14 replacement search.

## Plan

Models (fixtures app):
- `FixtureReschedule`: one per Admin reschedule. Fixture, from and to kick-off, from and
  to pitch, who, when, note, the Captain request it answered (if any), whether the
  Confirmations went out at once, how many were told. Never changed or deleted.
- `CaptainRequest`: a Captain's request to cancel or postpone a match (FR-18). Fixture,
  Team, kind (cancel or postpone), reason, the kick-off it was for, who asked, status
  (pending, accepted, declined, withdrawn, closed: no longer applies), who decided, when,
  note. One pending request per Fixture and Team. Never deleted.

Service `backend/fixtures/reschedules.py`:
- `plan(fixture, kick_off, pitch, now)`: checks the move and says what it will do (status
  after, Confirmations now, how many Players and officials are told). Only a scheduled,
  confirming or ready match; the new kick-off must be after the T-6h cutoff counted from
  now, inside the Season, on the Division's Night; the pitch must be the Club's and free
  then; neither Team may have another match that day; something must change.
- `reschedule(...)`: moves the kick-off and pitch, closes the match's open Notifications,
  moves it back to `scheduled` (the lifecycle restarts), sends one Update to both Teams'
  Players (FR-7) and only the Night's Admins and the old and new pitch's Referee (FR-8), and
  if the new kick-off is within the Confirmation window (36 hours) sends Confirmations now
  through the T-36h checkpoint (FR-9). Pending Captain requests for the old kick-off close.
- Captain requests: `request()`, `withdraw()`, `decline()`, `accept()`. Accepting a
  cancellation takes that Team out of the match: `one_team_out`, then the chunk 14
  replacement search (FR-13 to FR-17). Accepting a postponement is a reschedule to the
  kick-off and pitch the Admin picks. Nothing changes before an Admin accepts. The Night's
  Admins get an Update when a request comes in; the Captain gets one on the decision.

Endpoints:
- Admin: `POST /api/v1/clubs/{club_id}/fixtures/{id}/reschedule/preview/`,
  `POST .../fixtures/{id}/reschedule/`; `GET /api/v1/clubs/{club_id}/captain-requests/`,
  `POST .../captain-requests/{id}/accept/`, `POST .../captain-requests/{id}/decline/`.
  The fixture detail gains `reschedules` and `captain_requests`.
- Captain and Players of the Team: `GET` and `POST /api/v1/fixtures/{id}/requests/`;
  `POST /api/v1/captain-requests/{id}/withdraw/`.

Screens:
- Club fixture: Reschedule (date, time, pitch; preview of who is told and whether
  Confirmations go out now) and the match's Captain requests with Accept and Decline.
- Club requests: Cancellations and postponements waiting for the Admin.
- Match (Player): the Team's request status; for the Captain, "Cancel or postpone".
- Cancel or postpone (Captain): reason, cancel or postpone, Send to Admin, and that the
  Admin must accept it.

Tests: pytest for each rule, refusal, permission, club isolation and notification
target; Vitest for each screen.

Later (not in this chunk):
- Admin cancels a match outright (no Captain request): not in the chunk prompt; logged.
- Credit for a Team that withdraws while the match still goes ahead: none (as for a Team
  out at T-6h); FR-43 credit only when the match is cancelled (chunk 15).
- Booking reschedules (FR-31): chunk 23/24.

## Result

Built:
- `CaptainRequest` and `FixtureReschedule` (fixtures migration 0007), shown read-only in the
  Django admin under each Fixture; never deleted (a reschedule is never changed).
- `backend/fixtures/reschedules.py`: `plan()` and `reschedule()` (FR-7 to FR-9) with the
  checks above; a new kick-off restarts the lifecycle and, within the Confirmation window,
  sends Confirmations at once through `checkpoints.send_confirmations` (which now takes the
  Admin as actor); a pitch-only move keeps the replies. Captain requests: `request()`,
  `withdraw()`, `decline()`, `accept()` (a cancellation takes the Team out and opens the
  chunk 14 replacement search; a postponement is a reschedule). Pending requests that no
  longer apply close and their Captains are told.
- Endpoints: `POST /api/v1/clubs/{club_id}/fixtures/{id}/reschedule/preview/`,
  `POST .../fixtures/{id}/reschedule/`, `GET /api/v1/clubs/{club_id}/captain-requests/`
  (`status`, `fixture` filters), `POST .../captain-requests/{id}/accept/` and `/decline/`,
  `GET`/`POST /api/v1/fixtures/{id}/requests/`, `POST /api/v1/captain-requests/{id}/withdraw/`.
  The Admin's fixture detail gains `reschedules` and `captain_requests`. Enum names pinned
  (`CaptainRequestKindEnum`, `CaptainRequestStatusEnum`); schema.d.ts regenerated.
- Screens: Club fixture gains Reschedule (date, kick-off, pitch chips, note, "Check who is
  told" preview from the backend, then Reschedule), the reschedule history, and Captain
  requests with Accept and Decline (a postponement accepts with the time picked under
  Reschedule). New Captain requests screen (`/clubs/:clubId/requests`, linked from
  Fixtures). Match screen gains "Cancel or postpone" (the Team's requests; the Captain's
  link and Withdraw). New Cancel or postpone screen (`/fixtures/:fixtureId/request`).
  `southAfricanMoment()` in format.ts sends picked times with their +02:00 offset.
- Tests: 28 new pytest tests (`test_reschedules.py`): targeting (opt-outs, other clubs,
  only the affected pitches' Referees), restart and FR-9, pitch-only moves, every refusal,
  preview, permissions and club isolation, request create/withdraw/decline/accept for both
  kinds, fallback with no replacement, closing stale requests. 19 new Vitest tests
  (Club fixture reschedule and requests, Captain requests list, match requests, Cancel or
  postpone).

Not built: the Later list above (Admin cancel without a Captain request is logged in
docs/OPEN_QUESTIONS.md). No Admin home/menu exists yet, so the Captain requests screen is
reached from Fixtures.

By hand: run `make migrate` (one new migration).

Checks: make test (589 passed), make lint (passed), npm test (204 passed), npm run build
(passed).

## Review (fix: chunk 16 review)

Checked commit bb31f47 against the chunk prompt and CLAUDE.md: club isolation (the Admin
viewsets use `ClubAdminMixin`, pitches are checked against the Club in the serializer and
the service, a Captain withdraws only their own Team's requests), targeting (one Update to
both Teams' opted-in Players and only the Night's Admins and the old and new pitch's
Referee, FR-7, FR-8), FR-9 Confirmations at once through the T-36h checkpoint, cutoffs read
from ClubSettings, no money touched, append-only records (`CaptainRequest` and
`FixtureReschedule` refuse delete), UI only from `la-` classes, schema.d.ts in sync, nothing
from later chunks.

Found and fixed:
- **Rescheduling back to an earlier kick-off revived its old state.** Answers, checkpoints,
  readiness checks and replacement offers are keyed by kick-off. Moving A to B and back to
  A made the T-36h checkpoint think A's Confirmations had already gone out (none were sent,
  so both Teams would fail at T-6h) and brought back A's old answers. `reschedules._check`
  now refuses (409) a kick-off the match already has any of these for. Test:
  `test_moving_back_to_a_kick_off_that_already_had_confirmations_is_refused`. Logged in
  docs/OPEN_QUESTIONS.md and docs/DECISIONS.md (provisional).

Not changed (noted): a pitch clash is checked only at the exact kick-off, as the fixture
import does; the postponement Accept button sends the time under Reschedule without a
preview (the backend still checks everything).

Checks: make test (590 passed), make lint (passed), npm test (204 passed), npm run build
(passed).
