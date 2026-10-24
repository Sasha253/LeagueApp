# Chunk 28: Accountant export

PRD: FR-51 (with FR-50 append-only, FR-49 income lines, the money and time rules in
CLAUDE.md). Design: Screens.md Admin 5 ("Export to CSV / Excel"); the Finances nav's quiet
Export button in design/src/screens/f14-finances.mjs. Unattended run: the columns were
chosen without asking (docs/OPEN_QUESTIONS.md "Chunk 28: Accountant export").

## Plan

- No new models. `backend/finance/export.py` reads the Club's ledger entries recorded in a
  date range and writes them as CSV or Excel (openpyxl, already a dependency).
- Columns, one row per ledger entry, oldest first: Entry, Date, Time, Kind, Category,
  Method, Amount, Money in, Money out, Account, Team, Player or Booking User, Season,
  Night, Division, Fixture, Booking, Corrects entry, Credit from entry, Reason,
  Recorded by.
  - Date and Time: when it was recorded, South African time, "2026-10-27" and "19:40".
  - Amount: as recorded, rand, always above zero ("350.00"). Money in / Money out: only
    card and cash actually taken or paid back (payments in; refunds out; a correction of
    either the other way). Charges, credits and credit spent move no money: both empty.
- Endpoint, Admins of the Club only (`IsClubAdmin`, another Club 404):
  `GET /api/v1/clubs/{club_id}/finance/export/?starts_on=YYYY-MM-DD&ends_on=YYYY-MM-DD&file_type=xlsx|csv`
  (both days required and inclusive, South African days; `ends_on` not before `starts_on`).
  The file is an attachment named `ledger-<starts_on>-to-<ends_on>.<ext>`.
- Text cells that a spreadsheet would read as a formula (=, +, -, @, tab, CR) start with
  an apostrophe (CSV/formula injection).
- Excel: a "Ledger" sheet (real dates, money as numbers in a #,##0.00 format, header
  frozen) and an "About" sheet (Club, period, exported at, entries, what the columns mean).
  CSV: UTF-8 with BOM, same columns.
- Screen: Finances gets an Export link; `/clubs/:clubId/finances/export` has From and To
  dates (default: this month so far) and "Download Excel" and "Download CSV". Saving goes
  through `native/files.ts` (the installed app says to use a browser, as for templates).
- Tests: pytest for columns and values, money in/out per kind, range edges in SA time,
  club isolation, Admin only, bad ranges, formula escaping, the xlsx content; Vitest for
  the export screen. `npm run gen:api` after the API change.

## Later (not in this chunk)

- Saving files inside the installed app (Filesystem and Share plugins).
- A direct Xero hand-off (PRD lists Xero as the accountant's package; FR-51 asks only for
  CSV and Excel).

## Result

### Built

- `backend/finance/export.py` and `GET /api/v1/clubs/{club_id}/finance/export/
  ?starts_on=&ends_on=&file_type=xlsx|csv` (FR-51), Admins of the Club only: every ledger
  entry the Club recorded in the period (South African days, inclusive), oldest first, as
  Excel (Ledger sheet with real dates and #,##0.00 money, header frozen; About sheet with
  Club, period, exported at, entry count, currency and column meanings) or CSV (UTF-8 with
  BOM). Columns as in the plan; Money in / Money out for card and cash only. Text that a
  spreadsheet would run as a formula is escaped. Attachment `ledger-<from>-to-<to>.<ext>`.
- Query checked by `ExportQuerySerializer` (both days required, ISO dates, end not before
  start, xlsx or csv).
- Screen `/clubs/:clubId/finances/export` ("Export for accountant"), opened from an Export
  button on Finances: From and To (start on the South African month so far), Download
  Excel and Download CSV, API errors next to the fields; the installed app says to export
  from a browser.
- Tests: `backend/finance/tests/test_export.py` (15: columns and values, money in/out,
  friendly and booking rows, SA day edges, empty period, xlsx content, formula escaping,
  bad periods, Admin only, club isolation); `ExportPage.test.tsx` (6) and the Export link
  on Finances. `npm run gen:api` run.
- Decisions in docs/DECISIONS.md and docs/OPEN_QUESTIONS.md "Chunk 28: Accountant export"
  (provisional, unattended run): the columns were not confirmed by the user.

### Not built

- Saving the file inside the installed app (needs Filesystem and Share plugins).
- A Xero integration or Xero import layout; totals rows; a cap on period length.

### By hand

- Review the proposed columns (docs/OPEN_QUESTIONS.md, Chunk 28) with the club's
  accountant; changes are confined to `backend/finance/export.py`.

### Results

- make test: 971 passed. make lint: ruff check and format clean (after `ruff format`).
- npm test: 57 files, 340 tests passed. npm run build: built (chunk size warning only).
