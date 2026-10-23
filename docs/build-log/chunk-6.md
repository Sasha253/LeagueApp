# Chunk 6: Teams (UI)

Unattended run, 2026-10-23. Screens on the chunk 5 API, from design/src/ds/Screens.md
(Player 4 and 5, Captain 1 to 3, Admin 3). design/ has no drawn Team screens, so they are
built from the Screens.md descriptions with the existing `la-` components.

## Plan

No model or endpoint changes: the chunk 5 API covers every screen.

Screens (frontend/src/pages/teams/):
- `/teams` Teams (Player tab): my current and past Teams, my requests to join (Withdraw),
  links to Find a team and Request a Team.
- `/teams/find` Find a team: search by name and Night chips, then Division chips from the
  results; Ask to join; "Request sent" waiting state until the Captain answers.
- `/teams/new` Request a Team: pick a Season, then a Division from selectable rows (closed
  ones show why), a name; Send to Admin; then "Waiting for the Admin".
- `/teams/:id` A Team: status, Club, Season, Division, Night, Players (members only). For
  its Captain: pending requests to join with Accept / Decline. For a Player in it who is
  not Captain: Leave (asks first).
- `/clubs/:clubId/teams` Admin Team requests: requests waiting (Confirm, Decline with an
  optional reason), then active Teams.
- `/clubs/:clubId/teams/:id` Admin Team: details, Players, Make Captain.
- Entry points: Profile links to Teams (Players) and to Team requests (Admins). No tab bar
  yet.

Tests: Vitest for each screen with the fake API (lists, actions, API error reasons,
permissions shown as messages).

Later (not in this chunk): tab bar; notifications for Team decisions; removing Players;
squad confirmed/waiting per match and PaymentProgress on My team (Fixtures and payments
chunks).

## Result

Built (all in frontend/, no backend change; `npm run gen:api` gives no diff):
- Player: Teams (`/teams`: current and past Teams, requests to join with Withdraw), Find a
  team (`/teams/find`: name, Night and Division filters, Ask to join, waiting state).
- Captain: Request a Team (`/teams/new`: Season chips, Night and Division rows with fee,
  room and why a Division is closed, name, Send to Admin, waiting state), Team page
  (`/teams/:id`: status, Players, Asking to join with Accept and Decline). A Player in the
  Team who isn't Captain can leave it, after asking.
- Admin: Team requests (`/clubs/:clubId/teams`: Confirm, Decline with an optional reason,
  confirmed Teams), Team (`/clubs/:clubId/teams/:id`: who asked and decided, Players,
  Make Captain after asking).
- Profile links: Teams for Players, Team requests for Admins.
- `localDate()` in `frontend/src/format.ts`: a UTC moment's South African date.
- `LoadState` takes a `forbidden` message; SelectableRow proposed component.
- Tests: Vitest for every new screen (`frontend/src/pages/teams/*.test.tsx`), the Profile
  links and `localDate`.

Not built: the Later list above.

By hand: nothing. Review the provisional choices in docs/OPEN_QUESTIONS.md.

Checks: make test 161 passed; make lint clean; npm test 101 passed (21 files);
npm run build ok.
