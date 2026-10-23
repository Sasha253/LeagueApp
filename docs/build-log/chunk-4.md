# Chunk 4: Import Nights and Divisions from Excel

Unattended run, 2026-10-23. PRD: FR-39.

## Plan

The chunk was already built in the working tree, uncommitted, alongside chunk 5. This run
checks it against the chunk prompt, separates it from chunk 5, and commits chunk 4 alone.

- Models: none new. Night and Division from chunk 3 are reused.
- Reading files: `backend/core/tables.py` reads .xlsx (first sheet) and .csv (comma,
  semicolon or tab), matches headers loosely, limits 5 MB and 500 rows.
- Rules: `backend/clubs/imports.py` plans every row (preview, writes nothing) and applies a
  plan with no errors. Matching on Night and Division name (case-insensitive) makes
  re-importing idempotent. Templates as .xlsx (with a help sheet) and .csv.
- Endpoints (Club Admins only):
  - `POST /api/v1/clubs/{club_id}/imports/nights-divisions/preview/`
  - `POST /api/v1/clubs/{club_id}/imports/nights-divisions/commit/` (one transaction,
    club row locked, 400 with the rows if any has an error)
  - `GET /api/v1/clubs/{club_id}/imports/nights-divisions/template/?file_type=xlsx|csv`
- Screen: `frontend/src/pages/club/ImportNightsPage.tsx` (upload, preview with row-level
  errors, confirm, done), linked from the Nights and Divisions page. Template download
  goes through `frontend/src/native/files.ts`.
- Tests: `backend/clubs/tests/test_import_nights.py` (rules, all-or-nothing, re-import,
  club isolation, permissions, templates) and `ImportNightsPage.test.tsx`.

Later (not in this chunk): saving the template inside the installed app (Capacitor
Filesystem and Share plugins); the Fixtures import (FR-53, chunk 7) reuses `core/tables.py`.

## Result

- Built: everything in the plan above. Decisions are in docs/DECISIONS.md under
  "Import Nights and Divisions (chunk 4)".
- Not built: saving the template file in the installed app (it asks the Admin to use a
  browser); `max_teams` on a Division belongs to chunk 5 and is not read by the import.
- By hand: nothing for this chunk.
- Checks: make test 119 passed; make lint clean; npm test 70 passed; npm run build OK.

## Review (unattended, 2026-10-23)

Plan: compare c6c627f with the chunk 4 prompt and CLAUDE.md rules, run the four checks,
fix real defects only, and commit the fix without the uncommitted chunk 5 work in the tree.

Checked and fine:
- Scope: only FR-39. No Teams, Fixtures, ledger or notifications code. `max_teams` and
  `backend/teams/` in the working tree are chunk 5 and stay uncommitted.
- Club isolation: every endpoint uses `ClubAdminMixin` (`IsClubAdmin` on the URL's club);
  plan and apply read and write only that Club's Nights and Divisions. Tests cover other
  clubs' Admins, Referees and anonymous users, and an import not touching another club.
- Money: league fees parsed to `Decimal`, quantized to cents, never float; shown with
  `formatRand`. Configurable values: a blank Min players takes the club's setting, not a
  constant. No ledger or notification changes.
- All or nothing: commit plans again under a row lock on the Club inside one transaction.
- UI: design-system classes only; the FilePicker is listed as a proposed component.
- gen:api: schema.d.ts at c6c627f matches the chunk 4 endpoints.

Fixed:
- Matching could update the wrong Division. Names are unique per Night only as typed, so a
  Night can hold "Division A" and "division a"; the case-insensitive lookup kept whichever
  came last, so a row for one could silently change the other. A row now takes the
  Division with exactly its name, else a single case-insensitive match; several matches
  is a row error. Regression test:
  `test_divisions_differing_only_in_case_are_matched_exactly_or_refused`.

Noted, not changed:
- A crafted or bloated .xlsx (styled cells far down the sheet) makes the reader walk many
  blank rows before the 500-row limit applies. It is Admin-only and bounded by 5 MB, so it
  was left as is.
- "Choose another file" stays enabled while a commit is saving. Harmless.

Checks after the fix: make test 158 passed; make lint clean; npm test 70 passed; npm run
build OK. (The backend count includes the uncommitted chunk 5 tests in the tree.)
