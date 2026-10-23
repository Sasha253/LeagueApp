# Chunk 7: Fixtures and Admin fixture import

Unattended run, 2026-10-23. PRD: "Match lifecycle" intro and FR-53. Screens.md: Admin 2
(Fixtures), Player 1 and 2 (Matches, Match detail) as far as this chunk goes.

## Plan

New app `backend/fixtures/`.

Models:
- `Fixture`: Club, Season, Division (its Night is the Division's), pitch (`Field`), kick-off
  (UTC), home and away Team, `friendly_eligible` (with who set it and when), status.
- Status state machine in `fixtures/lifecycle.py`: scheduled, confirming, ready, one team
  out, replacement offered, friendly, cancelled, played. One table of allowed transitions;
  `transition()` refuses anything else, and is the only thing that changes a status.
- `FixtureTransition`: append-only log of every status change (from, to, when, the user
  who caused it or null, the cause: Admin, Captain, import, checkpoint or system, and a
  note). A Fixture's creation is logged as its first transition, into scheduled.

Import (same flow as chunk 4, reusing `core/tables.py`):
- Columns: Date, Time, Night (optional, must match the date), Division, Pitch, Home, Away,
  Friendly eligible (optional yes/no). One Season per file, chosen on the screen.
- Matching: a row is the same Fixture when Division, Home, Away and kick-off match, so
  re-importing creates nothing twice. Only the friendly-eligible flag can change on
  re-import; a different pitch is an error (that is a reschedule, chunk 16).
- Row errors: unknown Division, Team, or pitch; Team not confirmed or not in that Division
  and Season; same Team twice; kick-off outside the Season, in the past, or not on the
  Night's weekday; pitch or Team already playing at that kick-off (in the file or already
  scheduled).
- Endpoints (Club Admins only): `POST /api/v1/clubs/{club_id}/imports/fixtures/preview/`,
  `.../commit/` (one transaction, all or nothing), `GET .../template/?file_type=`.

Other endpoints:
- `GET /api/v1/clubs/{club_id}/fixtures/?season=&night=&division=&status=` (Admin list)
- `GET /api/v1/clubs/{club_id}/fixtures/{id}/` (Admin detail with the transition log)
- `PATCH /api/v1/clubs/{club_id}/fixtures/{id}/` (`friendly_eligible` only)
- `GET /api/v1/me/fixtures/?when=upcoming|past` (Fixtures of the Player's current Teams)
- `GET /api/v1/fixtures/{id}/` (a Player in either Team)

Screens (frontend/src/pages/fixtures/):
- Admin Fixtures `/clubs/:clubId/fixtures`: Season and Night chips, by date, then Division;
  link to Import.
- Admin Fixture `/clubs/:clubId/fixtures/:id`: kick-off, teams, pitch, Referee, status,
  friendly-eligible switch, history.
- Admin Import Fixtures `/clubs/:clubId/fixtures/import`: Season, template, upload,
  preview, confirm.
- My fixtures `/fixtures` (Players and Captains): upcoming and past.
- Fixture `/fixtures/:id`: kick-off, teams, pitch, status.
- Links from Profile (My fixtures for Players, Fixtures for Admins).
- `formatTime()` and `formatMoment()` in `format.ts`: Africa/Johannesburg, 24-hour.

Tests: pytest for the state machine, the import rules, idempotent re-import, all or
nothing, club isolation and permissions on every endpoint; Vitest for every screen.

Later (not in this chunk): the checkpoints that move a Fixture through its states (chunks
11 to 16), cancel and reschedule screens (chunk 16), adding or deleting one Fixture by hand,
the Tonight view, squad and payment progress on match cards, tab bar.

## Result

Built:
- Backend app `backend/fixtures/`: `Fixture` and the append-only `FixtureTransition` log
  (migration 0001), the state machine and the friendly-eligible rule in `lifecycle.py`, and
  the import in `imports.py`, reusing `core/tables.py` and the chunk 4 weekday parser.
- Endpoints: Admin list, detail with history, and `PATCH` friendly-eligible under
  `/api/v1/clubs/{club_id}/fixtures/`. Import preview, commit and template under
  `/api/v1/clubs/{club_id}/imports/fixtures/`. `GET /api/v1/me/fixtures/?when=` and
  `GET /api/v1/fixtures/{id}/` for Players and Captains. Django admin shows Fixtures
  read-only. `npm run gen:api` was run, and the import action enums now have their own
  names (`ImportActionEnum`, `FixtureImportActionEnum`).
- Screens (`frontend/src/pages/fixtures/`): Admin Fixtures (Season and Night chips, by
  day), Admin Fixture (match card, pitch and Referee, Friendly-eligible chip, history),
  Import fixtures (Season, templates, upload, preview, confirm), My fixtures (upcoming
  match cards, past list), Match (your team and opponent, pitch, league, status). Profile
  links to My fixtures (Players) and Fixtures (Admins). `formatTime` and `formatMoment`
  are in `format.ts`. MatchCard link is a proposed component.
- Tests: `backend/fixtures/tests/` (every status pair, the log, import rules, re-import,
  all or nothing, date forms, club isolation, permissions); Vitest for each new screen, the
  Profile links and the time formats.

Not built: the Later list above. No endpoint changes a status yet: the checkpoints and
Admin actions of chunks 11 to 16 call `lifecycle.transition()`.

By hand: nothing for this chunk. Review the provisional choices in docs/OPEN_QUESTIONS.md
under "Chunk 7".

Checks: make test 301 passed; make lint clean; npm test 126 passed (26 files);
npm run build ok.
