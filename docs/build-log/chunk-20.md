# Chunk 20: Payment Barcodes

Unattended run, 2026-10-23. PRD: "Barcode authorisation" table, "Payments, authorisation and
accounting", NFR Barcode integrity, Decisions table ("Barcode validity with the gateway: Per
match"). Screens.md Captain 6 "Payment Barcode" (`PaymentTicket`, valid for this match only),
design/src/screens/f13-scan.mjs (10-character code printed under the barcode, "RL 2710 4419").

## Plan

Backend, new app `barcodes`:
- `Barcode`: club, team (one subject; Bookings come in chunk 23/24 as a second, exclusive
  subject), mode (`match` in gateway mode, `season` in cash-only mode), fixture (match mode)
  or season (both), a 10-character code (Crockford base32) that is unique, a random nonce,
  issued_at/issued_by (empty when the app issued it), revoked_at/revoked_by/revoke_reason.
  Never deleted; only revocation changes it.
- Signed: the code is the first 50 bits of an HMAC-SHA256, keyed by `BARCODE_SIGNING_KEY`
  (env; falls back to a salted key derived from `DJANGO_SECRET_KEY`), over the nonce and
  the whole subject (club, team, mode, fixture, season). A row whose subject was changed, or
  a row added without the key, fails the signature check. Unguessable: 50 random-looking
  bits per code, looked up only by signed-in Referees and Admins (chunk 21).
- `BarcodeScan`: every scan logged, append-only (club, barcode or none, the code as
  entered, method camera/manual, who, when, result paid/not paid, reason, fixture).
- Services: `issue_for(team, by=None)` (when the Team is paid: gateway mode, a Barcode for
  the Team's current match; cash-only mode, one for the rest of the Season; revokes an
  earlier active Barcode for the same scope when an Admin reissues), `current_for(team)`
  (the Captain's Barcode now, issuing it when the Team is paid and has none for this match),
  `status_of(barcode)` (valid, revoked, expired, unpaid, signature), `revoke(...)`,
  `check(code, club)` and `log_scan(...)` (the scan endpoint and screen are chunk 21).
- `team_paid` receiver issues the Barcode and sends the Captain an Update notification.
- API:
  - `GET /api/v1/teams/{id}/barcode/`: the Captain (and the club's Admins): the current
    Barcode or why there is none (unpaid, no match coming up).
  - `GET /api/v1/teams/{id}/barcodes/`: Admins of the club: all the Team's Barcodes, with
    status and scan count.
  - `POST /api/v1/teams/{id}/barcodes/`: an Admin issues or reissues (409 when unpaid).
  - `POST /api/v1/barcodes/{id}/revoke/`: an Admin of the club, with a reason.
  - Anyone else gets 404.
- `npm run gen:api`.

Frontend:
- `components/PaymentTicket.tsx` from the design system's `la-ticket` classes, with a real
  Code 128 barcode (`components/code128.ts`, rendered as SVG bars).
- `/teams/:teamId/barcode`: the Captain's Payment Barcode (ticket, "valid for this match
  only" / "valid until <date>", or the reason there is none, with Pay my share).
- Team screen: "Payment Barcode" button for the Captain.
- Admin Team payments screen: the Team's Barcodes, Issue/Reissue and Revoke (with reason).

Tests: pytest for issuing (both modes, paid only, the signal), signing and forgery,
uniqueness, current match choice and expiry, revocation, scan logging, every permission and
club isolation; Vitest for code128, the ticket, the Captain screen and the Admin actions.

Later (not in this chunk):
- Scanning endpoint and screen, single-use and right-Fixture checks (chunk 21).
- Booking Barcodes (chunks 23/24), friendly-match Barcodes and the friendly Captain (chunk 22).
- Max brightness and keep-awake while the ticket is open (needs a Capacitor plugin).
- T-6h readiness reading the Barcode instead of the ledger (chunk 13 note).

## Result

Built:
- Backend app `barcodes`: `Barcode` (one Team; match or Season mode; signed 10-character
  code; never deleted, only revoked; one live Barcode per Team and match, or per Team and
  Season) and `BarcodeScan` (append-only log of every scan). `signing.py` (HMAC-SHA256
  over nonce and subject, keyed by `BARCODE_SIGNING_KEY`; normalising typed codes).
  `services.py`: `issue_on_payment` (the `team_paid` receiver; tells the Captain),
  `current_for`, `issue` (Admin, reissue revokes the live one), `revoke`, `status_of`,
  `next_match`, `scan` (checks and logs, club-scoped). Read-only Django admin.
- API: `GET /api/v1/teams/{id}/barcode/` (Captain and the club's Admins),
  `GET`/`POST /api/v1/teams/{id}/barcodes/` and `POST /api/v1/barcodes/{id}/revoke/`
  (the club's Admins); 404 for anyone else. schema.d.ts regenerated.
- Settings: `BARCODE_SIGNING_KEY` (base: optional, falls back to a key derived from
  `DJANGO_SECRET_KEY`; production: required). `.env.example` updated.
- 64 new pytest tests (`barcodes/tests/`): signing and forgery, issuing in both modes,
  paid only, the next match, expiry, reversals, revoking and reissuing, unique codes,
  scan logging and club isolation, every permission.
- Frontend: `PaymentTicket` (design system `la-ticket`, with a real Code 128 barcode from
  `components/code128.ts`), the Captain's Payment Barcode screen (`/teams/:teamId/barcode`,
  linked from the Team screen for the Captain), and the Admin's Payment Barcodes section on
  a Team's payments screen (list with state, Issue/Reissue, Revoke with reason).
  15 new Vitest tests.

Not built: the Later list above (scanning endpoint and screen are chunk 21).

Checks: make test 769 passed; make lint clean; npm test 253 passed; npm run build ok.

By hand:
- Set `BARCODE_SIGNING_KEY` (a long random value) in every deployed environment;
  production refuses to start without it. Changing it later invalidates every Barcode.
- Rebuild the native apps after this chunk to try the ticket on a phone, and check a
  phone camera reads the Code 128 at normal brightness.
