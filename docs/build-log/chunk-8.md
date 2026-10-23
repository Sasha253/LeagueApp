# Chunk 8: Ledger and credit

Unattended run, 2026-10-23. PRD: FR-43, FR-46, FR-50, FR-52. Backend only; no screens in
this chunk.

## Plan

New app `backend/ledger/`.

Model `LedgerEntry` (append-only):
- Club, kind (charge, payment, credit, refund, reversal), method (card, cash, credit; empty
  for charges and credits), category (league, friendly, booking: FR-49 needs them apart),
  amount (Decimal rand, always above 0; the kind gives the sign).
- Subject: Team, Player or Booking User, with `team` and `user` links. A Player's payment
  names both: the Player who paid and the Team paid for.
- Related Fixture (the Booking link comes with chunk 23), `reverses` (the entry a reversal
  undoes, at most one reversal each), `source` (the payment a credit was returned from),
  reason, recorded by (empty when the app did it), created at.
- No update or delete: `save()` refuses an existing row, `delete()` refuses, and the
  queryset refuses `update()`, `delete()` and `bulk_update()`. Django admin is read-only.
  The API is read-only.

Services (`ledger/services.py`), the only way entries are written:
- `charge`, `charge_league_fee` (idempotent, the Division's effective league fee),
  `record_payment` (card or cash, by a Player or for the whole Team), `issue_credit`,
  `return_as_credit` (credit goes back to whoever paid, FR-52), `spend_credit` (a payment by
  credit), `reverse`.
- Balances computed from entries: `team_balance` (due, paid by method, outstanding),
  `player_credit` (per Club), `team_credit`.
- The league fee is charged when the Admin confirms a Team; a data migration charges Teams
  already active.

Read-only endpoints:
- `GET /api/v1/me/credit/` (a Player's credit, per Club, with its entries)
- `GET /api/v1/teams/{id}/credit/` (that Team's Captain only)
- `GET /api/v1/teams/{id}/balance/` (that Team's Captain, or an Admin of its Club)

Tests: pytest for every service rule, append-only enforcement (ORM, queryset, admin, API),
balances, isolation and permissions on each endpoint.

Later (not in this chunk): card payments and refunds through PayFast (chunks 18, 24), the
Booking link and booking charges (chunks 23, 24), credit on cancellation (chunk 15),
friendly fees (chunk 22), the Finances view and Mark cash paid (finance chunks), screens.

## Result

Built:
- Backend app `backend/ledger/`: the append-only `LedgerEntry` (migration 0001) and a data
  migration (0002) that charges the league fee to Teams already active. Save-after-create,
  delete, and queryset `update`, `delete`, `bulk_update` and `update_or_create` all
  refuse. The Django admin is read-only, with no actions. DB checks: amount above zero, the
  subject's Team or user is named, and a reversal names the entry it undoes (one-to-one).
- `ledger/services.py`: `charge`, `charge_league_fee`, `record_payment`, `issue_credit`,
  `return_as_credit`, `spend_credit` and `reverse`, plus the balances `team_balance` (due,
  paid by card, cash and credit, outstanding), `team_credit`, `player_credit` and
  `user_credit`. Floats are refused, amounts are to the cent.
- `teams.rules.confirm_team` now charges the league fee; with no fee set, it refuses (409).
- Read-only endpoints: `GET /api/v1/me/credit/`, `GET /api/v1/teams/{id}/credit/` (Captain
  only), `GET /api/v1/teams/{id}/balance/` (Captain or the Club's Admins). Others get 404.
  `npm run gen:api` was run; the enums are `LedgerKindEnum`, `LedgerMethodEnum`,
  `LedgerSubjectEnum`, `LedgerCategoryEnum`.
- Tests: `backend/ledger/tests/` (55): every money rule, credit routing and spending,
  reversals, append-only in the ORM and admin, the API's permissions, isolation and that it
  only reads.

Not built: the Later list above. No screens in this chunk, so no new Vitest files.

By hand: nothing. Review the provisional choices in docs/OPEN_QUESTIONS.md under
"Chunk 8", especially credit per club (open question 6).

Checks: make test 356 passed; make lint clean; npm test 126 passed (26 files);
npm run build ok.

## Review (independent, unattended run)

Plan: compare commit 63e6bb3 with the chunk 8 prompt and CLAUDE.md rules, fix real
defects, run the four checks.

Checked and fine: money is Decimal throughout (floats refused, DB check amount > 0);
append-only enforced in save, delete, queryset update/delete/bulk_update/update_or_create,
read-only admin and read-only API; every entry has a Club and services refuse cross-club
records; credit endpoints are Captain-only / Player-only, balance is Captain or that Club's
Admins, others 404; league fee comes from Division/ClubSettings data, not a constant; no
notifications or UI in this chunk; nothing from later chunks; `npm run gen:api` leaves the
schema unchanged.

Defects fixed:
- A league fee of R 0 (allowed by ClubSettings/Division validators) made `confirm_team`
  crash with a 500: `charge_league_fee` passed 0 to `_money`, which refuses zero. Now a
  free league posts no charge and the Team is confirmed (same as the data migration,
  which already skipped a zero fee). Tests added.
- Race: `return_as_credit` checked "already reversed" before taking the payment's row
  lock, so a concurrent `reverse` of the same payment could commit in between and the
  money would be both reversed and returned as credit. The check now runs inside
  `issue_credit` under the lock (which `reverse` also takes first), so it covers direct
  `issue_credit(source=...)` calls too. Test added.

Checks after the fixes: make test 359 passed; make lint clean; npm test 126 passed;
npm run build ok.
