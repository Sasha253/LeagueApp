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
