# Chunk 25: Finance tracker (backend)

PRD: FR-25, FR-26, FR-27, FR-49. Unattended run.

## Plan

- New app `finance/` with no models: every figure is computed from `LedgerEntry` rows
  (FR-50 entries stay append-only; nothing here writes).
- `finance/services.py`: grouped ledger sums (one query per category) netting reversals
  and refunds; per-Team league sums rolled up to Division, Night and the Season.
- Endpoints, Admins of the Club only (`IsClubAdmin`, club in the URL, other Clubs' ids 404):
  - `GET /api/v1/clubs/{club_id}/finance/summary/?season=&night=&division=` (FR-25, FR-49):
    Season totals per Night and Division: Teams, expected (league charges = Teams x fee),
    received split card / cash, paid with credit, returned as credit, outstanding, Team
    credit held; friendly income per Division and Night; booking income and club-wide
    Player / Booking User credit held as their own lines.
  - `GET /api/v1/clubs/{club_id}/finance/comparison/?season=1,2` (FR-27): income per
    Season and Night (league, friendly) plus bookings per Season.
  - `GET /api/v1/clubs/{club_id}/finance/teams/{team_id}/` (FR-26): Team ledger, due, paid,
    outstanding, by method, Team credit held, every line newest first (date, Player,
    amount, method, recorded by).
- Tests (pytest): totals from mixed card / cash / credit / refund / reversal entries,
  filters, friendly and booking lines separate, club isolation, Admin only (Player,
  Referee, other Club's Admin refused), Team ledger order and 404 across Clubs.
- `npm run gen:api` after the API change.

## Later (not in this chunk)

- Finances screens and Team ledger screen (chunk 26).
- FR-47 planner, FR-48 outstanding list with Remind / Mark cash paid, FR-51 export.

## Result

### Built

- `backend/finance/` (no models, read-only): `services.py` computes every figure from
  ledger entries with grouped sums, each less its reversals (and refunds for card/cash).
- `GET /api/v1/clubs/{club_id}/finance/summary/?season=&night=&division=` (FR-25, FR-49):
  per Night and Division: active Teams, expected (league fees charged), outstanding (Team by
  Team), Team credit held, league line and friendly line (card, cash, received,
  credit_spent, returned_as_credit); totals; booking line and Player / Booking User credit
  held club-wide (null when filtered); overall received.
- `GET /api/v1/clubs/{club_id}/finance/comparison/?seasons=` (FR-27): income per Season
  (oldest first) and Night: league, friendly, booking lines and received.
- `GET /api/v1/clubs/{club_id}/finance/teams/{team_id}/` (FR-26): due, paid, outstanding,
  paid by method, is_paid, Team credit held, every account line newest first (date,
  Player, amount, method, reason, recorded by).
- Admins of the Club only; other Clubs' records 404; nothing is written.
- 18 pytest tests in `backend/finance/tests/`; `npm run gen:api` regenerated
  `frontend/src/api/schema.d.ts`.
- Provisional choices in docs/OPEN_QUESTIONS.md and docs/DECISIONS.md (received excludes
  credit, expected from charges, overpaid Teams, credit held scope, booking Season scope,
  what a League is, Season required).

### Not built

- Finances and Team ledger screens (chunk 26).
- FR-47 planner, FR-48 outstanding list (Remind, Mark cash paid), FR-51 CSV / Excel export.

### By hand

- Nothing for this chunk. Review the provisional finance definitions in
  docs/OPEN_QUESTIONS.md "Chunk 25".

### Checks

- make test: 935 passed (before the docs-only changes).
- make lint: all checks passed, 181 files formatted.
- npm test: 52 files, 308 tests passed.
- npm run build: built.
