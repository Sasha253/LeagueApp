# Chunk 17: Player and Goalkeeper Requests

Unattended run, 2026-10-23. PRD: FR-35 to FR-38, the visibility rule ("Player Requests are
shown only to outfield Players and Goalkeeper Requests only to Goalkeepers"), the
Notifications table (Player Request and Goalkeeper Request: Confirmation format, Accept /
Decline, Players not in either opposing Team) and the targeting rules (Night opt-ins).
Screens.md Captain 4 "Request a player" (Player or Goalkeeper and how many, preview of who
is told) and Player 1 "Games you can join". Builds on the chunk 9 targeting
(`request_recipients`), the chunk 12 squad (FR-38) and the chunk 13 readiness count.

Open questions 1 and 2 of docs/DECISIONS.md could not be asked (unattended run): see
docs/OPEN_QUESTIONS.md "Chunk 17". Chosen: no fee for a borrowed Player in this chunk
(nothing charged); the Captain gets an Update when the request fills.

## Plan

Models (fixtures app):
- `PlayerRequest`: a Captain's request for borrowed Players. Fixture, Team, kind (player or
  goalkeeper), places (how many, 1 to the Division minimum), the kick-off it is for, who
  raised it and when, status (open, filled, withdrawn, closed: no longer applies), when it
  ended, why, how many were asked. One open request per Fixture, Team and kind. Never
  deleted.
- `PlayerRequestInvite`: a Player the request was sent to and their Notification (the
  Accept / Decline lives on the Notification), like `FriendlyInvite`.
- `BorrowedPlayer`: a Player who accepted and joined the Team for that match and
  kick-off. Unique per Fixture, kick-off and Player (one Team per match), never deleted.

Service `backend/fixtures/borrowing.py`:
- `preview(fixture, captain, kind)`: how many would be asked (FR-36).
- `raise_request(fixture, captain, kind, places)`: only the Captain of a Team in the match,
  while it is scheduled, confirming or ready and before kick-off; sends a Player Request
  (outfield) or Goalkeeper Request (goalkeepers) Notification, answerable until kick-off, to
  `targeting.request_recipients` (not in either Team, opted into the Night) minus Players
  already borrowed for the match. 409 when no one can be asked or one is already open.
- Accepting the Notification joins (FR-37), in the Notification's transaction with the
  Fixture locked first and the request row locked: the first `places` to accept join, the
  rest get 409 and their answer is not saved; once filled the request closes, every other
  invite stops taking answers and the Captain gets an Update. A database constraint keeps a
  Player to one borrowed place per match.
- `withdraw(request, captain)`: closes an open request and its invites; who joined stays.
- A request stops applying when the match moves to a new kick-off, its Team leaves the
  match, or the match is no longer scheduled, confirming or ready; its invites already
  close with the match's Notifications.
- Borrowed Players count as confirmed for their Team (FR-5 readiness and FR-38 squad).

Endpoints:
- `GET`/`POST /api/v1/fixtures/{id}/player-requests/` (Team's Players see; Captain raises),
  `GET /api/v1/fixtures/{id}/player-requests/preview/?kind=` (Captain),
  `POST /api/v1/player-requests/{id}/withdraw/` (Captain),
  `GET /api/v1/me/player-requests/` (games I can join or joined; answering uses the
  existing `POST /api/v1/notifications/{id}/answer/`).
- The squad gains `borrowed`.

Screens:
- Match: "Players from other teams": the Team's requests, who joined, Withdraw (Captain),
  and "Request a player" for the Captain.
- Request a player (Captain 4): Player or Goalkeeper, how many, the backend's preview of
  who is asked, Send request.
- Squad replies show borrowed Players among the confirmed.
- My fixtures: "Games you can join" with Join match / Not tonight.

Tests: pytest for targeting, visibility, first-to-accept and filling, concurrency (two
accepts at once), refusals, permissions, club isolation, stale requests, readiness count;
Vitest for each screen.

Later (not in this chunk):
- A fee for a borrowed Player in a league match (open question 1; payments chunks 18 to 22).
- A borrowed Player leaving after joining.
- Admin view of a match's requests.

## Result

Built:
- `PlayerRequest`, `PlayerRequestInvite` and `BorrowedPlayer` (fixtures migration 0008),
  shown read-only in the Django admin under each Fixture; none can be deleted, a
  `BorrowedPlayer` never changes. Enum names pinned (`PlayerRequestKindEnum`,
  `PlayerRequestStatusEnum`).
- `backend/fixtures/borrowing.py`: `preview()`, `raise_request()`, `withdraw()`, and the
  `notification_answered` receiver that joins on Accept (`join()`): Fixture then request
  locked, the first N to accept join, then filled, other invites closed, Captain told. A
  late Accept is refused (409) and its answer is not saved. A request that no longer
  applies (new kick-off, Team out of the match, match out/friendly/cancelled, kick-off
  passed) shows as closed and can't be joined.
- Borrowed Players count as confirmed: `confirmations.confirmed_count` (T-6h check, FR-5)
  and the squad (`borrowed`, FR-38).
- Endpoints: `GET`/`POST /api/v1/fixtures/{id}/player-requests/`,
  `GET /api/v1/fixtures/{id}/player-requests/preview/?kind=`,
  `POST /api/v1/player-requests/{id}/withdraw/`, `GET /api/v1/me/player-requests/`
  (answer with `POST /api/v1/inbox/{notification_id}/answer/`). schema.d.ts regenerated.
- Screens: Match gains "Players from other teams" (requests, who joined, Withdraw, and
  "Request a player" for the Captain); new Request a player screen
  (`/fixtures/:fixtureId/players`: Player or Goalkeeper, how many as chips, the backend's
  preview of who is asked, "Ask for 2 goalkeepers"); squad replies list borrowed Players
  among the confirmed; My fixtures gains "Games you can join" with Join match / Not
  tonight. Built from existing `la-` classes and components only.
- Tests: 30 new pytest tests (`test_borrowing.py`, `test_borrowing_concurrency.py`):
  targeting by position, Night and Teams, other clubs, permissions, places, one open per
  kind, no one to ask, closed matches, first-to-accept and filling, the Captain's Update,
  decline then accept, no taking back, one Team per match, stale requests after a
  reschedule or a Team out, withdraw, the T-6h count, the squad, every endpoint, and two
  Players accepting the last place at once. 11 new Vitest tests (`PlayerRequests.test.tsx`).

Not built: the Later list above. Open questions 1 and 2 were answered provisionally (no
fee; the Captain is told when filled), see docs/OPEN_QUESTIONS.md "Chunk 17".

By hand: run `make migrate` (one new migration). Review the provisional answers to
open questions 1 and 2 in docs/OPEN_QUESTIONS.md.

Checks: make test (620 passed), make lint (passed), npm test (215 passed), npm run build
(passed).

## Review (fix: chunk 17 review)

Independent review of 8f12c15 against the chunk prompt and CLAUDE.md.

Plan: read the diff, check club isolation, targeting, races, append-only rows, configurable
values, UI and tests; run the four checks; fix real defects only.

Checked and fine:
- Club isolation: the Team's requests go through `FixtureViewSet.get_object` (my Teams'
  Fixtures, 404 otherwise); withdraw is scoped to `team__captain=user`; "Games you can
  join" to the signed-in Player's own invites. Recipients come from the Night (one Club).
- Targeting: outfield Players for a Player Request, Goalkeepers for a Goalkeeper Request
  ("both" counts as either), opted into the Night, in neither Team (FR-36, visibility rule).
- Races: Fixture locked first by `notifications.answer`, then the request row; a late
  Accept raises 409 and rolls the answer back; a unique constraint keeps one borrowed place
  per Player and match. Withdraw and raise lock in the same order.
- Configurable values: the most places is the Division's minimum (data). No money, no
  ledger entries (open question 1, provisional: no fee).
- Rows are never deleted; admin inlines are read-only.
- UI uses only existing `la-` classes and components; Vitest covers each screen; schema
  regenerated.
- Nothing from later chunks.

Defects fixed:
- `GET /api/v1/me/player-requests/` still said "You're playing for <Team>" after the match
  moved to a new kick-off or the Team left the match, although that borrowed place no
  longer counts (`confirmations.borrowed` filters by kick-off and Team). `joined` now uses
  the same rule (`borrowing.still_playing`).
- The same list kept offering a request that no longer applies (Team out of the match):
  the row stays open in the database and its Notification is not closed by a Team leaving,
  so it showed "1 place left" with no way to answer. The list now drops invites whose
  request no longer applies and where the Player has no place that still counts.
- The view's docstring named the answer URL as `/notifications/...`; it is
  `/api/v1/inbox/{notification_id}/answer/` (schema.d.ts regenerated).
- Two pytest tests added for the above.

Not changed (noted): a Team leaving the match does not close its request's invite
Notifications in the inbox; accepting one is refused with 409 "This request no longer
applies." Closing them belongs with the replacement and fallback paths.

Checks: make test (622 passed), make lint (passed), npm test (215 passed), npm run build
(passed).
