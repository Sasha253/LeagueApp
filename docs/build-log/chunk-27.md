# Chunk 27: Outstanding list and income planner

PRD: FR-47, FR-48 (with FR-22 cash, FR-25 scope, FR-50 append-only, the Notifications
targeting rules). Design: Screens.md Admin 5 (Finances: FinanceSummary with the
week-by-week planner, then the Outstanding list); design/src/screens/f14-finances.mjs.
Unattended run.

## Plan

- No new models. Everything is computed from the ledger and the fixture list in
  `backend/finance/`; writes go through the existing `payments.services.record_cash`
  (ledger entry, FR-22) and `notifications.services.notify`.
- `finance/services.py`:
  - `planner(club, season, night, division)` (FR-47): Season weeks (week 1 starts on the
    Season's first day, South African dates). Each Team's league fees charged are spread
    over its Fixtures in the Season (not cancelled), to the cent; what the Team has paid
    (card, cash, credit) covers its own Fixtures in date order. Per week: matches,
    expected, received (card and cash taken that week), covered, short (only for weeks up
    to now). Totals: season expected, due to date, covered to date, behind, unscheduled.
  - `outstanding(club, season, night, division)` (FR-48): active Teams that owe, largest
    first (with unpaid Players' names and the first short week); Players who owe, largest
    first: their share (what is due over the Team's current Players, rounded up to the
    cent, as "Pay my share") less what they paid, never more than the Team still owes.
- Endpoints, Admins of the Club only (`IsClubAdmin`, other Clubs' records 404):
  - `GET /api/v1/clubs/{club_id}/finance/planner/?season=&night=&division=`
  - `GET /api/v1/clubs/{club_id}/finance/outstanding/?season=&night=&division=`
  - `POST /api/v1/clubs/{club_id}/finance/outstanding/remind/` `{team_id, player_id?}`:
    an Update notification to the Team's Players who owe (and its Captain), or to that
    Player, only if they opted into the Team's Night.
  - `POST /api/v1/clubs/{club_id}/finance/outstanding/cash/` `{team_id, player_id?,
    amount}`: records what the row owes as cash; refused (409) if the amount owed changed.
- Recipients for Remind picked in `notifications/targeting.py`.
- Screens: on Finances, a planner card (Due to date, Paid to date, Behind, Season expected,
  bars per week from `la-planner`, a reading line) and an Outstanding section (Teams /
  Players chips, rows with Remind and Mark cash paid, confirm step for cash).
- Tests: pytest for planner spreading and coverage, outstanding order and shares, Remind
  targeting (opt-in only), Mark cash paid (ledger entry, stale amount refused), Admin only
  and club isolation; Vitest for the planner and the Outstanding list and its actions.
- `npm run gen:api` after the API change.

## Later (not in this chunk)

- Export to CSV / Excel (chunk 28).
- Tapping a planner week to filter the Outstanding list to that week (design note).
- Friendly fees and Booking Users who owe (no charges per Player exist for them yet).

## Result

### Built

- `backend/finance/planner.py` (FR-47) and `GET /api/v1/clubs/{club_id}/finance/planner/
  ?season=&night=&division=`: Season weeks with matches, expected (each Team's league fees
  spread over its Fixtures), covered (each Team's payments over its own Fixtures in date
  order), short (weeks started only) and card and cash received that week; totals season
  expected (equal to the summary's), due to date, covered to date, behind, unscheduled.
- `backend/finance/outstanding.py` (FR-48):
  - `GET /api/v1/clubs/{club_id}/finance/outstanding/`: active Teams that owe, largest
    first, with unpaid Players and the first short week; Players who owe (share less paid,
    capped at the Team's figure), largest first, with whether Remind can reach them.
  - `POST .../finance/outstanding/remind/`: an Update notification to the Team's Captain and
    Players who owe (or the one Player), only those opted into the Team's Night
    (`notifications.targeting.payment_reminder_recipients`); answers who was and wasn't told.
  - `POST .../finance/outstanding/cash/`: records what the row owes as one cash ledger entry
    via `payments.services.record_cash`; 409 if the amount shown is no longer what is owed.
- Admins of the Club only; other Clubs' Seasons and Teams 404.
- 21 pytest tests in `backend/finance/tests/test_planner_outstanding.py`.
- Finances screen: a "Week by week" planner card under FinanceSummary (Due to date, Paid to
  date, Behind, Season expected, `la-planner` bars, reading line, unscheduled note, Show
  weeks list) and an Outstanding section (Teams / Players chips, OwedRow with Remind and
  Mark cash paid, which asks first and reloads the figures). `Planner.tsx`,
  `Outstanding.tsx`; 10 Vitest tests in `Outstanding.test.tsx`.
- `npm run gen:api` regenerated `frontend/src/api/schema.d.ts`.
- Provisional choices in docs/OPEN_QUESTIONS.md and docs/DECISIONS.md "Chunk 27".

### Not built

- Export to CSV / Excel (chunk 28).
- Tapping a planner week to filter the Outstanding list to that week.
- Friendly fees and Booking Users on the Outstanding list; withdrawn Teams that owe.
- A limit on how often an Admin can Remind.

### By hand

- Nothing for this chunk. Review the provisional definitions in docs/OPEN_QUESTIONS.md
  "Chunk 27" (how fees are spread over weeks, who counts as a Player who owes, Remind).

### Checks

- make test: 956 passed.
- make lint: all checks passed, 184 files formatted.
- npm test: 56 files, 334 tests passed.
- npm run build: built (existing chunk-size warning only).
