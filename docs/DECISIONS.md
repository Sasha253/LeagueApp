# Decisions

Newest first. Each entry: the date, what was decided, and why.

## 2026-10-25: One league import from Excel

Decided by @Sasha: an Admin imports their Seasons, Nights and Divisions, and Fixtures from
one Excel workbook. This replaces the separate Nights and Divisions import (chunk 4) and
Fixtures import (chunk 7); their row rules still apply, except where this entry says
otherwise.

- **One workbook, a sheet each:** sheets named Seasons, Nights and Divisions, and Fixtures,
  found by name without regard to case, spaces or punctuation. Any sheet may be left out,
  and other sheets are ignored. Excel (.xlsx) only, since a CSV holds one sheet; the CSV
  template and upload are gone. Limits: 5 MB a file and 1000 rows a sheet (was 500 a file).
- **API:** `POST /api/v1/clubs/{club_id}/imports/league/preview/` and `.../commit/`, and
  `GET .../template/` (Excel, with example rows that import as they are given a league fee
  and a pitch named Pitch 3). The `imports/nights-divisions/` and `imports/fixtures/`
  endpoints and their screens are removed. The screen is Club setup, Import from Excel
  (`/clubs/:clubId/setup/import`); Nights and Divisions and Fixtures link to it.
- **Sheets are read in order** (Seasons, then Nights and Divisions, then Fixtures), each
  checked against what the sheets before it add, so a new Season or Division can have its
  Fixtures in the same file. The import writes as it goes inside one transaction and rolls
  it back for a preview, or for a commit with any error, so all or nothing still holds.
- **Seasons sheet:** Season, Starts on, Ends on, all required. A Season is matched on its
  name, ignoring case and outer spaces. An existing Season takes the file's dates unless
  one of its Fixtures would then fall outside them (an error). An import never deletes a
  Season.
- **Fixtures sheet:** gains a required Season column, so one file can hold several Seasons.
  The Season is no longer picked on the screen.
- **Teams from the Fixtures sheet:** a Home or Away name the Division doesn't have that
  Season adds the Team: confirmed (decided by the importing Admin), with no Captain and no
  Players. As when an Admin confirms a request, it needs a league fee (the Division's or the
  club's), counts against the Division's `max_teams`, and is charged the league fee. A Team
  still waiting for the Admin is an error, as before.
- **First joiner is Captain:** a Player who asks to join a Team with no Captain and no
  Players joins at once as its Captain; the request comes back accepted. Players after
  them ask the Captain as usual.

## 2026-10-25: Superuser sees every club

A superuser (`is_superuser`, made with `createsuperuser`, never by sign-up) sees every Club
in the app and can open each one with full Admin powers. The user decided this; it is the
one exception to "Admins and Referees see only their Club's data".

- **Full Admin, no ClubRole:** a superuser passes every Admin and Referee check at every
  Club (`ClubRolePermission`, `User.holds_club_role`, `User.is_club_admin`,
  `User.club_ids_with_role`). They hold no ClubRole, so they are not on any Club's People
  list and get no Club's Admin or Referee notifications (targeting still reads ClubRoles).
- **API:** `GET /api/v1/clubs/` lists every Club (superuser only, 403 otherwise).
  `GET /api/v1/clubs/{club_id}/` names one Club for its Admins and Referees and for a
  superuser, so club screens show the right club name. `/auth/me/` says `is_superuser`;
  it is read-only there and on register.
- **App:** Profile shows "All clubs" to a superuser. All clubs (`/clubs`) lists every Club
  with the same shortcuts an Admin sees on Profile (Scan, Tonight, Fixtures, Team requests,
  Bookings, Payments, Finances, Club setup), built from existing `la-` components.

## 2026-10-24: Store release (chunk 29) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 29: Store release" and
docs/STORE_RELEASE.md.

- **App icon and splash (provisional, unattended run):** no logo exists, so the icon is a
  pitch outline in `accent` on the Night `ground`, no text and no crest, drawn from the
  tokens by `frontend/scripts/app-assets.mjs` (`npm run assets`). Splash: the same mark,
  small, on `ground` (iOS launch screen background, Android 12+ splash colour). Replace
  the mark when a brand one is made. *Superseded 2026-10-27: see "Logo" below.*
- **Version and build (provisional, unattended run):** `frontend/release.json` holds the
  version ("1.0.0") and one build number for both stores (iOS CURRENT_PROJECT_VERSION,
  Android versionCode). Profile and the privacy screen show "Version 1.0.0 (1)".
- **Android signing (provisional, unattended run):** a Play App Signing upload key, read
  only from `LEAGUEAPP_KEYSTORE_FILE`, `LEAGUEAPP_KEYSTORE_PASSWORD`,
  `LEAGUEAPP_KEY_ALIAS`, `LEAGUEAPP_KEY_PASSWORD`; keystores and Apple signing files are
  git-ignored.
- **Privacy policy (provisional, unattended run):** one text in `backend/core/legal.py`,
  served as data at `GET /api/v1/legal/privacy/` (the app's `/privacy` screen, open
  without signing in) and as a plain public page at `/privacy/` (the store URL). The
  operator's name and contact email come from `PRIVACY_OPERATOR_NAME` and
  `PRIVACY_CONTACT_EMAIL`. Written for POPIA; financial records kept as long as the law
  requires; the app is for adults, a Player under 18 needs a parent's or guardian's
  consent.
- **Permissions (provisional, unattended run):** camera text "League App uses the camera to
  scan Payment Barcodes at the gate. Nothing the camera sees is saved."; notifications use
  the system prompt right after sign-in, with no extra screen first.
- **Export compliance (provisional, unattended run):** `ITSAppUsesNonExemptEncryption`
  false (HTTPS only). iOS privacy manifest declares no tracking and the data in the policy.
- **Minimum Android version (provisional, unattended run):** Android 8.0 (API 26), not 7.0
  (24): `@capacitor/barcode-scanner` (chunk 21) needs 26 and the Android build failed
  without it.
- **Proposed component:** `la-link`, an inline text link in `accent-ink`, underlined
  (frontend/src/styles/proposed.css).
- **Not built (needed before review):** in-app account deletion and a real home screen;
  see docs/STORE_RELEASE.md section 7.

## 2026-10-24: Accountant export (chunk 28) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 28: Accountant export".

- **Export (FR-51) (provisional, unattended run):**
  `GET /api/v1/clubs/{club_id}/finance/export/?starts_on=&ends_on=&file_type=xlsx|csv`,
  Admins of the Club only. Every ledger entry the Club recorded in the period (South African
  days, both inclusive, by when it was recorded), one row each, oldest first. Corrections
  are their own rows (FR-50). Built in `backend/finance/export.py`.
- **Columns (provisional, unattended run):** Entry, Date, Time, Kind, Category, Method,
  Amount (R), Money in (R), Money out (R), Account, Team, Player or Booking User, Season,
  Night, Division, Fixture, Booking, Corrects entry, Credit from entry, Reason, Recorded by.
- **Money in a file (provisional, unattended run):** amounts are plain decimal rand
  ("18550.00") so spreadsheets and accounting packages read them as numbers; Excel shows
  them as #,##0.00. The "R 18,550" display rule is for screens. Money in / Money out are
  card and cash only: payments in, refunds out, a correction of either the other way;
  charges, credits and credit spent leave both empty.
- **Dates in a file (provisional, unattended run):** "2026-10-27" and "19:40" (South
  African time), not "Tue 27 Oct": an accountant's software sorts and imports ISO dates.
- **Formula injection (provisional, unattended run):** text starting with =, +, -, @, tab
  or CR gets a leading apostrophe in both formats.
- **Installed app (provisional, unattended run):** as for import templates, the export
  downloads only in a browser; the app says to use one.

## 2026-10-24: Outstanding list and income planner (chunk 27) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 27: Outstanding list
and income planner".

- **Planner (FR-47):** `GET /api/v1/clubs/{club_id}/finance/planner/?season=&night=&division=`.
  Weeks are the Season's own (week 1 from its first day, South African dates). Each Team's
  league fees charged are spread evenly over its Fixtures (not cancelled), to the cent;
  Teams with no Fixtures are "unscheduled". Each Team's payments (card, cash, credit,
  capped at what it was charged) cover its own Fixtures in date order; a week that has
  started and isn't covered is short. Totals: season expected (equal to the summary's
  expected), due to date, covered to date, behind, unscheduled, and card and cash received
  per week (money before or after the Season counts in its first or last week).
- **Outstanding list (FR-48):** `GET /api/v1/clubs/{club_id}/finance/outstanding/`, same
  filters. Active Teams that owe, largest first, with the first short planner week and the
  Players who still owe. Players who owe: their share (due over current Players, rounded up)
  less what they paid, never more than the Team owes, largest first. Friendly fees and
  Booking Users are not listed.
- **Remind:** `POST .../finance/outstanding/remind/` `{team_id, player_id?}`: an Update
  notification to the Team's Captain and Players who owe, or to the one Player, only those
  opted into the Team's Night (`targeting.payment_reminder_recipients`). The answer says who
  was told and who wasn't. No rate limit.
- **Mark cash paid:** `POST .../finance/outstanding/cash/` `{team_id, player_id?, amount}`:
  records exactly what the row owes as cash through `payments.services.record_cash` (so the
  Barcode follows as for any payment). Refused with 409 if `amount` isn't what is owed now.
- Admins of the Club only; another Club's Team is 404, a Player not in the Team 400.
- **Proposed components** (`frontend/src/styles/proposed.css`): OwedRow (`.la-owed`,
  `.la-owed__amount` in pending ink, `.la-owed__actions`), from the design's owedRow; the
  planner key swatches (`.la-planner__swatch-exp`, `.la-planner__swatch-got`) and the
  current week's axis number (`.la-planner__now`), which the design drew inline. Who owes
  is picked with ChoiceChips ("Teams · 2", "Players · 2") in place of the design's
  segmented control, which the frontend doesn't have yet.

## 2026-10-24: Finance tracker (UI) (chunk 26) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 26: Finance tracker
(UI)".

- **Screens (provisional, unattended run):** Finances (`/clubs/{id}/finances`, from an
  Admin's Profile), Team ledger (`/clubs/{id}/finances/teams/{team_id}`) and Compare Seasons
  (`/clubs/{id}/finances/compare`). They only draw the chunk 25 API's figures; nothing is
  added up in the app.
- **Opening Season (provisional, unattended run):** the earliest-starting Season that hasn't
  ended, else the latest. Night filter, then Division filter for that Night.
- **FinanceSummary totals (provisional, unattended run):** Expected (league fees charged),
  Received (league card and cash), Outstanding, Team credit held. Friendly and booking
  income are separate lines; "All income received" is the API's total.
- **Team ledgers (provisional, unattended run):** opened from the Season's active Teams on
  Finances; read-only, newest first, a reversal shown as "Correction of entry N" with its
  reason.
- **Proposed component:** MethodChip, the word Card, Cash or Credit in `.la-chip
  .la-chip--info` without an icon (a method is not a status), in
  `frontend/src/pages/finance/shared.tsx`. No new CSS.

## 2026-10-24: Finance tracker (backend) (chunk 25) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 25: Finance tracker
(backend)".

- **Computed from the ledger (provisional, unattended run):** the `finance` app has no
  models and writes nothing; every figure is a sum of ledger entries, each less its
  reversals. Admins of the Club only (`IsClubAdmin`); another Club's Season, Night,
  Division or Team is 404.
- **Figures (provisional, unattended run):** expected is the league fees charged to the
  Teams in scope (Teams x fee as charged), less reversed charges; card and cash are money
  taken by that method less refunds and reversals; received is card plus cash; credit spent
  and credit returned from payments are their own figures, never in received; outstanding
  is summed Team by Team, an overpaid Team owing nothing; credit held is the balance now.
- **Scope (provisional, unattended run):** league by the Team's Season, Night and Division;
  friendly by the Fixture's Season and Division; bookings by Bookings starting in the
  Season's dates (South African time), club-wide. Team credit per Division; Player and
  Booking User credit club-wide. Club-wide lines are null with a Night or Division filter.
- **Endpoints (provisional, unattended run):** `GET /api/v1/clubs/{id}/finance/summary/
  ?season=&night=&division=` (FR-25, FR-49; season required),
  `GET /api/v1/clubs/{id}/finance/comparison/?seasons=1,2` (FR-27: income per Season and
  Night; a "League" is a Night's league, no League model), and
  `GET /api/v1/clubs/{id}/finance/teams/{team_id}/` (FR-26: the Team ledger, newest first).

## 2026-10-24: Booking payments and cancellation policy (chunk 24) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 24: Booking payments and
cancellation policy".

- **No stored cards (provisional, unattended run):** FR-32 tokenisation is not built. At the
  club's payment cutoff (`booking_payment_cutoff_hours`, Celery Beat `bookings.run_payments`)
  the Booking User's credit at the club is spent first (FR-46) and they are asked to pay the
  rest by card on PayFast's hosted page (Pay on the booking), or in cash to the club, which
  an Admin records (FR-44). Card payments are offered only from the cutoff.
- **Policy engine (provisional, unattended run):** `bookings/policy.py`, every number from
  the club's settings. Windows: free (before the cutoff and before payment was ever taken),
  late (to the late-cancel hours), very late (until it starts), club. Cancelling returns a
  percent of what was paid as credit, never cash: 100% free, the late percent, the no-show
  percent, the club percent. Late reschedules: the allowed number, within the window days
  of the current start; none when very late. Shown before booking
  (`GET /api/v1/bookings/policy/`) and before cancelling or moving
  (`GET /api/v1/me/bookings/{id}/outcome/`, FR-45).
- **Club cancels (provisional, unattended run):** an Admin cancels a booking for the club
  until it ends, with a reason; the club percent comes back as credit. No card refunds in
  the app yet. Declining a paid move returns the club percent too.
- **No-shows (provisional, unattended run):** an accepted booking that ended without a Paid
  scan gets the no-show percent of what was paid as credit, once.
- **Money (provisional, unattended run):** booking payments, credit spent on a booking and
  credit returned from one are ledger entries naming the Booking (`LedgerEntry.booking`),
  subject Booking User, category `booking`. What a booking has paid is its payments less
  refunds, reversals and credit returned. A `Payment` is for a Team or a Booking (exactly
  one). Percentages round half a cent up.

## 2026-10-23: Bookings (chunk 23) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 23: Bookings".

- **Match length (provisional, unattended run):** a club setting `match_length_minutes`,
  empty until the Admin sets it; a league match holds its pitch that long from kick-off.
  Bookings need it and the booking hourly fee.
- **Slots (provisional, unattended run):** a Booking starts on the hour (South African
  time), still to come, for 1 to 24 whole hours, and ends by midnight. Pending and
  accepted Bookings and Fixtures that aren't cancelled hold a field; nothing may overlap
  them. The hourly fee is fixed on the Booking when requested; price = fee x hours.
- **Deciding (provisional, unattended run):** every Admin of the club gets the Booking
  Notification; the first answer (or the club's Bookings screen) decides it. The Booking
  User is told of the decision; the Admins of a cancelled accepted booking.
- **Cancel and reschedule (provisional, unattended run):** the Booking User cancels or
  reschedules before it starts; a reschedule waits for an Admin again and its Barcode is
  revoked until then. The policy outcomes are chunk 24.
- **A Booking's Barcode (provisional, unattended run):** a third exclusive subject (mode
  `booking`, no Season), issued on accept, revoked on cancel or reschedule. It counts at
  the gate only when nothing is owed (no booking payments until chunk 24), on its day,
  once, and only an Admin checks it.
- **Proposed components:** the day picker (`.la-days`, `.la-day`), start-time slots
  (`.la-slots`) and the hours stepper (`.la-stepper`), copied from design/src/proposed.css
  into `frontend/src/styles/proposed.css`.

## 2026-10-23: Friendly fees (chunk 22) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 22: Friendly fees".

- **FriendlyFee (provisional, unattended run):** one per friendly, set by an Admin of the
  Fixture's Club while it is a friendly and before kick-off: the fee for the whole match
  (Decimal rand, 0 or more, starting at the club's `friendly_fee`), who pays (the borrowed
  Players, the Team's Players, the club/manager) and the Captain (a Player who joined it,
  or a current Player of the Team still in it). Fee and payer are fixed once a payment
  stands.
- **Payers (provisional, unattended run):** borrowed Players are those who joined from
  outside the Team still in it; the Team's Players are that Team's current Players (not
  offered with both Teams out). The club/manager, or a fee of R 0: nothing is collected and
  the friendly counts as paid.
- **Friendly income (provisional, unattended run, FR-49):** cash recorded by an Admin from
  a payer, never more than still owed, as a ledger payment in the `friendly` category for
  the Fixture, subject the Player, on no Team's account. A cancelled friendly returns it as
  Player credit. Card payments for friendlies are not built yet.
- **The friendly's Barcode (provisional, unattended run):** a Barcode's subject is a Team
  or a friendly (exclusive, signed). Issued to the Captain once the friendly is settled,
  valid for that match while it is a friendly, once at the gate; a new Captain revokes the
  old one's. A Team's own Barcode doesn't count at a match that became a friendly. This
  widens CLAUDE.md's "tied to one Team or Booking" to "one Team, friendly or Booking".

## 2026-10-23: Gate scanning (chunk 21) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 21: Gate scanning".

- **Which match (provisional, unattended run):** a scan may name a match; otherwise a
  per-match Barcode is checked against its own match and a Season Barcode against its
  Team's match today.
- **Today only (provisional, unattended run):** the match must be today (South African
  date), still on (not cancelled, played or both Teams out), and the Team not ruled out of
  it at T-6h; otherwise Not paid with the reason.
- **Single use (provisional, unattended run):** a Barcode lets its Team in once per match
  (Season Barcodes once per match too). A second scan reads Not paid with when and by whom
  it was scanned. Locked check plus a unique constraint on Paid scans.
- **Who scans (provisional, unattended run):** every Admin and Referee of the club, at any
  of its matches; others 403. Only the club's own Barcodes are found. 60 scans a minute
  each (`BARCODE_SCAN_THROTTLE_RATE`).
- **Result (provisional, unattended run):** Paid / Not paid, Team, match, reason, code,
  validity, and on Paid the amount and methods the Team paid.
- **Camera (provisional, unattended run):** the official `@capacitor/barcode-scanner`
  plugin behind frontend/src/native/scanner.ts (its own camera view with torch); typing the
  code is the fallback and the only way in a browser. iOS `NSCameraUsageDescription` and
  Android `CAMERA` added.
- **Proposed component styles:** the scan result block (`.la-result`, `--paid`,
  `--notpaid`, `__word`) and the key-value row (`.la-kv`) copied from design/src/proposed.css
  into `frontend/src/styles/proposed.css`. The design's framed camera overlay (`.la-scan`)
  is not used: the plugin draws its own.

## 2026-10-23: Payment Barcodes (chunk 20) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 20: Payment Barcodes".

- **Validity (provisional, unattended run):** gateway mode gives a Barcode for the Team's
  current match (first match not cancelled or played, today or later, South African
  date); cash-only mode one for the rest of the Season. The mode is the club's when the
  Barcode is issued.
- **Issuing (provisional, unattended run):** only to a paid Team: automatically when it
  becomes paid (`team_paid`), on the Captain's first look for a later match, or by an Admin
  of its Club (issue or reissue, revoking the live one). The Captain is told with an Update
  notification.
- **Valid (provisional, unattended run):** genuine (signature), not revoked, not past its
  match or Season, Team active and still paid. Computed at every look and scan.
- **Signed code (provisional, unattended run):** 10 Crockford base32 characters, the first
  50 bits of an HMAC-SHA256 over a random nonce and the subject, keyed by
  `BARCODE_SIGNING_KEY` (environment). Shown as a Code 128 barcode with the code printed
  under it ("RK 2710 4419").
- **Revoking (provisional, unattended run):** Admins of the club, with a reason. Never
  replaced automatically.
- **Who sees it (provisional, unattended run):** the Captain and the club's Admins.
- **Scans (provisional, unattended run):** every scan logged in `BarcodeScan`
  (append-only), only the scanning club's Barcodes are found.
- **Proposed component styles:** PaymentTicket's status line and notches
  (`.la-ticket__status`, `.la-ticket__notch--left/right` in
  `frontend/src/styles/proposed.css`), from the inline styles of design/src/ui.mjs
  `ticket()`.

## 2026-10-23: Payments UI (chunk 19) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 19: Payments (UI)".

- **Opening PayFast (provisional, unattended run):** `frontend/src/native/browser.ts`
  `openCheckout(url)`: the in-app browser (@capacitor/browser) in the installed app, then
  the result screen once it is closed; in a browser the tab goes to PayFast and returns to
  `/payments/done` or `/payments/cancelled?payment=<reference>` (`PAYMENT_RETURN_URL`,
  `PAYMENT_CANCEL_URL`). No universal links / app links yet.
- **Pay my share (provisional, unattended run):** starts at `suggested_amount` from the
  backend: the fee over the Team's current Players, rounded up to the cent, less what the
  Player has paid, capped at what is owed. Credit first is a choice (none, my credit, Team
  credit for the Captain). The backend checks every amount.
- **Who has paid (provisional, unattended run):** `GET /api/v1/teams/{id}/payments/summary/`
  for the Captain and the club's Admins: what each Player has paid (net of refunds and
  reversals, leavers included), what was paid for the whole Team, Team credit for the
  Captain only (FR-21, FR-52).
- **Admin payments (provisional, unattended run):** Profile, Payments per club: the
  club's active Teams, unpaid first; each opens who has paid and Record cash (FR-22).

## 2026-10-23: PayFast payments (chunk 18) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 18: PayFast payments
(backend)". Answers open question 5 below, provisionally.

- **Gateway (provisional, unattended run):** `payments.gateways.PaymentGateway`, picked by
  the club's `payment_provider`; PayFast is the first (`payments/payfast.py`). Card
  details are typed only on PayFast's hosted page. Sandbox or live, credentials and URLs
  come from the environment (`PAYFAST_*`, `PAYMENT_RETURN_URL`, `PAYMENT_CANCEL_URL`).
- **Merchant accounts, open question 5 (provisional, unattended run):** one default
  account from the environment, and optionally a club's own in `PAYFAST_CLUB_ACCOUNTS`
  (environment, keyed by Club id). Each Payment records the merchant id it used.
- **Paying (provisional, unattended run):** a Player in an active Team pays any amount up
  to what the Team owes (FR-19). Credit first if chosen: their own, or the Team's for the
  Captain (FR-52), spent at once; the rest by card, at least R 5. Credit covering it all
  needs no card.
- **ITN (provisional, unattended run):** recorded only after source (PayFast's networks),
  signature, merchant, amount and PayFast's server-side validation pass. One card ledger
  entry per Payment, however often the ITN comes; every ITN is logged in
  `GatewayNotification`. A complete Payment never goes back.
- **Paid (provisional, unattended run):** not stored: an active Team that owes nothing
  (`is_paid`). `payments.signals.team_paid` is sent when a payment takes what is owed to
  nothing (FR-20), for the Barcode chunk.
- **Cash (provisional, unattended run):** an Admin of the Team's Club records cash for a
  Player or the whole Team, up to what is owed, in either payment mode (FR-22). Admins
  see which of their Teams have paid, unpaid first (FR-21).

## 2026-10-23: Player and Goalkeeper Requests (chunk 17) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 17: Player and
Goalkeeper Requests". Answers open questions 1 and 2 below, provisionally.

- **Requests (provisional, unattended run):** a Captain of a Team in the match raises a
  Player Request (outfield) or Goalkeeper Request for 1 to N places (N: the Division's
  minimum), while the match is scheduled, confirming or ready and before kick-off. One open
  request per Team, match and kind. Refused when no one can be asked.
- **Who is asked (provisional, unattended run):** Players opted into the match's Night, in
  neither Team, of that position (both counts as either), less anyone already borrowed for
  the match (FR-36, the visibility rule). Answerable until kick-off.
- **Joining (provisional, unattended run):** the first N to accept join (FR-37); then the
  request is filled and every other invite closes. One borrowed place per Player and match.
  A joined Player can't leave; the Captain can withdraw an open request (who joined stays).
  A borrowed Player counts as confirmed for the Team at T-6h (FR-5) and in the squad.
- **Open question 1 (provisional, unattended run):** no fee for a borrowed Player in a
  league match; nothing is charged.
- **Open question 2 (provisional, unattended run):** the Captain gets one Update when the
  request fills.

## 2026-10-23: Reschedules and Captain requests (chunk 16) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 16: Reschedules and
Captain requests".

- **Reschedule (provisional, unattended run):** only a scheduled, confirming or ready match,
  before kick-off. A new kick-off must be after the T-6h cutoff counted from now, inside the
  Season, on the Division's Night, with the pitch free and neither Team playing another match
  that day. Every reschedule is logged in `FixtureReschedule` (never changed or deleted).
- **Lifecycle restart (provisional, unattended run):** a new kick-off moves the match back to
  `scheduled`, closes its open Notifications and runs every checkpoint again for the new
  kick-off; within the Confirmation window the Confirmations go out at once (FR-9). A new
  pitch at the same kick-off restarts nothing.
- **Who is told (provisional, unattended run):** one Update to both Teams' Players (opted
  into the Night) and only the Night's Admins and the Referees of the old and new pitch
  (FR-7, FR-8).
- **Captain requests (provisional, unattended run):** a Captain asks to cancel or postpone
  with a reason; the Night's Admins are told; nothing changes until an Admin accepts
  (FR-18). An accepted cancellation takes that Team out (`one_team_out`) and starts the
  replacement search, then friendly or cancellation (FR-13 to FR-17). An accepted
  postponement is a reschedule to the time the Admin picks. One pending request per Team
  and match; a reschedule closes the others. The Captain is told of the decision.
- **Not built (provisional, unattended run):** an Admin cancelling a match outright without
  a Captain request.
- **Back to an earlier kick-off (provisional, unattended run; chunk 16 review):** refused
  (409) when the match already has Confirmations, answers, a readiness check or a
  replacement offer for that kick-off, since all of these are kept per kick-off and would
  come back. The Admin picks another kick-off.

## 2026-10-23: Friendly fallback or cancellation (chunk 15) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 15: Friendly fallback
or cancellation".

- **When (provisional, unattended run):** both Teams out at T-6h, or a replacement offer
  that lapsed, falls back at once: a friendly if the Admin listed the match as
  friendly-eligible and kick-off is still to come, otherwise a cancellation. Recorded once
  per Fixture in `FixtureFallback` (never changed or deleted).
- **Friendly (provisional, unattended run):** General with "Find a match" to the out
  Team(s); a Confirmation ("free to join") to every Player opted into the Night outside the
  out Team(s) (FR-11: outside both; FR-17: the remaining Team too); an Update to the
  Night's Admins and the pitch's Referee. "Confirm" joins, changeable until kick-off, no
  cap. No fee yet (chunk 22).
- **Cancellation and credit (provisional, unattended run):** every payment recorded
  against the cancelled Fixture comes back as credit to whoever paid (Player or Team,
  FR-52), only what is left of it, never twice; season-fee payments and charges are left
  as they are. The Teams and officials are told. `fallbacks.cancel_match` is reusable by
  later chunks.

## 2026-10-23: One Team out: replacement opponent (chunk 14) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 14: One Team out:
replacement opponent".

- **Eligible Teams (provisional, unattended run):** active, same Club, Season and Division,
  not either Team of the match, owing nothing on the ledger, no other match that day, and
  a Captain opted into the Night.
- **The offer (provisional, unattended run):** when the T-6h check leaves one Team out, the
  match moves to `replacement_offered` and each eligible Team's Captain gets a
  Confirmation-kind offer, open until `replacement_close_hours_before` kick-off (new club
  setting, default 2, fewer than the readiness hours). The first Captain to confirm wins;
  the backend locks the match, so a second gets 409. `ReplacementOffer` and
  `ReplacementCandidate` keep the record and are never deleted.
- **After an accept (provisional, unattended run):** the Team takes the out Team's place in
  the same Fixture; the match moves to `scheduled` (before T-36h, new move), `confirming`
  (before T-6h) or `ready` (after). Its Players get Confirmations; after T-6h they can
  answer until kick-off. Updates go to the remaining Team and to the Admins and Referee.
- **Notifications (provisional, unattended run):** FR-13 General with "Find a match" to the
  out Team; FR-14 Update to the remaining Team; FR-16 Update to the Night's Admins and the
  pitch's Referee on opening and on accept.
- **No Team (provisional, unattended run):** at the close time the offer lapses and
  `replacement_lapsed` hands off to chunk 15; an offer for a match that moved on is
  withdrawn.
- **Locking (provisional, unattended run):** a Fixture is locked without joins
  (`lifecycle.lock`), because PostgreSQL drops a joined locked row whose Team changed
  while it waited.

## 2026-10-23: T-6h readiness (chunk 13) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 13: T-6h readiness".

- **The check (provisional, unattended run):** at the T-6h cutoff (`readiness_hours_before`)
  a timed checkpoint, once per Fixture and kick-off and before the Reminder, looks at each
  Team of a `confirming` match: fewer confirmed than the Division minimum is out (FR-5);
  otherwise anything still owed on the ledger waits for the Admin (FR-6); otherwise it
  plays. A match still `scheduled` (no Confirmations went out): both Teams wait for the
  Admin. Recorded in `TeamReadiness` (counts and amount as seen, outcome, reason, the
  Admin's ruling); a ruling is made once.
- **The Admin's ruling (provisional, unattended run):** "Let them play" or "Rule out", on
  Tonight, while the match is still `scheduled` or `confirming`; no deadline and nothing
  automatic. No money moves with it.
- **Status (provisional, unattended run):** once every Team is decided the Fixture moves
  once: to `ready`, `one_team_out` or the new `both_teams_out` (which can only become a
  friendly or be cancelled, chunk 15). New move `scheduled` to `ready` for a match the
  Admin lets go ahead without Confirmations. The `readiness_settled` signal hands off to
  chunks 14 and 15.
- **Tonight (provisional, unattended run):** today's Fixtures (South African date) and any
  still waiting for a ruling; at-risk matches on top (f11 design), the rest by kick-off.
  Opened from Profile. Proposed components copied from design/src/proposed.css: the team
  readiness line (`.la-team-line`) and a ListRow led by a time (`.la-item__time`).

## 2026-10-23: Answering Confirmations (chunk 12) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 12: Answering
Confirmations".

- **Replies (provisional, unattended run):** a Player in either Team answers "I'm in" or
  "Can't make it" from the Confirmation Notification or the match screen, and can change
  it, while the Fixture is `confirming` and before the cutoff (`readiness_hours_before`
  kick-off, T-6h, from the Club's settings). The backend refuses anything else with 409.
- **One answer (provisional, unattended run):** `ConfirmationAnswer`, one per Fixture,
  Player and kick-off, changed in place; the Player's Confirmation Notification shows the
  same answer, so the resend skips anyone who answered either way. A Player without the
  Night's notifications still answers on the match screen. A new kick-off starts with no
  answers. A Player who joins after T-36h gets no Confirmation and answers on the match
  screen.
- **Who sees (provisional, unattended run):** a Team's Players see their own Team's
  replies (names and answers, confirmed against the Division minimum, below it or not);
  not the other Team's. Only Players in the Team now count.
- **Screens (provisional, unattended run):** Match detail shows SquadProgress, the reply
  card and the squad list (Confirmed, Waiting, Declined) from f02 and f06; a Confirmation
  in the inbox shows SquadProgress. New Lucide icon: clock.
- **Moving Teams (provisional, unattended run):** an answer counts only for the Team it
  was given for; a Player who moves to the other Team of the match answers again.

## 2026-10-23: Celery Beat and the timed checkpoints (chunk 11) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 11: Celery Beat and the
timed checkpoints".

- **Celery (provisional, unattended run):** Celery 5.6 with Redis (docker compose, port
  6380). `make worker` and `make beat`; one Beat only. Beat starts `fixtures.run_checkpoints`
  every 60 seconds (`CHECKPOINT_INTERVAL_SECONDS`).
- **Checkpoints (provisional, unattended run):** each Club's own hours. T-36h: a
  `scheduled` Fixture moves to `confirming` and every Player of both Teams gets a
  Confirmation answerable until T-6h. Resend, once, `confirmation_resend_after_hours` after
  the first went out, to Players who haven't answered: the same inbox entry pushed again.
  T-6h: Reminder to Players and Captains of both Teams, the Night's Admins and the pitch's
  Referee, for `scheduled`, `confirming` and `ready` Fixtures.
- **Exactly once (provisional, unattended run):** one `FixtureCheckpoint` row per Fixture,
  kind and kick-off, claimed with the notifications in one transaction; the log is
  append-only. A new kick-off (reschedule) gets new checkpoints.
- **Late (provisional, unattended run):** a missed checkpoint runs on the next pass while it
  still makes sense: Confirmations and the resend only before T-6h, Reminders only before
  kick-off.

## 2026-10-23: Push and inbox in the app (chunk 10) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 10: Push and inbox in
the app (UI)".

- **When the app asks for push (provisional, unattended run):** right after someone is
  signed in (each start of the app while signed in), only if the phone hasn't been asked
  yet. The token is registered with `POST /api/v1/devices/` every start, and removed with
  `DELETE /api/v1/devices/{id}/` on logout, before the session ends.
- **Push buttons never answer by themselves (provisional, unattended run):** a tapped
  push, or any of its buttons, opens the notification's screen; the Player answers there.
  "Find a match" opens My fixtures until the "Games you can join" screen exists.
- **iOS token (provisional, unattended run):** the backend sends by FCM token, so the iOS
  app must hand Capacitor the FCM token, not the APNs token. Until Firebase is added to the
  iOS project by hand, the AppDelegate passes the APNs token and pushes to iPhones fail
  (the inbox still has every notification).
- **Inbox entry point (provisional, unattended run):** an Inbox row with the unread count
  on Profile, since no chunk has built the tab bar yet. The Inbox and Notification screens
  follow design/src/screens/f02-confirmation.mjs; answer buttons use player phrases ("I'm
  in", "Can't make it", "Join match", "Not tonight").
- **Proposed components** (`frontend/src/styles/proposed.css`): icon disc (`.la-disc`,
  copied from design/src/proposed.css), ChoiceChip count, status hero (`.la-hero`, scale-in
  with a Reduce Motion fade) and the unread dot (`.la-unread`). Lucide icons in
  `frontend/src/components/Icon.tsx`.

## 2026-10-23: Notifications (chunk 9) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 9: Notifications
(backend and push sending)".

- **Notification (provisional, unattended run):** one per recipient, belongs to a Club, of
  one of the seven PRD kinds. The kind gives its buttons: Confirm / Decline
  (Confirmation, Booking), Accept / Decline (Player and Goalkeeper Requests), a "Find a
  match" link (General), none (Reminder, Update). An answer can be changed until
  `answer_by` and while the notification is open. Every notification stays in the inbox
  whether or not the push arrived.
- **Targeting (provisional, unattended run):** all recipients come from
  `backend/notifications/targeting.py`. Night opt-ins filter every notification sent to a
  Player, their own Team's included. "The Admin of the registered Night" is every Admin
  of the Night's Club. "Referees" means the Fixture's pitch's Referee (both pitches when
  a reschedule moves it). A Player who plays both positions gets both kinds of request.
- **Push (provisional, unattended run):** Firebase Cloud Messaging through firebase-admin,
  credentials from FIREBASE_CREDENTIALS_FILE or FIREBASE_CREDENTIALS_JSON. Locally pushes
  are only logged; tests use a fake sender. Pushes go out after the transaction commits.
  Dead tokens are removed; a token registered again moves to the account signed in.
- **Delivery fallback (provisional, unattended run):** not built yet; only the inbox and
  recorded push results. The proposal (retries in chunk 11, then email) waits for an
  answer.

## 2026-10-23: Ledger and credit (chunk 8) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 8: Ledger and credit".

- **LedgerEntry (provisional, unattended run):** append-only (FR-50). Club, kind (charge,
  payment, credit, refund, reversal), method (card, cash, credit, or empty), category
  (league, friendly, booking, for FR-49), amount (Decimal rand, always above 0; the kind
  gives the direction), subject (Team, Player, Booking User) with its Team and user, related
  Fixture, the entry a reversal undoes, the payment a credit came from, reason, recorded
  by, created at. The ORM, the Django admin and the API never change or delete one.
  Writes go only through `ledger/services.py`; balances are computed from entries.
- **Credit is per club (provisional, unattended run):** a Player's credit is spent only at
  the Club that issued it. Answers open question 6 below, provisionally.
- **League fee charged on confirmation (provisional, unattended run):** confirming a Team
  posts its league fee as a charge, fixed at that moment; no fee, no confirmation.
- **Who sees and spends (provisional, unattended run):** a Team's balance: its Captain and
  its Club's Admins. Team credit: its Captain only. Player credit: the Player only, on a
  Team they are in now. Never more than held, or than the Team still owes.
- **Credit back to whoever paid (provisional, unattended run):** a Player's payment returns
  as Player credit, a whole-Team payment as Team credit, never more than the payment. The
  Team's paid amount is unchanged. Booking User credit is a separate wallet.
- **Reversals (provisional, unattended run):** any entry but a reversal, once, with a
  reason; spent credit can't be reversed; a payment can't be reversed while credit
  returned from it stands.

## 2026-10-23: Fixtures and Admin fixture import (chunk 7) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 7: Fixtures and Admin
fixture import".

- **Fixture (provisional, unattended run):** belongs to a Club and a Season. It has a
  Division (its Night is that Division's Night, not stored twice), a pitch (a Field),
  kick-off (stored in UTC, sent with its offset, shown in South African time), and home
  and away Teams. It also has friendly-eligible, with who set it and when, and a status.
- **Status moves (provisional, unattended run):** only the moves in
  `backend/fixtures/lifecycle.py` `TRANSITIONS`. Cancelled and played are final. A friendly
  needs friendly-eligible. Every move, and the Fixture's creation, is logged in
  `FixtureTransition`: from, to, when, the user or none, the cause (import, Admin, Captain,
  timed checkpoint, League App) and a note. The log is append-only. Fixtures and their logs
  can't be deleted, and the Django admin shows them read-only.
- **Import (provisional, unattended run):** same flow as chunk 4, for one Season picked on
  the screen. The columns are Date, Time, Night (optional, must match the date), Division,
  Pitch, Home, Away and Friendly eligible (optional). A row is the same Fixture when
  Division, Home, Away and kick-off match. A re-import can change only Friendly eligible.
  The import never moves or deletes a Fixture. Kick-offs must still be to come, inside the
  Season and on the Night's weekday. Both Teams must be confirmed Teams of that Division
  and Season. A pitch or Team can't have two Fixtures at the same kick-off.
- **Who sees Fixtures (provisional, unattended run):** a club's Admins see all of its
  Fixtures. Players and Captains see the Fixtures of the Teams they are in now. No one
  else sees them.
- **Friendly-eligible (provisional, unattended run):** the Admin can change it while the
  match may still fall through (scheduled to replacement offered), not after.
- **Proposed component:** MatchCard link (`.la-card-link` in
  `frontend/src/styles/proposed.css`): a whole MatchCard that opens the match.

## 2026-10-23: Teams screens (chunk 6) (provisional, unattended run)

Chosen during an unattended run; see docs/OPEN_QUESTIONS.md "Chunk 6: Teams (UI)".

- **No drawn Team screens (provisional, unattended run):** design/ has no Team mockups, so
  the screens follow the Screens.md descriptions (Player 4 and 5, Captain 1 to 3, Admin 3)
  with the existing `la-` components.
- **Where Teams are reached (provisional, unattended run):** there is no tab bar yet, so
  Profile links a Player to Teams (`/teams`) and an Admin to Team requests
  (`/clubs/{id}/teams`). The tab bar comes in a later chunk.
- **Division filter in Find a team (provisional, unattended run):** after a Night is
  picked, its Division chips are the Divisions of that Night's Teams in the results.
- **Declined Teams (provisional, unattended run):** a declined Team drops out of the
  Player's Teams list, as the chunk 5 API does, and its reason is shown only to Admins. The
  Captain hears of it with the notifications chunks.
- **Proposed component:** SelectableRow (`.la-item--choice` in
  `frontend/src/styles/proposed.css`): a ListRow picked like a radio, `accent-soft` when
  selected. Used for the Night and Division rows in Request a Team.

## 2026-10-23: Teams (chunk 5)

Decided by @Sasha while building chunk 5 (the Captain and Admin rows of the roles table).

- **Season:** a Captain requests a Team for a Season and a Division, choosing from the
  club's Seasons that haven't ended. A Team belongs to one Season; carrying a Team over to
  the next Season comes later.
- **Most Teams per Division:** each Division has a `max_teams`, set by the Admin. Empty
  means no limit. It counts active Teams in one Season. A full Division takes no new
  requests, and the Admin can't confirm past it. Requests waiting for the Admin don't
  count. The Nights and Divisions import doesn't read it yet.
- **One Team per Division and Season:** a Player can be in several Teams, at several clubs,
  but in only one Team in each Division and Season. It counts Teams that are active and
  Teams still waiting for the Admin. When a Captain accepts a Player, that Player's other
  open requests in the same Division and Season are withdrawn.
- **Team names:** unique in a Division and Season, in any case. A declined Team's name can
  be used again.
- **League fee first:** a Team can't be requested until the Division has a league fee (its
  own or the club's). This is the block on Team sign-up promised in chunk 3.
- **The requester is Captain** and the Team's first Player as soon as they ask. If the
  Admin declines, the Team's Players leave it, so they can request or join another Team.
- **Joining:** Players ask to join active Teams only. No joining, or accepting a Player into, a Team
  whose Season has ended (provisional, unattended run). The Captain accepts or declines, and
  the Player can withdraw while the request is pending.
- **Captain:** the Admin can make any current Player of the Team its Captain. The old
  Captain stays in the Team as a Player. A Captain can't leave their Team until the Admin
  assigns another Captain. Removing Players from a Team comes later.
- **Membership history:** leaving closes a membership and keeps it, and rejoining opens a
  new one.
- **Who sees what:** any Player can search active Teams at every club, at most 50 a
  search. Only a Team's own Players see who is in it. Only its Captain sees its join
  requests. Admins see their own club's Teams only.

## 2026-10-23: Import Nights and Divisions (chunk 4)

Decided by @Sasha while building chunk 4 (FR-39).

- **Columns:** one row per Division: Night (a weekday, like Tuesday, Tue or "Tuesday Night"),
  Division, Min players and League fee. Night and Division are required. Headers are
  matched without regard to case or spaces, and other columns are ignored. Only the first
  sheet of an .xlsx is read. The template (Excel or CSV) is downloaded from the import
  screen, and its second sheet explains the columns.
- **Matching:** a Division is matched on its Night and its name, ignoring case and outer
  spaces, so re-importing a file creates nothing twice. A Night the Club doesn't have yet
  is created. Names are unique per Night only as typed, so if a Night has Divisions whose
  names differ only in case, a row takes the one with exactly its name, and a row that
  matches several only ignoring case is an error (chunk 4 review).
- **Re-importing updates:** an existing Division takes the file's Min players and League
  fee. A blank cell keeps the value it has. For a new Division, a blank Min players means
  the club's minimum, and a blank League fee means the club's fee.
- **Divisions not in the file are left alone:** an import never deletes.
- **All or nothing:** preview writes nothing. Commit checks the file again and saves every
  row in one transaction, or saves nothing if any row has an error. The server keeps no
  upload between the two: the app sends the file again.
- **Fees** are read in rand: "350", "R 350", "1,200.50" and "1 200" are accepted. A comma
  counts only as a thousands separator, so "350,50" is an error, not R 35,050.
- **Limits:** 5 MB and 500 rows a file.
- **Not in the installed app yet:** the template download works in a browser. The
  installed app can't save files until the Capacitor Filesystem and Share plugins are
  added, so it asks the Admin to use a browser. Uploading works in both.
- **Proposed component** (`frontend/src/styles/proposed.css`): FilePicker, a button-styled
  label around a hidden file input.

## 2026-10-23: Club setup and configurable values (chunk 3)

Decided by @Sasha while building chunk 3.

- **Defaults are data:** one `SettingsDefaults` record, seeded by a data migration with the
  PRD values and edited in the Django admin. A new Club's `ClubSettings` is copied from it
  when the Club is created. A later change to the defaults affects only Clubs created after
  it. The seeded values: Confirmations at T-36h, resent once 12 hours later; Reminder and
  readiness at T-6h; at least 5 Players per Division; booking payment taken 24h before;
  50% credit from then to 6h before, none after that or for a no-show, and 100% when the
  club cancels; one late reschedule to a slot within 30 days; card and cash through PayFast.
- **Fees start empty:** the league fee per Team, the friendly fee and the booking hourly
  fee have no default. The club's Admin must set them; settings report what is `missing`,
  and Setup shows it. Blocking Team sign-up and bookings until they are set comes with
  those chunks.
- **Resend (FR-2):** 12 hours after the first Confirmation, so at T-24h. It must go out
  before the readiness check.
- **League fee:** one per Club, and a Division may set its own, which overrides it.
- **Nights and Divisions carry over across Seasons:** a Division belongs to a Night, not
  a Season, so Players' Night opt-ins carry over too. One Night per weekday per Club.
  Teams (chunk 5) will tie a Season to a Division.
- **Hours, not durations:** cutoffs are whole hours before kick-off, and the reschedule
  window is whole days. Credit is a whole percentage from 0 to 100.
- **Inviting Admins and Referees:** a Club's Admin invites by email. An account with that
  email gets the role at once. Otherwise the invite stays open and the role is given when
  someone signs up with that email. The app sends no invite email yet: the Admin tells
  the person. A Club always keeps at least one Admin, and removing a Referee takes them
  off their Fields. A Field's Referee must hold the Referee role at that Club.
- **Not yet safe for store release:** sign-up does not verify email addresses, so whoever
  first signs up with an invited email gets that role. Email verification, or an invite
  link with a code, must come before store release.
- **Deleting:** a Night with Divisions can't be deleted (409). Every other setup record can
  be deleted until later chunks give it Teams, Fixtures or bookings.
- **Proposed components** (`frontend/src/styles/proposed.css`): a ListRow that is a link,
  a back link above the screen title, a section header with an action, and ConfirmButton,
  which asks once more before a delete or removal.

## 2026-10-23: Accounts, roles and token auth (chunk 2)

Decided by @Sasha while building chunk 2. Closes open questions 3 and 4.

- **One account, any club (Q3):** an account is app-wide. One Player can play for Teams at
  more than one club, and can opt into any club's Nights. Only Admin and Referee are held
  per Club (`ClubRole`).
- **New clubs are set up by us (Q4):** clubs do not sign up in the app. We create the Club
  and its first Admin in the Django admin. Giving Admin and Referee roles in the app comes
  with chunk 3 (see the chunk 3 entry above).
- **Login:** email and password only, with the email matched in any case. Phone is asked
  at sign-up (optional) for contact, not for login. Phone login can come later.
- **Roles at sign-up:** the user picks "I play" (a Player, then a position: outfield,
  goalkeeper or both), "I hire a field" (a Booking User), or both. Both can be changed in
  Profile. At least one is required.
- **Captain** is not a stored role: a Player is a Captain of the Team they captain
  (chunk 5).
- **Tokens:** JWT (djangorestframework-simplejwt). The access token lasts 15 minutes and
  the refresh token 60 days. Every refresh hands out a new refresh token and blacklists
  the old one. Logout blacklists it too. The API accepts no session cookies; the Django
  admin keeps its own session login.
- **Token storage:** Capacitor Preferences in the installed app, localStorage in the
  browser (`frontend/src/native/storage.ts`). Preferences is not the iOS Keychain or
  Android Keystore. Moving the refresh token to secure storage is listed for before store
  release.
- **Proposed components** (not in the design system yet, built from its tokens in
  `frontend/src/styles/proposed.css`, recipes from the key-moments draft): TextField,
  ChoiceChip, Banner, ListGroup and ListRow, and a screen layout (`la-screen`).

## 2026-10-23: One app for every club; Capacitor setup

Decided by @Sasha while building chunk 1.

- **Multi-club:** the app is not built for one club. One backend and one store app serve
  every club. Each club's Seasons, Nights, Divisions, Fields, Teams, Fixtures, settings and
  ledger belong to that Club, and its Admins and Referees see and change only that Club's
  data. No club's name goes in code, app ids or store listings. Old Parks, named in the
  PRD, is the first club, not the only one.
- **App id:** `za.co.leagueapp`, name "League App". It cannot change once the app is in
  the stores, so confirm it (and that the domain is ours) before the first upload.
- **API address in the installed app:** the build reads `VITE_API_BASE_URL`
  (`frontend/.env.example`). The browser keeps using its own origin and the Vite proxy.
  On a simulator or emulator it is `http://127.0.0.1:8000`; the Android emulator reaches
  it through `adb reverse tcp:8000 tcp:8000`.
- **CORS:** `capacitor://localhost` (iOS) and `https://localhost` (Android) are always
  allowed, in every environment, because they are the installed app's own origins. No
  credentials: the app uses token auth.
- **Cleartext HTTP:** allowed only in Android debug builds, only to 127.0.0.1, localhost and
  10.0.2.2 (`frontend/android/app/src/debug/`). Release builds block it.
- **Toolchain:** Capacitor 8. iOS uses Swift Package Manager, so CocoaPods is not needed.
  Android needs JDK 21.

## 2026-10-23: Platform, gateway, scheduler, Fixture source, credit

Decided by @Sasha while splitting the PRD into build chunks. Added to `docs/PRD.md` as FR-52,
FR-53 and new rows in its Decisions table.

- **Platform:** not a native app, but installed from the App Store and Google Play. The React
  web app is wrapped with Capacitor (`frontend/ios/`, `frontend/android/`), which gives native
  push notifications on iOS without the home-screen-only limit of Web Push. This closes the
  open point in the 2026-10-21 entry below. What store release needs:
  - Push goes through Firebase Cloud Messaging for both platforms (APNs key uploaded to
    Firebase), using `@capacitor/push-notifications` in the app and `firebase-admin` in the
    backend.
  - Gate scanning uses the device camera through a native Capacitor barcode plugin, not a
    browser camera API.
  - The app talks to the API with token auth, not session cookies, because the wrapped app
    runs on its own origin (`capacitor://localhost` on iOS, `https://localhost` on Android).
  - Apple rejects apps that are only a website in a frame (App Review Guideline 4.2). Native
    push, native scanning and app-only flows are what keep this app above that line.
  - League fees and field bookings are real-world services, so card payment through PayFast
    is allowed in the app and no Apple or Google in-app purchase is needed (Guideline 3.1.5(a)).
  - The club needs an Apple Developer account and a Google Play Console account, a privacy
    policy URL, and store listings.
- **Payment gateway:** PayFast first. Peach Payments and Yoco come later, so payments go
  through one gateway interface with PayFast as the first provider.
- **Timed jobs:** Celery Beat runs the T-36h and T-6h checkpoints and the booking payment
  cutoff. Each job must be safe to run twice for the same fixture.
- **Fixtures:** the Admin imports them from Excel, like Nights and Divisions (FR-53). Syncing
  from an external fixtures system stays under FR-40 for later.
- **Credit (FR-52):** held by Players and by Teams. Player credit belongs to the Player and can
  be spent on any Team's match they play in. Team credit belongs to the Team and only its
  Captain can spend or manage it. Credit goes back to whoever paid: a Player's contribution
  becomes Player credit, and a payment for the whole Team becomes Team credit.

## 2026-10-21: React + Django web app

The app is built as a web app: a React frontend (`frontend/`) over a Django REST API
(`backend/`), the same stack as Swingbok.

- The PRD lists iOS and Android as the platforms, and the designs in `design/` are mobile
  screens at 375 × 812. The web app is therefore built mobile-first from those designs.
- **Still open:** push notifications are the PRD's core mechanism. A web app sends them with
  Web Push, and iOS delivers Web Push only to a web app added to the home screen (iOS 16.4 and
  later). Whether that is enough, or the app needs a native wrapper, is not decided yet.

## 2026-10-21: Design source

The UI follows the League App design system: tokens, type styles and `la-` components.
Its files are in `design/src/ds/`, copied unchanged from `League App Design System.zip`
(dated 2026-10-20) because the claude.ai artifact link could not be read from Claude Code.
`design/` also holds the canvas generator and the key-moments draft
(`design/key-moments-draft.html`).

## Open questions

Raised while drawing the key moments; the PRD does not answer them.

1. Does a borrowed Player pay for a league match, how much, and who pays? FR-24 sets a fee
   only for friendlies. (Provisionally answered in chunk 17: no fee yet.)
2. Is the Captain notified when a Player or Goalkeeper Request fills? The PRD names no
   notification for it. (Provisionally answered in chunk 17: yes, one Update.)

Raised by the multi-club decision (2026-10-23). Questions 3 and 4 were answered in chunk 2
(see the entry above).

5. Does each club take card payments into its own PayFast merchant account?
   (Provisionally answered in chunk 18: either works by configuration; a default account
   and optional per-club accounts, all from the environment.)
6. Does a Player's credit (FR-52) belong to one club, or can it be spent at any club?

## 2026-10-27: Logo, "Kick-off stripes"

- **Logo (chosen by the owner, option 1d):** two forward-leaning bars, like kit stripes or a
  "vs" slash, with an italic wordmark. In the app the lead bar is `accent-ink` and the second
  `ink`, the wordmark "LEAGUE APP" in `font-display` 700 italic capitals, `ink`, so it reads
  in Night and Day. The fonts ship no italic, so the slant is the browser's synthetic oblique.
- **App icon and splash:** the bars alone, `accent` then `ink`, on the Night `ground`,
  drawn by `frontend/scripts/app-assets.mjs` (`npm run assets`); they replace the pitch
  outline. The mark fills 44% of a square icon, as in the logo's app-icon tile.
- **Proposed component** (`frontend/src/styles/proposed.css`): Logo (`.la-logo`,
  `frontend/src/components/Logo.tsx`), shown on Home in place of the plain "League App"
  title. The design canvas's push-notification app icon uses the same mark.
