# Decisions

Newest first. Each entry: the date, what was decided, and why.

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
