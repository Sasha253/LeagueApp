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

## Review (fix: chunk 6 review)

Independent review of 38b7ae2 against the chunk 6 prompt and CLAUDE.md.

Checked and fine:
- Scope: frontend only, no backend or API change, `npm run gen:api` not needed; nothing from
  later chunks (no tab bar, notifications, fixtures or payments).
- Club isolation: Admin screens call `/api/v1/clubs/{club_id}/teams/...`, which the API scopes
  to the Admin's Club; a 403 shows "Only this club's Admins can see its Teams." Profile only
  links Admins to their own Clubs' Team requests.
- Captain and membership checks compare `captain_id` and `player_id` with `me.id`; both are
  user ids in the chunk 5 API, so they match.
- Money: the league fee is the API's Decimal string, shown with `formatRand` ("R 350").
  Whether a Division takes Teams (`is_open`) comes from the API.
- Dates: UTC moments are turned into South African dates with `localDate` before `formatDate`.
- UI: `la-` components and tokens only; SelectableRow is listed as a proposed component.
- Tests: a Vitest file for every new screen, plus Profile links and `localDate`.

Fixed:
- Double taps sent a change twice. Accept and Decline (Captain), Ask to join (Find a team)
  and Withdraw (Teams) stayed live while the request was in flight, so a second tap sent a
  second POST and the API's refusal of it showed as an error after the first one worked.
  Those buttons are now off until the API answers. Test: TeamPage "sends an answer once,
  even on a double tap".

Noted, not changed:
- The "Full" / "Not open yet" label on a closed Division is read from `is_open` and
  `effective_league_fee`, the same rule the API documents for `is_open`. If more reasons
  appear, the API should send the reason itself.
- `useLoad` keeps the last result while a new key loads, so for a moment after a new Night
  is picked in Find a team, the old Night's results and Division chips still show. Harmless
  (the results refresh), left as is to keep `useLoad` unchanged for the club setup screens.

Checks after the fix: make test 161 passed; make lint clean; npm test 102 passed (21 files);
npm run build ok.
