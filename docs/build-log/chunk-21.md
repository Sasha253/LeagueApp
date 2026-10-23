# Chunk 21: Gate scanning

Unattended run, 2026-10-23. PRD: FR-23 (Referees and Admins scan the Barcode at the entrance;
the app shows whether the Team has paid), FR-6, NFR Barcode integrity, Screens.md Admin 9 and
Referee 2, design/src/screens/f13-scan.mjs (Key moment 3).

## Plan

Backend (`barcodes`):
- `services.scan` becomes the gate check. On top of chunk 20's `status_of` (genuine, not
  revoked, not past, Team active and paid) it decides the match the Barcode is let in for:
  - per-match Barcode: its own match; season Barcode: the Team's match today (the first
    one not cancelled, played or with both Teams out).
  - When the gate names a match (`fixture`, optional), the Barcode must be for it (per-match)
    or its Team must play in it (season).
  - The match must be today (South African date): an earlier or later match's Barcode reads
    "Not paid" with the date.
  - The match must still be on (not cancelled, played, both Teams out) and the Team not
    ruled out of it at T-6h (`TeamReadiness` outcome `out`).
  - Single use: a Barcode lets its Team in once per match. A second scan reads "Not paid:
    already scanned at 19:21 by <name>". The Barcode row is locked while checking, and a
    partial unique constraint (one `paid` scan per Barcode and match) backs it up.
- Every scan is still logged (`BarcodeScan`), now with the match it was checked against.
- API: `POST /api/v1/clubs/{club_id}/scans/` for the club's Admins and Referees
  (`IsClubAdminOrReferee`; anyone else 403). Body: `code`, `method` (camera/manual),
  optional `fixture` (must be this club's). Answer: paid, state, reason, the code as printed,
  Team, match (teams, kick-off, pitch), validity (this match only / until date), and for a
  paid result what the Team paid (amount and methods).
- Migration for the constraint. `npm run gen:api`.

Frontend:
- `frontend/src/native/scanner.ts`: `canScan()` and `scanBarcode()` with the official
  `@capacitor/barcode-scanner` plugin (its own full-screen camera with torch, Code 128 hint),
  loaded only in the installed app; in a browser the screen offers manual code entry.
- `/clubs/:clubId/scan` (ScanPage): in the app the camera opens straight away, with "Enter
  code instead"; in a browser the code field ("Check code"). The result: large Paid / Not
  paid (`la-result`), Team, match, reason, Barcode code, valid for, paid; "Scan next" and
  "Enter code".
- Profile: "Scan" link for each club where the user is Admin or Referee.
- Native projects: iOS `NSCameraUsageDescription`, Android `CAMERA` permission; `cap sync`.
- Proposed styles `la-result` and `la-kv` copied from design/src/proposed.css.

Tests: pytest for each gate rule (right match, today, single use, ruled out, match off,
season Barcodes, races via the constraint), permissions and club isolation; Vitest for the
scanner wrapper (native, cancel, denied, browser) and the scan screen (camera, manual, Paid,
Not paid, errors) and the Profile link.

Later (not in this chunk):
- The Referee's Tonight (only their pitch's matches) and the tab bar per role.
- Picking the match on the scan screen (the API already takes `fixture`).
- A scan history screen for Admins (the log is stored).
- Booking Barcodes at the gate (chunks 23/24), friendly-match Barcodes (chunk 22).
- A custom camera overlay with the design's framed scan area (the plugin brings its own).

## Result

Built:
- Backend (`barcodes`): `services.scan` is now the gate check (FR-23). On top of chunk 20's
  validity it picks the match (the Barcode's own, the one the gate names, or for a Season
  Barcode the Team's match today), and reads Not paid with a reason when the match is not
  this one, not today, off (cancelled, played, both Teams out), the Team was ruled out at
  T-6h, or the Barcode already let the Team in for that match. The Barcode row is locked
  during the check and a partial unique constraint (`one_paid_scan_per_barcode_and_match`,
  migration 0002) keeps it single-use under two gates at once. Every scan is logged with
  the match it was checked against.
- API: `POST /api/v1/clubs/{club_id}/scans/` for the club's Admins and Referees (others
  403), body `code`, `method` (camera/manual), optional `fixture` (this club's only).
  Answer: paid, state (`BarcodeScanStateEnum`), reason, code as printed, Team, match,
  mode and valid-until, and on Paid the amount and methods paid. Throttled per user
  (`BARCODE_SCAN_THROTTLE_RATE`, default 60/min, in `.env.example`). schema.d.ts
  regenerated.
- 29 new pytest tests (`barcodes/tests/test_gate.py`, `test_scan_api.py`): each gate rule,
  Season Barcodes, single use including the two-gates race and the constraint, every
  permission and club isolation.
- Frontend: `frontend/src/native/scanner.ts` (`canScan`, `scanBarcode`) with the official
  `@capacitor/barcode-scanner` (Code 128, torch, loaded only in the app); the Scan screen
  (`/clubs/:clubId/scan`): camera straight away in the app, typed code as the fallback and
  in a browser, and a large Paid / Not paid result with Team, match, reason, code, validity
  and paid amount, "Scan next" and "Enter code". "Scan" links on Profile for each club
  where the user is Admin or Referee. Proposed styles `la-result`, `la-kv`. 14 new Vitest
  tests.
- Native: iOS `NSCameraUsageDescription`, Android `CAMERA` permission (camera not
  required), `npx cap sync` run (Package.swift and Gradle list the plugin).

Not built: the Later list above.

By hand:
- Rebuild the native apps (Xcode, Android Studio) to include @capacitor/barcode-scanner,
  then scan a Captain's Payment Barcode from another phone's screen at a real gate light
  level, with and without the torch; check the camera permission prompt text.
- Optionally set `BARCODE_SCAN_THROTTLE_RATE` per environment.

Checks: make test 800 passed; make lint clean; npm test 267 passed; npm run build ok.
