# Chunk 22: Friendly fees

Unattended run, 2026-10-23. PRD: FR-24 (friendly fee, who pays it per match, the Captain who
receives the Barcode), FR-49 (friendly income its own line), FR-43/FR-52 (credit on a
cancelled match), NFR Barcode integrity.

## Plan

Backend:
- `FriendlyFee` (fixtures app): one per friendly (`FixtureFallback` with outcome friendly),
  set by an Admin of the Fixture's Club: `fee` (Decimal rand, 0 or more; the form starts at
  the club's `friendly_fee`), `payer` (borrowed Players, the Team's Players, the club/manager)
  and `captain` (the Player who receives the Barcode), with who set it and when.
  - Set while the match is a friendly for that kick-off and kick-off is still to come.
  - "The Team's Players" only when a Team is still in (FR-17); with both Teams out there is
    no Team, so 400.
  - Fee and payer are fixed once any friendly payment stands (409); the Captain can change.
  - Captain: a Player who plays in the friendly: one who joined (confirmed the invite) or a
    current member of the remaining Team.
- Money (`ledger.services`): friendly payments are ledger PAYMENT entries in the `friendly`
  category for the friendly's Fixture, subject the paying Player, on no Team's account (so a
  Team's league balance and Barcode are untouched). `friendly_paid(fixture)` sums them.
  Due = the fee; outstanding = fee less paid. The club/manager paying, or a fee of R 0, means
  nothing is collected from Players.
  - An Admin records cash for the friendly from one of the payers (borrowed: Players who
    joined from outside the Teams; Team: current members of the remaining Team), never more
    than is outstanding.
  - A friendly that is later cancelled returns these payments as Player credit through the
    existing `cancel_match` / `return_fixture_payments`.
- Barcode: a friendly's Barcode is tied to the friendly (`Barcode.friendly`, new, exclusive
  with `team`; `team` becomes nullable; signed over the friendly too). Issued when the
  friendly is settled (paid, free or paid by the club) and has a Captain; the Captain is told.
  A new Captain revokes the old Barcode and gets a new one. Valid while the match is still a
  friendly for that kick-off, not past, and settled. At the gate: the same today / single use
  checks; a Team's own league Barcode no longer lets it into a match that became a friendly.
- API:
  - `GET/POST /api/v1/clubs/{club_id}/fixtures/{id}/friendly/` (Admin): fee terms, totals,
    payments, who can pay, who can captain, the Barcode's state.
  - `POST /api/v1/clubs/{club_id}/fixtures/{id}/friendly/payments/` (Admin): record cash.
  - `GET /api/v1/me/friendlies/` and `GET /api/v1/friendlies/{fixture_id}/barcode/` (the
    friendly's Captain; Admins of the club can see the Barcode too; anyone else 404).
- `npm run gen:api`.

Frontend:
- Club fixture screen, Friendly section: fee form (fee, who pays, Captain), paid / due /
  outstanding, payments list, "Record cash" form.
- My matches: "Friendlies you captain" with a link to the friendly's Barcode screen
  (`/friendlies/:fixtureId/barcode`, PaymentTicket).
- Scan result and the Team Barcode screen handle a Barcode with no Team (a friendly).

Tests: pytest for each rule and permission (terms, payer groups, captain, cash, totals,
barcode issue/revoke/validity, gate, club isolation, credit on cancel); Vitest for the new
screens.

Later (not this chunk):
- Card payments (PayFast) and spending credit for a friendly fee: the Payment model is tied
  to a Team; needs a friendly subject on Payment.
- Friendly income lines in the Finances view (FR-49 display): finance tracker chunk.
- Charging borrowed Players in league matches (chunk 17 open question 1).

## Built

Backend:
- `FriendlyFee` (fixtures migration 0009): fee, payer, Captain, set by and when; read-only
  inline in the Django admin. `fixtures/friendlies.py`: `set_terms`, `record_cash`, payer
  groups, Captain candidates and totals.
- `ledger.services`: `record_friendly_payment` (category `friendly`, subject the Player, no
  Team), `friendly_payments`, `friendly_paid`.
- `Barcode.friendly` (barcodes migration 0003): `team` nullable, exactly one subject, one
  live Barcode per friendly; signed over the friendly (Team Barcodes sign as before).
  `barcodes.services`: `sync_friendly` (issue / revoke on a new Captain, tell the Captain),
  `current_for_friendly`, friendly validity in `status_of`, the gate check, a Team's own
  Barcode refused at a friendly (`friendly` state), `next_match` skips friendlies.
- API: `GET/POST /api/v1/clubs/{club_id}/fixtures/{id}/friendly/`,
  `POST /api/v1/clubs/{club_id}/fixtures/{id}/friendly/payments/`,
  `GET /api/v1/me/friendlies/`, `GET /api/v1/friendlies/{fixture_id}/barcode/`. Barcode
  and scan answers gained `holder` (Team name or "Friendly: Home vs Away"); `team` may be
  null. `npm run gen:api` run.

Frontend:
- Club fixture screen: "Friendly fee" section (`pages/fixtures/FriendlyFees.tsx`): fee,
  who pays, Captain form; paid / due / to pay; Barcode state; payments; Record cash.
- My fixtures: "Friendlies you captain" with a Barcode link;
  `/friendlies/:fixtureId/barcode` (`FriendlyBarcodePage`, PaymentTicket).
- Scan result and Team Barcode screens show `holder`; a "friendly" gate hint.

Tests: `backend/fixtures/tests/test_friendlies.py` (26: terms, payer groups, Captain rule,
kick-off, club isolation, cash rules, income category, no Team account change, fixed
terms, credit on cancel, Barcode issue / revoke / lapse / signature, Captain-only view,
gate single use, Team Barcode refused at a friendly). Vitest: `FriendlyFees.test.tsx`,
`FriendlyBarcodePage.test.tsx`, MyFixturesPage and ScanPage cases.

## Not built

- Card (PayFast) payments and credit spending for a friendly fee (needs a friendly subject
  on `Payment`).
- Friendly income lines in the Finances view (FR-49 display): the finance tracker chunk.
- Notifying the payers of the fee (PRD names none).

## By hand

- Nothing new. Review docs/OPEN_QUESTIONS.md "Chunk 22: Friendly fees", especially what
  "the club/manager pays" means and whether Players should pay friendly fees by card.

## Results

- make test: 829 passed
- make lint: ruff check and format clean
- npm test: 276 passed
- npm run build: built

## Review (independent, unattended)

Checked against the chunk prompt and CLAUDE.md: money is Decimal (serializers, service
checks, ledger `_money`), every endpoint is club-scoped (`ClubAdminMixin`) or limited to the
Captain / the club's Admins (404 otherwise), the default fee comes from club settings,
friendly payments are new append-only ledger entries in the `friendly` category, only the
Captain is notified, the UI uses `la-` components and tokens only, `gen:api` output is in
the commit, nothing from later chunks (PayFast for friendlies, Finances lines) was built.

Fixed:
- Gate: a friendly was let in once per Barcode, not once per friendly. After the Captain
  was changed (old Barcode revoked, new one issued) the new Captain's Barcode passed the
  gate again for the same match. `_at_the_gate` now checks for an earlier paid scan of any
  Barcode of that friendly (NFR Barcode integrity). Test added.
- Friendly fee screen decided whether cash could be recorded from `Number(outstanding)`;
  it now uses the backend's `settled` flag.
- Added a test that an Admin can revoke a friendly's Barcode through the existing revoke
  endpoint (no Team on it).

Noted, not changed:
- A Captain stays Captain if they later leave the remaining Team; the Admin can change it.
- The payment list shows the raw method ("cash"); only cash exists for friendlies now.

Review results: make test, make lint, npm test and npm run build all pass (see below).

- make test: 831 passed
- make lint: ruff check and format clean
- npm test: 276 passed
- npm run build: built
