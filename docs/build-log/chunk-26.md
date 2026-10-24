# Chunk 26: Finance tracker (UI)

PRD: FR-25, FR-26, FR-27, FR-49 (screens on the chunk 25 API). Design: Screens.md Admin 5
(Finances) and 6 (Team ledger); design/src/screens/f14-finances.mjs. Unattended run.

## Plan

- No backend change: the screens only call the chunk 25 endpoints (and the existing
  Seasons, Nights and team-payments lists) and draw what they answer. No sums in the app.
- `frontend/src/pages/finance/`:
  - `FinancesPage` (`/clubs/:clubId/finances`): Season, Night and Division filters
    (chips; Division only once a Night is picked); FinanceSummary card (expected,
    received, outstanding, Team credit held); league money by method (card, cash, credit
    used, returned as credit); income lines for League, Friendlies and Bookings, all
    income received, and Player / Booking User credit held; the Nights and Divisions
    breakdown; the Teams in scope, each opening its Team ledger; a link to the comparison.
  - `TeamLedgerPage` (`/clubs/:clubId/finances/teams/:teamId`): PaymentProgress, paid by
    method and Team credit held, then every entry newest first (date, Player, amount,
    method chip Card / Cash / Credit, recorded by, reason). Read-only.
  - `ComparisonPage` (`/clubs/:clubId/finances/compare`): Season chips (multi-select, all by
    default); per Season received and League / Friendlies / Bookings lines, Night by Night.
  - A Finances link for Admins on Profile.
- Tests (Vitest): each screen renders the API's figures as "R 18,550", filters send the
  right query, empty and 403 states, ledger order and method chips, comparison query.

## Later (not in this chunk)

- Week-by-week planner inside FinanceSummary and the Outstanding list with Remind / Mark
  cash paid (chunk 27, FR-47, FR-48).
- Export to CSV / Excel (chunk 28, FR-51).

## Result

### Built

- `frontend/src/pages/finance/FinancesPage.tsx` (`/clubs/:clubId/finances`, FR-25, FR-49):
  Season, Night and Division chips (opens on the running Season); FinanceSummary card
  (Expected, Received, Outstanding in pending ink, Team credit held, Teams count); league
  money by method (Card, Cash, Credit used, Returned as credit); income lines for League,
  Friendlies and Bookings (Bookings explained when a filter hides them), All income
  received, and Player / Booking User credit held; By Night and Division rows with a
  "R x to go" or Paid chip; the Season's active Teams in scope, each opening its ledger; a
  Compare Seasons link.
- `TeamLedgerPage.tsx` (`/clubs/:clubId/finances/teams/:teamId`, FR-26, FR-50):
  PaymentProgress, paid by method, Team credit held, overpaid note, every entry newest
  first (date and time, kind, Player, amount, Card / Cash / Credit chip, entry number,
  recorded by, reason). Read-only.
- `ComparisonPage.tsx` (`/clubs/:clubId/finances/compare`, FR-27): every Season by default,
  multi-select Season chips sent as `?seasons=`; per Season received, the three income
  lines and each Night's league and friendly income.
- Finances link for Admins on Profile; routes in `frontend/src/routes.tsx`.
- Money always through `formatRand` ("R 18,550"); dates "Tue 27 Oct", times 24-hour SAST.
- Vitest: 16 new tests in `frontend/src/pages/finance/` (figures, filters and their query,
  Team list scope, ledger order and chips, comparison query, empty, 403 and error states,
  opening Season) and the Profile link. No API change; `npm run gen:api` left the schema
  as it was.
- Provisional choices in docs/OPEN_QUESTIONS.md and docs/DECISIONS.md "Chunk 26".

### Not built

- Week-by-week planner in FinanceSummary and the Outstanding list with Remind / Mark cash
  paid (chunk 27). Export to CSV / Excel (chunk 28).
- Links to withdrawn Teams' ledgers (only active Teams are listed).

### By hand

- Nothing for this chunk. Review the provisional UI choices in docs/OPEN_QUESTIONS.md
  "Chunk 26".

### Checks

- make test: 935 passed.
- make lint: all checks passed, 181 files formatted.
- npm test: 55 files, 324 tests passed.
- npm run build: built (existing chunk-size warning only).

## Review (fix: chunk 26 review)

Checked commit 50d629d against the chunk prompt and CLAUDE.md.

- Money: every amount is an API decimal string shown through `formatRand`; no sums in
  the app. `Number()` is used only to compare a backend figure with zero (chips, captions).
- Club isolation: no backend change; the screens call the chunk 25 finance endpoints and
  `team-payments`, all `IsClubAdmin` and scoped to the URL's Club. 403 shows the
  "Only this club's Admins" state.
- Ledger: read-only screens; nothing edits or deletes an entry.
- Design system: only `la-` classes from bundle.css / proposed.css and type styles.
- Scope: no planner, Outstanding list or export (chunks 27, 28).
- No API change, so gen:api not needed.

Fixed:

- The Team ledgers list on Finances fetched every active Team of every Season and filtered
  in the browser. It now asks `team-payments` for the picked Season only (`?season=`),
  so the list stays bounded as Seasons pile up. Test asserts the query.

Checks after the fix:

- make test: 935 passed (backend unchanged by the fix).
- make lint: all checks passed, 181 files formatted.
- npm test: 55 files, 324 tests passed.
- npm run build: built (existing chunk-size warning only).
