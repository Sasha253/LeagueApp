# Open questions

Questions met during unattended runs, with the choice made. Move the answers you agree
with into docs/DECISIONS.md.

## Chunk 4: Import Nights and Divisions from Excel

None. Every question this chunk raised was already answered and is recorded in
docs/DECISIONS.md under "2026-10-23: Import Nights and Divisions (chunk 4)".

## Chunk 5: Teams (backend)

None. Every question this chunk raised was already answered and is recorded in
docs/DECISIONS.md under "2026-10-23: Teams (chunk 5)".

- **Joining a Team after its Season has ended (review).** Question: may a Player ask to
  join, or a Captain accept a Player into, a Team whose Season has ended? Choice: no, 409
  "This Season has ended." Why: a Team can't be requested for an ended Season, and a
  membership in a finished Season means nothing for fixtures or payments. If the answer
  differs: remove the `_season_ended` checks in `backend/teams/rules.py` and the test
  `test_no_joining_a_team_once_its_season_has_ended`.

## Chunk 6: Teams (UI)

- **No Team mockups in design/.** Question: which layout do the Team screens use? Choice:
  built from design/src/ds/Screens.md (Player 4 and 5, Captain 1 to 3, Admin 3) with the
  existing `la-` components, plus one proposed SelectableRow. Why: the screen list
  describes them and the components exist. If the answer differs: restyle
  `frontend/src/pages/teams/`; no API change.
- **How a user reaches the Team screens.** Question: there is no tab bar yet; where do the
  screens hang? Choice: Profile links Players to Teams and Admins to Team requests. Why:
  smallest change that makes them reachable; the tab bar is its own piece of work. If the
  answer differs: add the tab bar (Teams / My team / Requests tabs) and drop the Profile
  links.
- **Division filter in Find a team.** Question: which Divisions to offer, given the Night
  list carries no Divisions? Choice: after a Night is picked, the Divisions of that Night's
  Teams in the results. Why: no API change, and only Divisions with Teams can match. If
  the answer differs: add Divisions to `GET /api/v1/nights/` and list them all.
- **Telling a Captain their Team was declined.** Question: should the Captain see a
  declined Team and the Admin's reason in the app? Choice: no, the chunk 5 API leaves
  declined Teams out of "my Teams", and the reason is shown only on the Admin's screen.
  Why: conservative, no API change in a UI chunk; notifications (chunks 9 and 10) are the
  place to tell them. If the answer differs: include declined Teams with `decline_reason`
  in `GET /api/v1/me/teams/` and show them on Teams.

## Chunk 7: Fixtures and Admin fixture import

- **Which status moves are allowed.** Question: the PRD names the stages of a match but not
  every move between them. Choice: the table in `backend/fixtures/lifecycle.py`.
  Cancelled and played are final. A friendly needs the friendly-eligible flag. A reschedule
  may move confirming or ready back to scheduled, or ready back to confirming. One team out
  goes only to replacement offered, friendly or cancelled. Why: it follows the PRD flows
  (FR-1 to FR-18) and refuses anything they don't describe. If the answer differs: change
  `TRANSITIONS`. The parametrised test covers every pair.
- **When a re-imported row is the same Fixture.** Question: what makes a row match a
  Fixture the club already has? Choice: the same Division, Home, Away and kick-off. A
  re-import can change only Friendly eligible. A row for that Fixture on another pitch is an
  error ("reschedule it instead"). The import never moves or deletes a Fixture. Why:
  re-importing must not duplicate, and moving a match notifies people (FR-7 to FR-9), which
  the import doesn't do. If the answer differs: let `fixtures/imports.py` update the pitch
  or time once the reschedule chunk can notify.
- **Kick-off checks.** Question: which kick-offs can be imported? Choice: only kick-offs that
  are still to come, inside the Season's dates, and on the weekday of the Division's Night.
  Seasons that have ended take no imports. Why: a past or off-Night Fixture would trigger
  checkpoints at the wrong time or not at all, and is most likely a typo. If the answer
  differs: drop the checks in `plan()`; the model allows any kick-off.
- **Which Teams can play.** Question: may a Fixture name a Team still waiting for the Admin,
  or a Team of another Division? Choice: no. Both Teams must be confirmed (active) Teams of
  the row's Division in the chosen Season. Why: only confirmed Teams play league matches.
  If the answer differs: relax the Team lookup in `plan()`.
- **Clashes.** Question: when do two Fixtures clash? Choice: when they share a pitch, or a
  Team, at exactly the same kick-off, among Fixtures that aren't cancelled. The database
  also refuses two Fixtures on one pitch at one kick-off. Why: the PRD gives no match
  length, so overlaps can't be judged. If the answer differs: add a match length to
  ClubSettings (data, not code) and check overlaps.
- **Dates in the file.** Question: which date forms are read? Choice: 2026-10-27, 27/10/2026
  (day first, never month first), 27 Oct 2026 and Tue 27 Oct 2026, always with the year.
  Excel date and time cells are read as they are. Times are 24-hour in South African time.
  Why: day first is how South Africa writes dates; anything ambiguous is refused. If the
  answer differs: add forms to `parse_date`.
- **Who sees Fixtures.** Question: who can see which Fixtures? Choice: a club's Admins see
  all its Fixtures, filtered by Season and Night, and only Seasons that haven't ended unless
  a Season is picked. A Player or Captain sees the Fixtures of the Teams they are in now,
  including cancelled ones. A Player who left a Team stops seeing its Fixtures. No one else
  sees them. Referees get their pitch's matches with the Tonight view (later). Why: this is
  the smallest view that covers the screens. Fixtures name Teams, so they aren't made
  public. If the answer differs: widen the querysets in `backend/fixtures/views.py`.
- **When friendly-eligible can change.** Question: until when can the Admin change the flag?
  Choice: while the Fixture is scheduled, confirming, ready, one team out or replacement
  offered. After that the answer is 409. The flag can also be set by the import. Who set it
  and when is kept. Why: once a match is a friendly, cancelled or played, changing the flag
  means nothing. If the answer differs: change `FLAG_OPEN` in `lifecycle.py`.

## Chunk 8: Ledger and credit

- **Is Player credit per club? (open question 6 in DECISIONS.md)** Question: can credit
  issued at one club be spent at another? Choice: no. Every entry belongs to one Club, and
  a Player's credit is counted and spent per Club; `GET /api/v1/me/credit/` lists it per
  Club. Why: CLAUDE.md says every club's data is its own, and each club may take payments
  into its own merchant account (open question 5), so one club can't spend another's
  money. If the answer differs: drop the `club` filter in `ledger.services.user_credit` and
  let `spend_credit` use credit from any Club (and settle between clubs).
- **When the league fee becomes "due".** Question: is a Team's amount due computed live
  from the fee, or fixed when charged? Choice: a charge entry is posted when the Admin
  confirms the Team (`teams.rules.confirm_team`), at the Division's effective fee then;
  a data migration charged Teams already active. A later fee change doesn't rewrite what a
  Team owes; the Admin reverses the charge and the fee is charged again. Confirming a Team
  with no league fee set is refused (409). Why: a ledger is history; a live figure would
  change paid-up Teams' balances whenever the fee is edited. If the answer differs: compute
  `due` from `Division.effective_league_fee` in `team_balance` and drop the charge.
- **Who sees a Team's balance.** Question: the prompt says "Team balance" without naming
  who reads it. Choice: the Team's Captain and the Admins of its Club; everyone else gets
  404 (Players of the Team too). Why: FR-21 names Captains and Admins; Players' view of
  who paid is not in the PRD. If the answer differs: let current members in, in
  `ledger/views.py` `TeamBalanceView`.
- **Who may spend credit.** Question: can an Admin (or the app) spend a Player's or a Team's
  credit for them? Choice: only the Player spends Player credit, and only the Team's
  Captain spends Team credit (FR-52), on a Team that is active, never more than held or
  than the Team still owes. Why: FR-52 says only the Captain manages Team credit, and
  credit is the holder's money. If the answer differs: widen the `spent_by` check in
  `spend_credit` (FR-46 automatic use for bookings will need the app to spend it).
- **Does returning a payment as credit change what the Team has paid?** Question: when a
  paid match is cancelled (FR-43), does the Team's "paid" drop? Choice: no. Credit is a
  separate entry in the holder's wallet; the payment stays paid. At most the payment's
  amount can be returned as credit, in total, and a payment can't be reversed while credit
  returned from it stands. Why: the league fee is per Season, so the Team has still paid
  its fee; how much of a payment a cancelled match is worth is chunk 15's decision. If the
  answer differs: chunk 15 can also post a charge or reversal on the Team account.
- **Booking User credit.** Question: is a Booking User's credit (FR-46) the same wallet as
  their Player credit? Choice: no, kept apart by subject (`user_credit(club, user,
  subject)`). Why: conservative; bookings come in chunk 23. If the answer differs: count
  both subjects in one wallet.
- **Correcting entries.** Question: what can be reversed? Choice: any entry except a
  reversal, at most once, with a reason. Spent credit can't be reversed. To undo a
  mistaken reversal, record the entry again. Why: FR-50; keeps every balance from going
  below zero. If the answer differs: change the checks in `ledger.services.reverse`.

## Chunk 9: Notifications (backend and push sending)

- **Does the Night opt-in also filter a Player's own Team's notifications?** Question: the
  PRD says "Players only receive notifications for the Nights they opted into", but FR-1
  says every Player of both Teams gets a Confirmation. Choice: the opt-in filters every
  notification addressed to a Player (Captains too), own Team included, as CLAUDE.md asks
  ("follows the PRD exactly"). Admins and Referees are told through their Club role and
  are not filtered. Why: the literal rule, and the stricter one. Risk: a Player in a
  Tuesday Team who didn't opt into Tuesday gets no Confirmation, so may count as not
  confirmed at T-6h. If the answer differs: in `notifications/targeting.py`, drop
  `opted_in()` from `team_players` and `fixture_players` (keep it in `players_outside`),
  or opt a Player into a Team's Night when they join it (teams chunk).
- **Who is "the Admin of the registered Night"? (FR-8)** Question: a Night has no Admin of
  its own; Admins are held per Club. Choice: every Admin of the Night's Club
  (`targeting.night_admins`). Why: no model for a Night's Admin exists, and adding one is a
  bigger change than this chunk. If the answer differs: add Admins to Night and change
  `night_admins` only; every caller goes through it.
- **Which Referees are told for FR-4, FR-12, FR-16 and FR-17?** Question: the PRD says
  "Referees" without saying which. Choice: only the Referee of the Fixture's pitch, while
  they still hold the Referee role at that Club; on a pitch change (FR-8) the old and the
  new pitch's Referees. Why: they are the ones affected; the fewest people told. If the
  answer differs: add the Club's Referees in `targeting.officials`.
- **Which Admins are told for the Reminder and FR-12, FR-16, FR-17?** Choice: the Night's
  Admins, which today is every Admin of the Club. If the answer differs: change
  `targeting.officials`.
- **Player Requests to Players who play both positions.** Choice: a Player whose position
  is "both" gets Player Requests and Goalkeeper Requests. A Player in another Team of the
  same Night can still be asked (only the two opposing Teams are left out, FR-36). If the
  answer differs: change `targeting.players_outside`.
- **Delivery failure fallback (NFR Timeliness) - proposal, not built.** The prompt asks to
  propose and ask first. Proposal: (1) every notification is kept in the inbox whatever
  happens to the push (built); (2) each push result is recorded, and tokens Firebase
  reports as dead are removed (built); (3) with Celery (chunk 11), retry a failed push
  twice, 1 and 5 minutes later; (4) if an answerable notification (Confirmation, Player
  or Goalkeeper Request, Booking) still has no device that took it, or no answer 2 hours
  before its `answer_by`, send an email with a link to the app; SMS only if the club
  wants to pay for it. Choice for now: (1) and (2) only. Why: the prompt says to ask
  before building the fallback, and email and SMS need a provider and its keys. If the
  answer differs: build (3) and (4) in chunk 11 or later.
- **Sending now, not from Celery.** Choice: `notify()` pushes in the same process right
  after the transaction commits. Why: Celery arrives in chunk 11. If the answer differs:
  chunk 11 moves `services.push` into a task; callers don't change.
- **FCM registration tokens.** firebase-admin 7.7 marks `Message.token` deprecated in
  favour of `fid` (Firebase installation ID). Choice: send by registration token, which
  is what `@capacitor/push-notifications` gives on Android (iOS needs FCM tokens too, so
  chunk 10 must register an FCM token, not the raw APNs token). If the answer differs:
  store the FID in `DeviceToken.token` and send with `fid=` in `FirebaseSender`.
- **A token registered by another account.** Choice: registering a token already known
  moves it to the account now signed in (a shared or handed-on phone gets the new
  account's pushes only). Removing a device works only for its owner. Why: a phone
  should never receive another account's notifications. If the answer differs: refuse
  with 409 in `DeviceListView`.
- **Answering.** Choice: an answer can be changed until `answer_by` (later chunks set it,
  e.g. T-6h for FR-3) and while the notification isn't closed; closed or late answers get
  409. What an answer does is left to later chunks through the `notification_answered`
  signal. The inbox shows the newest 100, unanswered ones first.

## Chunk 10: Push and inbox in the app (UI)

- **When to ask for push permission.** Question: the PRD doesn't say when the app asks.
  Choice: once someone is signed in, the first time only (the phone's own prompt; never
  asked again after a no). Why: pushes are per account, and asking before sign-in would
  register a token with no one to send to. If the answer differs: call `registerPush`
  from another place (for example after choosing Nights) in `push/PushBridge.tsx`.
- **Do push buttons answer straight from the lock screen?** Question: the lock screen
  design shows "I'm in" / "Can't make it" on the push; the prompt says a tap "opens the
  right screen". Choice: every button opens the notification's screen and nothing is
  answered until the Player taps there. Why: the stricter reading; an answer from a
  pocket tap counts towards T-6h readiness. Also, OS action buttons need the backend to
  send a category per kind and the app to register them natively, which isn't built. If
  the answer differs: in `push/links.ts` and `PushBridge`, post the answer for
  `confirm`, `decline` and `accept` action ids, and add categories in
  `notifications/push.py` and natively.
- **Where "Find a match" goes.** Question: the General notification's button has no
  screen yet ("Games you can join" comes with Player Requests and friendlies). Choice:
  My fixtures (`/fixtures`). If the answer differs: change `FIND_MATCH_PATH` in
  `frontend/src/push/links.ts`.
- **Inbox entry point without a tab bar.** Question: the designs put Inbox in the tab
  bar, which no chunk has built. Choice: an Inbox row with the unread count on Profile.
  If the answer differs: add the tab bar (its own chunk) with the Inbox badge from
  `GET /api/v1/inbox/summary/`.
- **Which match screen a notification opens.** Choice: an Admin of the notification's
  Club opens the club's Fixture screen; everyone else the Player's. If the answer
  differs: change `matchPath` in `pages/inbox/NotificationPage.tsx`.
- **Session that ends by itself.** When the refresh token stops working (not a logout),
  the phone can't remove its device registration, so it keeps getting that account's
  pushes until someone signs in on it (the token then moves) or Firebase reports it dead.
  Choice: accepted for now. If the answer differs: let the backend drop devices whose
  account has no valid refresh token.

## Chunk 11: Celery Beat and the timed checkpoints

- **How often the checkpoints run.** Question: the PRD says only "on time". Choice: Beat
  starts one pass every 60 seconds (`CHECKPOINT_INTERVAL_SECONDS`), and a pass not started
  within that time expires. Why: a minute late is on time for a 36-hour or 6-hour notice,
  and each pass is cheap. If the answer differs: change the env variable.
- **Late runs.** Question: what happens when Beat or the worker was down at the due time?
  Choice: the next pass catches up, while it still makes sense: a Confirmation (and its
  resend) only before the T-6h cutoff, because it couldn't be answered after; a Reminder
  only before kick-off. A Fixture that missed its Confirmation stays `scheduled` for the
  T-6h readiness check (chunk 13). Why: never send something that can't be acted on. If the
  answer differs: widen the windows in `fixtures/checkpoints.py` `due()`.
- **Exactly once, and reschedules.** Choice: a `FixtureCheckpoint` row per Fixture, kind and
  kick-off, claimed in the same transaction as the notifications. A second run finds the
  row and does nothing. A reschedule to a new kick-off gets fresh checkpoints (FR-9 comes in
  chunk 16). Why: the 2026-10-23 decision says each job must be safe to run twice.
- **What "resend" is.** Question: a second Notification, or the first one pushed again?
  Choice: the same inbox entry pushed again, shown unread, with `resent_at` set. Why: one
  Confirmation per Player per match keeps one answer; two entries could be answered
  differently. If the answer differs: call `notify()` again in `resend_confirmations`.
- **Who gets the resend.** Choice: Players who got the first Confirmation, haven't answered
  (confirm or decline both count as answered), are still in one of the two Teams and still
  opted into the Night. Resend time counts from when the first actually went out, so a late
  first send means a late resend, and no resend at all if that falls after T-6h. Why: FR-2
  says once, to Players who haven't answered. If the answer differs: change
  `resend_confirmations`.
- **Which Fixtures get the checkpoints.** Choice: Confirmations only for `scheduled`
  Fixtures (moving them to `confirming`, cause "timed checkpoint"); Reminders for
  `scheduled`, `confirming` and `ready`. A Fixture already out, offered to a replacement, a
  friendly, cancelled or played gets neither: the chunk that moves it there tells people.
  Why: those matches are no longer the league match the Reminder describes. If the answer
  differs: change `REMINDER_STATUSES`.
- **Reminder recipients.** Question: does a Player who declined still get the T-6h
  Reminder? Choice: yes, as FR-4 and the targeting rules say (Players and Captains of both
  Teams, the Night's Admins, the pitch's Referee), filtered by Night opt-ins. Why: the PRD
  names no exception. If the answer differs: exclude decliners in `send_reminders`.
- **Readiness order (for chunk 13).** The T-6h readiness check should run in the same pass,
  before the Reminder, so a Team that is out isn't reminded.
- **A Player who joins after T-36h.** Not answered here: they get no Confirmation. Chunk 12
  should decide whether joining a `confirming` match sends one.
- **Delivery fallback.** The chunk 9 proposal (push retries, then email) is still waiting
  for an answer, so pushes are still sent in-process after commit, not as Celery tasks.
- **Local worker pool.** `make worker` uses `--pool=threads`: on this Mac with Python 3.14
  Celery's default process pool fails every task ("not enough values to unpack"). Production
  on Linux can use the default pool.

## Chunk 12: Answering Confirmations

- **When replies open.** Question: FR-3 says a Player can change their answer "at any time
  before the cutoff"; can they answer before the T-36h Confirmation goes out? Choice: no.
  Replies are open only while the Fixture is `confirming` (from T-36h, or when a later
  chunk moves it there) and before the cutoff. Before that the match screen says "Replies
  open when the Confirmations go out." Why: the answer is an answer to the Confirmation;
  early answers would need the T-36h Confirmation to know about them. If the answer
  differs: allow `scheduled` in `fixtures/confirmations.py` `_refuse_if_closed` and skip
  answered Players in `send_confirmations`.
- **The cutoff.** Choice: `readiness_hours_before` kick-off (T-6h) from the Club's
  settings, checked by the backend on every answer, whichever way it comes in. Answers at
  or after it are refused (409). Why: FR-3, FR-5 and the chunk 11 decision.
- **Where the answer lives.** Choice: a `ConfirmationAnswer` per Fixture, Player and
  kick-off, changed in place; the Player's Confirmation Notification is kept in step both
  ways. Why: a Player who didn't opt into the Night's notifications gets no Confirmation
  (targeting rule) but is still in the Team and must be able to answer, and the T-6h
  readiness check needs one place to count. A changed kick-off (reschedule) starts with
  no answers. If the answer differs (keep answers across a reschedule): drop `kick_off`
  from the lookups in `fixtures/confirmations.py`.
- **History of changed answers.** Choice: only the current answer and when it was given
  are kept, not every change. Why: answers are not money and the PRD asks for none. If
  the answer differs: add an append-only log like FixtureTransition.
- **Who sees replies.** Choice: a Team's Players (its Captain too) see their own Team's
  replies: each Player's name and answer, the counts, the Division minimum and whether the
  Team is below it. They don't see the other Team's replies. Admins get both Teams' replies
  with the T-6h queue (chunk 13). Why: FR-38 says "Team members", and the other Team's
  squad is theirs. If the answer differs: return both Teams from the squad endpoint.
- **Who counts.** Choice: confirmed answers of Players in the Team now. A Player who
  answered and then left the Team no longer counts or shows. Borrowed Players (FR-37) are
  added in chunk 17.
- **A Player who joins after T-36h** (from chunk 11). Choice: no Confirmation is sent to
  them; they answer on the match screen. Why: the smallest change; the PRD names no
  notification for it. If the answer differs: notify on joining a `confirming` match.
- **Wording.** The squad hint says "Your team needs n more by Tue 13:40 or it's out of the
  match." (FR-5: the Team's participation is cancelled, not necessarily the match.)
- **A Player who moves between the two Teams of a match** (chunk 12 review). Choice: an
  answer counts only for the Team it was given for; after the move the Player shows as
  Waiting in the new Team and answers again on the match screen. Why: a "playing" given
  for one side must not lift the other side over its minimum at T-6h (FR-5). If the answer
  differs: carry the answer over to the new Team on the move.

## Chunk 13: T-6h readiness

- **What "paid" means before Payment Barcodes exist.** Question: FR-6 says a Team plays
  only with a valid Payment Barcode; Barcodes come in chunk 20. Choice: at T-6h a Team is
  unpaid when its ledger balance (chunk 8 `team_balance`, every category) shows anything
  still owed. Why: the prompt says "from the chunk 8 ledger", and an unpaid Team is never
  ruled out automatically, so counting too much as unpaid only adds a ruling for the
  Admin. If the answer differs: count only the league fee, or check the Barcode once
  chunk 20 exists (`fixtures/readiness.py` `_assess_team`).
- **Short and unpaid.** Choice: a Team below the minimum is out at T-6h whether or not it
  has paid; it is not queued for the Admin. Why: FR-5 is automatic; FR-6 only covers
  whether an unpaid Team may play. If the answer differs: queue it instead.
- **A match whose Confirmations never went out** (Beat was down, or the match was added
  less than 6 hours before kick-off). Question: FR-5 would rule both Teams out with 0
  confirmed, though no one could answer. Choice: both Teams wait for the Admin (reason
  "Confirmations didn't go out"), and a match the Admin lets go ahead moves straight from
  `scheduled` to `ready` (a new allowed move). Why: never punish Teams for the app's
  failure; nothing decided without the Admin. If the answer differs: apply FR-5 as written
  (0 confirmed is out) in `_assess_team`.
- **When the match status moves.** Question: with one Team out by the minimum and the other
  waiting for the Admin, does the Fixture move to `one_team_out` at once? Choice: no; it
  stays `confirming` until every Team is decided, then moves once to `ready`,
  `one_team_out` or the new `both_teams_out`. Why: one status move, one hand-off to chunks
  14 and 15, and no move from `one_team_out` to `both_teams_out` to undo a replacement
  search already started. The Admin decides within the 6 hours before kick-off. If the
  answer differs: move at once and add `one_team_out` to `both_teams_out`.
- **No deadline for the Admin's ruling.** Choice: a waiting Team waits until the Admin
  rules, even past kick-off, while the match is still `scheduled` or `confirming`. Nothing
  rules it automatically (prompt: "Nothing is decided automatically"). Tonight keeps
  showing it until then.
- **"Mark paid (cash)" in the f11 design.** Choice: the button is "Let {Team} play"; it
  records the ruling only and moves no money. Why: recording a cash payment is a ledger
  action of the payments chunks, and the prompt's choice is "play (for example cash at
  the gate) or out". If the answer differs: record the cash payment in the same step once
  the Admin cash flow exists.
- **Late check.** Choice: the readiness check runs at the T-6h cutoff, or late while
  kick-off is still to come; never after kick-off. It runs before the Reminder in the same
  pass, so a match that is out is not reminded (its Teams hear from chunks 14 and 15). A
  match still waiting for the Admin is reminded, since it may go ahead.
- **Tonight.** Choice: the Club's Fixtures kicking off on today's South African date, plus
  any Fixture with a Team still waiting for a ruling. "At risk" (decided by the backend):
  a Team waits for a ruling, or the check is still to come and a Team is below the
  minimum or owes money. The money summary row and the Referee's Tonight come later.

## Chunk 14: One Team out: replacement opponent

- **What "eligible" means (FR-15).** Question: the PRD does not say which Teams the slot is
  offered to. Choice: an active Team of the same Club, Season and Division, not either
  Team of the match, that owes nothing on the ledger, has no other match that day (South
  African date, not cancelled), and whose Captain has opted into the Night. Why: the same
  Division keeps the match fair and keeps it a league match; owing nothing stands in for
  FR-6, since a Team that takes the slot after T-6h gets no readiness check of its own;
  one match a day avoids double-booking a Team; the opt-in is the targeting rule. If the
  answer differs: widen to every Division of the Night (or of the Club) in
  `fixtures/replacements.py` `eligible_teams` and `_why_not`; drop the money check to
  let the Admin rule on an unpaid replacement instead.
- **Who answers for a Team.** Choice: only its Captain gets the offer and can accept, by
  "Confirm" on a Confirmation-kind notification ("Open slot: play {Team}"). Why: Captains
  act for their Team everywhere else in the PRD; one answer per Team makes "the first
  Team to accept" exact. Declining only records the answer; the Captain can still change
  it to accept while the offer is open. If the answer differs: offer to every Player of
  each eligible Team and count a Team in once N of them accept.
- **How long the offer stays open.** Question: the PRD says only "if no replacement is
  found". Choice: a new club setting, `replacement_close_hours_before`, default 2 hours
  before kick-off, which must be fewer than the readiness hours. Why: configurable values
  are data (FR-42); 2 hours leaves the new Team time to get to the pitch and the Admin
  time for a friendly or cancellation. If the answer differs: change the default in
  `SettingsDefaults` (Django admin) and each Club's settings.
- **What happens to the Fixture.** Choice: the accepting Team takes the out Team's place
  (home or away) in the same Fixture; the out Team, the remaining Team and who accepted
  are kept on `ReplacementOffer` and in the Fixture's history. The match then moves to
  `scheduled` (accepted before the T-36h Confirmations; a new allowed move), `confirming`
  (before T-6h) or `ready` (after T-6h). Why: one Fixture per pitch and kick-off; every
  screen that shows a match's Teams keeps working. Side effects: the out Team's Players
  no longer see the match once replaced, and re-importing the original fixture row before
  kick-off finds no match and reports a clash.
- **Confirmations for a Team that takes the slot after T-6h (FR-15).** Choice: its Players
  get Confirmations they can answer until kick-off (the match is `ready`). Their answers
  only tell the Captain who is coming; the T-6h check has already run. Everyone else's
  cutoff stays T-6h. If the answer differs: send them as Updates instead.
- **Notifications.** Choice: FR-13 General ("{Team} is out of {match}", with "Find a
  match") to the out Team's Players; FR-14 Update ("{Team} withdrew") to the remaining
  Team's Players; FR-16 Update to the Night's Admins and the pitch's Referee when the
  offer opens (how many Teams, until when) and again when a Team accepts; an Update to the
  remaining Team naming its new opponent. Players only for the Nights they opted into.
  Nothing is sent when the offer lapses: FR-17's notifications are chunk 15's.
- **No Team accepts.** Choice: at the close time the offer lapses (checked every minute
  with the checkpoints), the offers close, and `replacement_lapsed` is sent; the match
  stays `replacement_offered` until chunk 15 makes it a friendly or cancels it. With no
  eligible Team, or the close time already past, it lapses at once. An offer whose match
  moved on (the Admin cancelled or rescheduled it) is withdrawn, with no hand-off.
- **Both Teams out.** No replacement search: chunk 15 (FR-10 to FR-12).

## Chunk 15: Friendly fallback or cancellation

- **Which payments become credit on a cancellation (FR-43).** Question: the league fee is
  charged once per Season (chunk 8), so a season payment isn't "for" one match; how much of
  it is a cancelled match worth? Choice: only payments recorded against the cancelled
  Fixture (ledger entries with that `fixture`: card, cash or credit) come back as credit,
  each to whoever paid it (FR-52), and only what is left of each (none twice; a reversed
  payment is skipped). Season-fee payments are untouched; an Admin can still issue credit by
  hand. Why: it never turns money that wasn't paid for this match into credit, and per-match
  payments (PayFast, Barcodes "per match", friendly fees) record their Fixture in later
  chunks. If the answer differs: add a per-match share of the season fee in
  `ledger.services.return_fixture_payments` (for example the fee divided by the Season's
  Fixtures), which needs no model change.
- **Charges for a cancelled match.** Choice: left as they are; the payment stays paid on
  the Team account (chunk 8) and its value goes to the payer's wallet. Why: reversing the
  charge as well would give the money back twice. If the answer differs: reverse an unpaid
  match charge in `fallbacks.cancel_match`.
- **Who is invited to a friendly.** Choice: both Teams out (FR-11): every Player opted into
  the Night who is in neither Team. No replacement (FR-17, "all Players outside it"): the
  remaining Team's Players and everyone in neither Team, opted into the Night. Goalkeepers
  and outfield Players alike (the Player and Goalkeeper Request split is for requests). The
  out Teams' Players get the General "Find a match" instead. If the answer differs: change
  `fallbacks._friendly_recipients`.
- **How a Player joins, until when, and how many.** Choice: "Confirm" on the friendly
  Confirmation joins, "Decline" doesn't; changeable until kick-off while the match is still
  a friendly for that kick-off; no cap on numbers. The Admin's fixture screen lists who
  joined. Why: the PRD gives no cutoff or cap; kick-off is the latest a Player can still
  turn up. If the answer differs: set `answer_by` in `fallbacks._open_friendly`, or refuse
  joins past a cap in `fallbacks.invite_answered` (a cap would be a club setting).
- **A fallback after kick-off.** Question: the Admin can rule both Teams out after
  kick-off (chunk 13 has no deadline). Choice: a match whose kick-off has passed is
  cancelled even when friendly-eligible. Why: no one can join a match that has started. If
  the answer differs: change `friendly` in `fallbacks.fall_back`.
- **Notifications on a cancellation.** Question: FR-17 says only "cancel it and apply
  FR-43". Choice: the out Team(s) get a General with "Find a match", the remaining Team an
  Update, and the Night's Admins and the pitch's Referee an Update (with the credit total);
  the Team messages say "Anything paid for this match is now credit" when credit was
  returned. No separate message to each credit holder. If the answer differs: notify each
  payer in `fallbacks._cancel`.
- **FR-17 after FR-13.** The out Team already had a General ("{Team} is out", chunk 14)
  when the search opened; FR-17 sends another when the match becomes a friendly or is
  cancelled, as the PRD lists it. If the answer differs: skip the out Team in
  `fallbacks._open_friendly` and `_cancel` for the `no_replacement` cause.
- **Friendly fees and the friendly's Captain (FR-24).** Not here: chunk 22. A friendly has
  no fee yet and nothing is charged to those who join.
- **Who decides friendly or cancelled.** Choice: the backend, at once, from the
  friendly-eligible flag the Admin set beforehand (PRD Decisions: "Only when the Admin
  lists the match as friendly-eligible"); the Admin isn't asked again.

## Chunk 16: Reschedules and Captain requests

- **Which matches can be rescheduled.** Question: the PRD says only "Admin reschedule".
  Choice: a match that is scheduled, confirming or ready, before kick-off. One that is out,
  offered to a replacement, a friendly, cancelled or played is refused (409). Why: those
  have their own flows (chunks 13 to 15), and moving a match mid-replacement would strand
  the offers. If the answer differs: widen `reschedules.OPEN_STATUSES` and withdraw open
  offers on a move.
- **How late a new kick-off can be set.** Question: FR-9 says Confirmations go out at once
  within 36 hours, but not what happens inside the T-6h cutoff. Choice: a new kick-off must
  be after the T-6h cutoff counted from now (`readiness_hours_before`), so Players can still
  reply before the readiness check. Why: a kick-off inside the cutoff would be checked at
  once with no replies and rule both Teams out. If the answer differs: allow it and let the
  Admin rule both Teams in at T-6h (chunk 13 already queues a match with no replies).
- **Where a new kick-off can go.** Choice: inside the Season and on the Division's Night
  (the same weekday), as the fixture import checks; the pitch must be the Club's and free at
  that kick-off; neither Team may have another match that South African day. Why: the same
  checks as the import, and a Team playing twice in a night is the conservative thing to
  refuse. If the answer differs (another weekday, two matches a night): relax
  `reschedules._check`.
- **A new pitch at the same kick-off.** Question: is a pitch-only move a reschedule that
  restarts the lifecycle? Choice: no. The answers, Confirmations and status stand (they are
  per kick-off); it can be made any time before kick-off, even after the T-6h check (a
  flooded pitch on the night). Both Teams' Players, the Night's Admins and the Referees of
  the old and the new pitch get an Update (FR-7, FR-8). Why: nothing about the time changed,
  and wiping replies at T-3h would rule the Teams out for nothing. If the answer differs:
  restart in `reschedules.reschedule` whenever anything changes.
- **What "the lifecycle restarts" does.** Choice: a new kick-off moves the match back to
  `scheduled`, closes its open Notifications (old Confirmations stop taking answers),
  and the Confirmations, resend, T-6h check and Reminder run again for the new kick-off.
  Within the Confirmation window they go out at once through the T-36h checkpoint (FR-9),
  logged as the Admin's move. Why: everything is already per kick-off (chunks 11 to 13),
  and the decision that a changed kick-off starts with no answers. If the answer differs
  (keep answers): see the chunk 12 entry.
- **One Update or two.** Choice: one Update to both Teams' Players (opted into the Night)
  and the officials together, so someone who is both gets it once. "The affected pitch" is
  the old and the new pitch when the pitch changes. If the answer differs: split the call
  in `reschedules.reschedule`.
- **What an accepted Captain cancellation does (FR-18).** Question: the PRD only says it
  takes effect once an Admin accepts. Choice: the Captain's Team is out of the match: it
  moves to `one_team_out` and the chunk 14 replacement search starts (FR-13 to FR-16),
  falling back to a friendly or a cancellation (FR-17, FR-43) when no Team takes the slot.
  This is the PRD's "One Team cancels" flow and what the chunk 7 lifecycle already
  describes. The withdrawing Team gets no credit while the match still goes ahead (as for a
  Team out at T-6h); everyone gets credit if the match is cancelled. If the answer differs
  (an accepted cancellation cancels the whole match): call `fallbacks.cancel_match` in
  `reschedules.accept` instead.
- **What an accepted postponement does.** Choice: the Captain gives only a reason; the
  Admin accepts by picking the new kick-off (and pitch), which is a reschedule with all its
  checks and notifications. Why: the Admin owns the schedule; Screens.md's Captain screen
  has no date picker. If the answer differs: add a proposed time to `CaptainRequest`.
- **Requests that no longer apply.** Choice: one pending request per Team and match. A
  reschedule to a new kick-off, or the other Team's cancellation being accepted, closes the
  other pending requests ("No longer applies") and tells their Captains. A request whose
  match moved on otherwise (cancelled, out at T-6h) can't be accepted (409) but can be
  declined. Requests can be made until kick-off. The Captain can withdraw a pending one.
- **Who is told about requests.** Choice: the Night's Admins get an Update when a request
  comes in; the Captain gets an Update on accept, decline or close (only if opted into the
  Night, as every Player). The PRD names no notification for these. If the answer differs:
  change `reschedules.request` and `_tell_captain`.
- **Admin cancels a match outright.** Not built: the chunk prompt covers reschedules and
  Captain requests only, although the PRD Admin role lists "cancel or reschedule fixtures"
  and Screens.md Admin 2 shows "cancel". `fallbacks.cancel_match` is ready for it. If
  wanted: an Admin cancel endpoint calling it, with FR-43 credit and notifications.
- **Moving a match back to a kick-off it already had (chunk 16 review).** Question: answers,
  checkpoints, readiness checks and replacement offers are all kept per kick-off, so moving
  a match A to B and back to A would bring back A's old answers and treat A's checkpoints as
  done (no new Confirmations go out). Choice: refuse (409) a reschedule to a kick-off the
  match already has any of these for; the Admin picks another time (19:45 instead of
  19:40). Why: the most conservative option that needs no model change and never revives
  stale replies. If the answer differs (allow it as a fresh start): key those records by a
  per-reschedule "round" instead of the kick-off.

## Chunk 17: Player and Goalkeeper Requests

- **Does a borrowed Player pay for a league match? (docs/DECISIONS.md open question 1).**
  Question: FR-24 sets a fee only for friendlies; the PRD names none for a borrowed Player
  in a league match. Choice: nothing is charged to a borrowed Player in this chunk; no
  ledger entry is made. Why: charging money the PRD doesn't name is the riskier guess, and
  payments come in chunks 18 to 22. If the answer differs: add a club-configurable fee
  (ClubSettings or Division) and a ledger charge in `borrowing.join`, or fold it into the
  chunk 22 friendly fees; the `BorrowedPlayer` record already says who joined which match.
- **Is the Captain told when a request fills? (open question 2).** Choice: yes, one Update
  to the requesting Team's Captain (if opted into the Night) once every place is taken,
  naming who joined. Not on each single join; the Match screen shows those as they come.
  Why: an informational Update is harmless and the Captain needs to know they are no
  longer short. If the answer differs: drop `_tell_captain_filled`, or call it per join.
- **How many places one request asks for.** Question: FR-37 speaks of "the slot";
  Screens.md Captain 4 says "pick Player or Goalkeeper and how many". Choice: a request has
  1 to N places, N being the Division's minimum players; the first N to accept join. One
  open request per Team, match and kind. Why: matches the screen and keeps it to one
  Notification per Player. If the answer differs (always one): fix `places` at 1.
- **When a request can be raised and answered.** Choice: while the match is scheduled,
  confirming or ready, before kick-off; answers are taken until kick-off. Why: "a Captain
  who expects to be short" can know early (FR-38), and a borrowed Player still helps after
  T-6h. A request stops applying when the match moves to a new kick-off, its Team leaves
  the match, or it is out, a friendly or cancelled. If the answer differs: change
  `borrowing.can_raise` and the Notification's `answer_by`.
- **Does a borrowed Player count towards the Division minimum at T-6h (FR-5)?** Choice:
  yes, as confirmed for the requesting Team at that kick-off; they also show in the squad
  (FR-38). Why: that is the point of borrowing ("keeps turn-up rates and the league
  schedule stable"). If the answer differs: drop the borrowed count in
  `confirmations.confirmed_count`.
- **Can a borrowed Player leave after accepting?** Choice: no, their answer is final once
  they join (their Notification closes). The Captain can withdraw the request; who joined
  keeps their place. Why: leaving would reopen places and re-notify, which the PRD doesn't
  describe; a no-show is the same risk as a Team Player's. If the answer differs: add a
  leave action that removes the place before the T-6h cutoff and reopens the request.
- **No one to ask.** Choice: a request with no one to send it to is refused (409) and the
  screen says so before sending. Why: a request no one can see would mislead the Captain.
- **Other checks on who can join.** A Player joins only one Team per match (database
  constraint), must still be outside both Teams, opted into the Night and of the right
  position when they accept. Not checked: whether they play another match that night.
  If the answer differs: add that check to `borrowing.join` and `borrowing.recipients`.

## Chunk 18: PayFast payments (backend)

- **Whose PayFast merchant account takes a club's card payments? (open question 5 in
  DECISIONS.md)** Question: does each club have its own merchant account, or do all card
  payments go to one account? Choice: both are configuration only. One default merchant
  account from the environment (`PAYFAST_MERCHANT_ID`, `PAYFAST_MERCHANT_KEY`,
  `PAYFAST_PASSPHRASE`), and a club can have its own in `PAYFAST_CLUB_ACCOUNTS` (JSON keyed
  by Club id, also from the environment). Each Payment records the merchant id it was made
  with, and its ITN is checked against that account. Why: CLAUDE.md keeps secrets in the
  environment, and this way neither answer reworks models or money. If the answer
  differs: per-club accounts only: drop the default; if clubs must enter their own keys in
  the app, add encrypted per-club credentials (a security decision to make first).
- **Who chooses how much, and is it capped?** Question: FR-19 lets a Player choose their
  contribution; may it exceed what the Team still owes? Choice: from R 0.01 up to what the
  Team owes when the payment starts (409 above it, and 409 when nothing is owed). Two
  payments started together can still overpay when both are confirmed: the money was
  taken, so both are recorded and the Team shows below zero. Why: never refuse money
  PayFast already took; an Admin can return the overpayment as credit. If the answer
  differs: count pending card payments against what is owed when starting one.
- **Card minimum.** Question: what is the smallest card payment? Choice: R 5 (PayFast's
  minimum), a property of the PayFast gateway, not a club setting. A card part under it
  is refused with a hint to use less credit. If the answer differs: change
  `PayFastGateway.minimum_amount`.
- **Credit first.** Question: how is "spending Player or Team credit first" chosen?
  Choice: the Player picks `credit`: none, their own (`player`), or the Team's (`team`,
  Captain only, FR-52). As much credit as is held, up to the amount, is spent at once (a
  ledger payment with method credit); the rest is the card part. Credit covering it all
  completes with no card. If the card part is then abandoned, the credit stays spent: it
  is a real payment towards what the Team owes. Why: credit is the holder's to spend and
  spending it is immediate. If the answer differs: hold credit until the card part is
  confirmed (needs a pending-credit step in `ledger.services`).
- **Who sees what is owed.** Question: chunk 8 shows a Team's balance only to its Captain
  and Admins; what does a Player see before paying? Choice: a Player in the Team sees due,
  outstanding and paid or not (`GET /api/v1/teams/{id}/payments/options/`), not the
  payment lines. Team credit is shown only to the Captain. Why: FR-19 needs the Player to
  know the total to choose a share; FR-21 keeps "who paid" for Captains and Admins. If the
  answer differs: drop `due` and `outstanding` from the options.
- **"Team marked paid" (FR-20).** Question: is "paid" stored? Choice: no, computed: an
  active Team that owes nothing (`is_paid` on the balance). When a payment (card, cash or
  credit) takes what is owed from above zero to zero or below, `payments.signals.team_paid`
  is sent, for the Barcode chunk. A reversal later makes it unpaid again. Why: a stored
  flag would go stale on reversals. If the answer differs: store `paid_at` on Team.
- **A confirmed card payment from a Player who left the Team.** Choice: recorded anyway
  (`record_payment(..., money_taken=True)`), named for that Player and Team. Why: the
  money was taken. If the answer differs: record it as Player credit instead.
- **A COMPLETE ITN after a FAILED or CANCELLED one.** Choice: recorded, and the Payment
  becomes complete; a complete Payment never goes back. Why: PayFast's COMPLETE means the
  money is taken.
- **Cash (FR-22).** Question: who records cash, and how much? Choice: an Admin of the
  Team's Club, in either payment mode, for a Player in the Team or for the whole Team, up
  to what the Team owes (409 above it), with an optional reason ("Cash paid to the club"
  by default). A cash payment for the whole Team becomes Team credit if returned (FR-52).
  If the answer differs: change `payments.services.record_cash`.
- **ITN source behind a proxy.** Choice: the connecting address, unless
  `PAYFAST_TRUSTED_PROXIES` says how many proxies add to X-Forwarded-For; then it is read
  from the right, so a caller can't add an address of their own. PayFast's networks are
  `PAYFAST_ITN_NETWORKS`, defaulting to PayFast's published list. If the answer differs:
  set the variables; no code change.
- **Return to the app.** Choice: `PAYMENT_RETURN_URL` and `PAYMENT_CANCEL_URL` (env) get
  `?payment=<reference>`, so the app can show the result with
  `GET /api/v1/payments/{reference}/`. The ITN, not the return, records the payment.
  Chunk 19 decides the URLs (a deep link or a web page).

## Chunk 19: Payments (UI)

- **Return from PayFast to the app.** Question: should PayFast's return page reopen the
  installed app by itself (universal links / app links), or is closing the in-app browser
  enough? Choice: no deep links yet. The installed app opens PayFast in the in-app browser
  (@capacitor/browser, `frontend/src/native/browser.ts`); when the Player closes it, the
  app shows the payment's result screen. In a browser the tab goes to PayFast and comes
  back to `PAYMENT_RETURN_URL` / `PAYMENT_CANCEL_URL`, which are the app's
  `/payments/done` and `/payments/cancelled` (with `?payment=<reference>`). Why: works
  with the chunk 18 URLs and needs no store-side configuration; the ITN, not the return,
  records the payment either way. If the answer differs: add @capacitor/app's
  `appUrlOpen`, an apple-app-site-association and assetlinks.json for the web host, and
  close the in-app browser on return. No API change.
- **Where "Pay my share" starts.** Question: Screens.md says the amount "defaults to the
  per-player share"; what is the share? Choice: what the Team owes (its fee) divided by
  its current Players, rounded up to the cent, less what this Player has already paid,
  never more than the Team still owes. Once the Player has paid their share, the share is
  suggested again (still capped). Computed by the backend
  (`payments.services.suggested_amount`, `suggested_amount` on the payment options). The
  Player can change it. Why: the PRD lets each Player choose (FR-19) and has no per-player
  fee; the frontend must not compute money. If the answer differs: change
  `suggested_amount` only (for example the Division minimum instead of the squad size).
- **What the Captain sees of who has paid (FR-21).** Question: amounts per Player, or only
  paid / unpaid? Choice: what each Player has paid, net of refunds and reversals, and
  "Unpaid" for nothing; Players who paid and have since left are listed as such, and what
  was paid for the whole Team (Team credit, cash for the Team) is its own line. New
  endpoint `GET /api/v1/teams/{id}/payments/summary/` for the Captain and the Admins of
  the Team's Club (404 for anyone else); Team credit in it only for the Captain. Why: the
  design's PaymentProgress rows show an amount per Player, and the sums must come from the
  backend. If the answer differs: drop `paid` from `PlayerPaid` and keep `has_paid`.
- **Who sees "Pay my share".** Choice: every Player in an active Team, the Captain too,
  even when the Team has paid (the pay screen then says there is nothing left to pay).
  Why: one place to pay; the backend refuses anything over what is owed.
- **Admin cash screen.** Choice: Payments, opened from Profile per club, lists the club's
  active Teams (unpaid first, from chunk 18's endpoint); a Team opens who has paid and a
  Record cash form (amount, the whole Team or one current Player, optional note). No
  Season filter yet. If the answer differs: add the `season` filter the endpoint already
  takes.

## Chunk 20: Payment Barcodes

- **"Per match" when the league fee is per Season.** Question: the league fee is charged
  once per Season (chunk 8), but with the gateway a Barcode is "valid per match". Which
  match is it for, and when is the next one issued? Choice: a paid Team's Barcode is for
  its current match: its first match not cancelled or played, on today's date (South
  African time) or later. It is issued when the Team becomes paid (`team_paid`) if that
  match exists, otherwise the first time the Captain opens the Barcode screen; each later
  match gets its own Barcode the same way. It stops being valid after its match's day, or
  when the match is cancelled or played. Why: one Barcode can't be reused at another match
  (NFR Barcode integrity), and the Season's payment still covers every match. If the answer
  differs: issue per payment instead (needs a per-match charge, chunk 22's friendly fees
  are the model), or change `barcodes.services.next_match` and `status_of`.
- **Issuing on opening the screen.** Question: `GET /api/v1/teams/{id}/barcode/` can create
  the Barcode for a paid Team's next match. Choice: yes, once per match (the same Barcode
  every time after). Why: no timed job is needed, and the Captain gets it when they need it.
  If the answer differs: a Celery Beat job issuing them the day before each match.
- **Cash-only mode.** Question: "Admin confirms payment in the app; Barcode sent to the
  Captain". Is recording cash the confirmation, or is there a separate step? Choice:
  recording the cash that makes the Team paid issues the Season Barcode by itself and tells
  the Captain (an Update notification). An Admin can also issue or reissue one by hand,
  but only for a paid Team. Validity follows the club's payment mode when it is issued, not
  how the Team paid: in gateway mode, cash paid to the club still gives per-match
  Barcodes. Why: the ledger says whether the Team has paid; nothing else should. If the
  answer differs: a separate "Confirm and send Barcode" Admin step (`issue` exists).
- **What makes a Barcode valid.** Choice: genuine (its signature checks), not revoked, not
  past its match or Season, and its Team active and still paid (a reversed payment makes
  it invalid at once; paying again makes the same Barcode valid again). Checked live at
  every look and every scan, not stored. Why: a stored flag goes stale on reversals. If
  the answer differs: revoke Barcodes on a reversal instead.
- **Revoking.** Question: who may revoke, and does a revoked Barcode come back by itself?
  Choice: only an Admin of the Team's Club, with a reason. A revoked Barcode is never
  replaced automatically, so revoking blocks the Team until an Admin issues a new one.
  Reissuing revokes the live one for the same match or Season ("Reissued by an Admin.").
  Why: revoking is for a leaked or misused Barcode; the app giving the Captain a new one
  at once would undo it. If the answer differs: let the Captain's screen issue a new one
  after a revocation.
- **Who sees the Barcode.** Choice: the Team's Captain, and the Admins of its Club (to help
  at the gate); nobody else (404). Players of the Team don't. Why: PRD "Captain: receive
  the Payment Barcode". If the answer differs: let any Player in the Team open it.
- **The code and what "signed" means.** Question: the design prints a 10-character code
  ("RL 2710 4419") that the gate can type in. How is that signed? Choice: the code is the
  first 50 bits of an HMAC-SHA256 (Crockford base32, 10 characters, no I, L, O or U) over a
  random nonce and the whole subject (club, Team, mode, Season, match), keyed by
  `BARCODE_SIGNING_KEY` from the environment (falls back to a key derived from
  `DJANGO_SECRET_KEY`; production requires its own). Unguessable (50 bits, looked up only
  by the club's signed-in Referees and Admins), can't be made or moved to another Team
  without the key. The barcode is a Code 128 of the same code, so scanning and typing
  check the same thing. Why: one short code serves both the camera and the typed fallback
  in the design. If the answer differs: a longer signed payload in the barcode (a QR code)
  with the short code only for typing; the model keeps its nonce, so only signing.py and
  the ticket change.
- **Changing the signing key.** Choice: every Barcode issued before fails its check
  ("not genuine") and Admins reissue them. Why: the key is the only thing that makes a
  code genuine. If the answer differs: keep the old key as a second key to check against.
- **Bookings.** Question: Barcodes are "tied to one Team or Booking"; Bookings don't exist
  yet. Choice: a Barcode's subject is a Team now; chunks 23/24 add a Booking foreign key
  and a constraint that exactly one of the two is set (a migration making `team`
  nullable, no rework). If the answer differs: nothing to change now.
- **Every scan logged.** Choice: `BarcodeScan` (append-only) records every scan or typed
  code: club, Barcode (or none), the code as entered, camera or typed, who, when, paid or
  not and why, and the match when the gate says. The scan endpoint, the right-match check
  and single use per match are chunk 21; `barcodes.services.scan` already logs and checks
  everything above, only within the scanning club.
- **Brightness.** Screens.md: "full screen at max brightness". Choice: not yet; the screen
  asks the Captain to turn brightness up. Why: needs a native plugin
  (e.g. @capacitor-community/screen-brightness) and a device to test on. If the answer
  differs: add it behind frontend/src/native/.

## Chunk 21: Gate scanning

- **Which match a scan is for.** Question: FR-23 says the gate shows whether the Team has
  paid; the chunk asks for "right Fixture". How does the gate know the match? Choice: the
  scan may name a match (`fixture`, optional in the API); otherwise a per-match Barcode is
  checked against its own match and a Season Barcode against its Team's match today (the
  first one still on that it hasn't been let in for). The screen doesn't ask for a match
  yet. Why: the gate is the club's entrance, and a Referee scanning at speed shouldn't have
  to pick a match first. If the answer differs: a match picker on the scan screen (the API
  already takes `fixture`).
- **Valid only today.** Choice: the match must be today (South African date). A Barcode for
  a later match reads "Not paid: this Barcode is for Tue 3 Nov. It isn't valid today."; an
  earlier one already read "no longer valid" (chunk 20). Why: the design's Not paid example
  is an old pass; a future pass is the same mistake. If the answer differs: let a future
  match's Barcode in with a warning.
- **Single use.** Question: "not reused where single-use": what counts as one use? Choice: a
  Barcode lets its Team in once per match, per-match and Season Barcodes alike (a Season
  Barcode once for each of the Team's matches). A second scan for the same match reads Not
  paid: "Already scanned at 19:21 by Rita. A Barcode lets its Team in once per match." The
  Barcode row is locked during the check and a unique constraint (one Paid scan per Barcode
  and match) stops two gates letting it in at once. Why: NFR "impossible to reuse"; the
  Captain shows one Barcode for the whole Team. If the answer differs (an accidental
  rescan should read Paid again): drop the "used" check for scans by the same person within
  a few minutes, or let an Admin undo a scan; the constraint would move to a flag.
- **Ruled out or match off.** Choice: a Team ruled out at T-6h (`TeamReadiness` out), or a
  match cancelled, played or with both Teams out, reads Not paid with that reason, even with
  a valid Barcode. Why: FR-6, a Team only plays when it is in the match. If the answer
  differs: show Paid with a warning line instead.
- **Who may scan.** Choice: every Admin and Referee of the club, at any of the club's
  matches (not only a Referee's own pitch). Others get 403. Only the club's own Barcodes are
  found. Why: PRD roles "Referee: scan a Barcode to confirm a Team has paid", the gate is one
  entrance per venue. If the answer differs: limit Referees to Fixtures on their pitch
  (`Field.referee`) when the scan names one.
- **What the result shows.** Choice: Paid or Not paid in large type, the Team, the match
  (opponent, time, pitch; the date when not today), the reason, the code, "This match only"
  or "Until <date>", and on Paid what the Team paid and how ("R 350 · card"). Referees see
  the amount too. Why: the design (f13-scan.mjs). If the answer differs: hide the amount from
  Referees.
- **Camera plugin.** Choice: the official `@capacitor/barcode-scanner` (Ionic): its own
  full-screen camera view with a torch button, Code 128 hint. The design's own framed camera
  overlay (`la-scan`) isn't built: the plugin draws its own. Why: an official plugin that
  works on iOS and Android with no custom native code, opened from one wrapper
  (frontend/src/native/scanner.ts). If the answer differs: `@capacitor-mlkit/barcode-scanning`
  with a transparent WebView and the design's overlay.
- **Rate limit.** Choice: 60 scans per minute per signed-in Admin or Referee
  (`BARCODE_SCAN_THROTTLE_RATE`). Why: a busy gate stays far below it, guessing codes can't.
  If the answer differs: change the environment value.

## Chunk 22: Friendly fees

- **What "a specified fee" is.** Question: FR-24 says a friendly charges "a specified fee";
  is it per Player or for the whole match? Choice: one fee for the whole friendly (the
  `FriendlyFee.fee`), starting at the club's `friendly_fee` setting and changeable per
  match; the payers' contributions add up to it, as Team contributions do for the league
  fee (FR-19). Why: "a fee" per match reads as one amount, and it can't be split before
  anyone knows who will turn up. If the answer differs (a fee per Player): charge each
  joined payer in `fixtures/friendlies.py` and change `totals`.
- **Who "the borrowed Players" and "the Team's Players" are.** Choice: borrowed Players are
  the Players who joined the friendly (confirmed its invite) from outside the Team still in
  it; the Team's Players are the current Players of the Team still in it (FR-17). With both
  Teams out (FR-10 to FR-12) there is no Team, so "the Team's Players" isn't offered (409).
  Why: those are the only Teams and Players the friendly has. If the answer differs: change
  `friendlies.team_players` / `borrowed_players` and `payer_choices`.
- **What "the club/manager pays" means.** Question: is it income to record, or the club
  covering the fee? Choice: the club/manager covers it: nothing is collected from Players,
  no ledger entry is made, and the friendly counts as paid (its Barcode can be issued). A
  fee of R 0 works the same way. Why: the club paying itself isn't income, and charging
  Players nothing is the conservative side. If the answer differs (a manager hands over
  cash): let `record_cash` take a payment for the club/manager payer.
- **How a friendly is paid.** Choice: in this chunk an Admin records cash from one of the
  payers, never more than is still owed; each is a ledger payment in the `friendly`
  category for the Fixture, subject the paying Player, on no Team's account (so no Team's
  league balance, Barcode or replacement eligibility changes). Card payments (PayFast) and
  spending credit on a friendly are not built: chunk 18's `Payment` is tied to a Team and
  would need a friendly subject. Why: the smallest change that keeps payments and the
  Team accounts as they are. If the answer differs: add a friendly subject to `Payment`
  and a `start_friendly_payment` beside `payments.services.start_payment`.
- **When the terms can change.** Choice: while the match is a friendly for that kick-off
  and before kick-off. The fee and payer are fixed once a payment stands (409); the Captain
  can change at any time until then. Why: changing what was owed after money came in
  would rewrite a settled amount. If the answer differs: allow raising the fee and keep the
  payments.
- **Who can be the friendly's Captain.** Choice: a Player who plays in it: one who joined
  it, or a current Player of the Team still in it. Not set automatically; the Admin picks.
  Why: FR-24 says the Captain "is assigned", and they must be at the gate. If the answer
  differs: default it to the remaining Team's Captain.
- **The friendly's Barcode.** Question: Barcodes are tied to one Team, but a friendly with
  both Teams out has none. Choice: a Barcode's subject is a Team or a friendly
  (`Barcode.friendly`, exclusive with `team`, signed over the friendly too). It is issued
  when the friendly is settled (paid, free or paid by the club) and has a Captain, valid
  for that match while it is still a friendly; the Captain is told and sees it under My
  fixtures. A new Captain revokes the old one's. A Team's own league Barcode no longer
  lets it into a match that became a friendly (and a Team's "current match" skips
  friendlies). Why: only the assigned Captain has the friendly's Barcode verified (FR-24),
  and it can't be reused at another match (NFR Barcode integrity). If the answer differs
  (the Team's Barcode also counts for its friendly): drop the `friendly` check in
  `barcodes.services._at_the_gate` and `NOT_LEAGUE` in `next_match`.
- **A cancelled friendly.** Choice: its friendly payments come back as the Player's credit
  (FR-43, FR-52) through the existing `cancel_match`; its Barcode stops being valid.
- **Who is told.** Choice: only the Captain, when the Barcode is issued (an Update). The
  payers aren't sent the fee. Why: the PRD names no notification for it, and the
  targeting rules say to send only what it names. If the answer differs: an Update to the
  payers in `friendlies.set_terms`.

## Chunk 23: Bookings

- **How long a league match holds its pitch.** Question: "no clash with Fixtures" needs a
  match length; the PRD gives none (chunk 7 compared kick-offs only). Choice: a new club
  setting `match_length_minutes`, empty until the Admin sets it (like the fees), counted
  from kick-off. Bookings aren't taken until it and the booking hourly fee are set; Setup
  lists both as missing. Why: a guessed default would be a constant in disguise, and an
  overlap can't be judged without it. If the answer differs (a default, or per Division):
  seed `SettingsDefaults.match_length_minutes`, or move it to `Division`, and read it in
  `bookings/services.match_length`.
- **Which start times are offered.** Question: the PRD says "available fields and times"
  but gives no opening hours. Choice: whole hours (South African time), still to come, for
  1 to 24 whole hours, ending by midnight of the day it starts; any hour of the day, since
  every booking is approved by an Admin anyway. Why: no opening hours are configured, and
  inventing them would be a constant. If the answer differs: add opening and closing hours
  to ClubSettings and filter in `availability` and `check_slot`.
- **What holds a field.** Choice: pending and accepted Bookings, and every Fixture that
  isn't cancelled. A declined or cancelled Booking frees it. Accepting re-checks Fixtures,
  so a Fixture imported after the request blocks the accept (409). Why: holding pending
  requests is the only way two Admins can't accept two overlapping ones. If the answer
  differs: let only accepted Bookings hold a field and check again on accept.
- **Fixtures over a booked field.** Question: should a Fixture import or a reschedule onto
  an accepted Booking be refused? Choice: not in this chunk; the booking side is checked
  only. Why: chunk 23 is about bookings, and refusing fixtures changes chunk 7 and 16. If
  the answer differs: check `bookings.services.clashing_bookings` in `fixtures/imports.py`
  and `fixtures/reschedules.py`.
- **Who is asked, and what an answer does.** Choice: every Admin of the club gets the
  Booking Notification (Confirm / Decline), answerable until the booking starts; the first
  answer decides it and closes every Admin's copy. The Booking User gets an Update when it
  is accepted or declined (with the reason if given); the Admins get an Update when an
  accepted booking is cancelled. Referees are not told. Why: the PRD's Booking row names
  Admins only; "a Night's Admin" doesn't apply to a booking. If the answer differs: change
  `targeting.booking_recipients`.
- **Rescheduling.** Question: does a reschedule need the Admin again? Choice: yes. It moves
  the booking in place to the new field, time and hours (same club), it waits for an Admin
  again, and its Barcode is revoked until then; the old time is released at once. The
  price is the hourly fee it was first booked at times the new hours. Why: an Admin
  approves each booking (FR-29), so a new slot is approved too. If the answer differs
  (the original time kept until the new one is accepted, or no new approval): keep the old
  slot in a separate change request, or skip `_ask_admins` and keep the status in
  `bookings.services.reschedule`.
- **The hourly fee.** Choice: fixed on the booking when requested (`hourly_fee`), so the
  price doesn't change if the club changes its fee later. Why: the user saw that price.
  If the answer differs: read the club's fee at payment time in chunk 24.
- **Is a Booking's Barcode "paid" before payments exist?** Question: FR-30 sends the
  Barcode on acceptance, but payment comes with chunk 24. Choice: the Barcode is issued
  on accept and shown to the Booking User, but it counts at the gate only when the booking
  owes nothing: until chunk 24 takes booking payments, only a R 0 booking is let in; any
  other scans as "Not paid" with what is owed. Why: the gate never lets in what hasn't been
  paid. If the answer differs: chunk 24's `bookings/money.paid` fills it in.
- **Who checks a booking at the gate.** Question: the PRD's roles say Admins scan "Team
  and Booking User payment", Referees "a Team". Choice: only the club's Admins; a Referee
  scanning a booking's Barcode gets "Only an Admin checks a booking's Barcode". Valid on the
  booking's day only, once per booking. Why: least access the PRD allows. If the answer
  differs: drop the Admin check in `barcodes.services.scan`.
- **Barcode subject.** Choice: `Barcode.booking` is a third exclusive subject, mode
  `booking`, with no Season (`season` is now nullable, but only for a booking's Barcode),
  signed over the booking. Why: chunk 20's note planned it. If the answer differs: nothing
  to change.
- **What the cancellation costs.** Not decided here: the policy outcome (free, 50% credit,
  none) and showing it before confirming come with chunk 24. In this chunk nothing is paid,
  so nothing is returned.

## Chunk 24: Booking payments and cancellation policy

- **How PayFast holds card details for a later charge (tokenisation, FR-32).** Question: the
  chunk prompt asks this before building it. Choice: no card details or card tokens are held
  at all. At the club's payment cutoff the app spends the Booking User's credit and asks
  them (an Update notification, and Pay on the booking) to pay the rest on PayFast's hosted
  page, the chunk 18 flow. Why: nobody could answer during the unattended run, and holding
  nothing is the most conservative choice for PCI scope and consent; it reuses a verified
  flow. If the answer differs (PayFast tokenisation / ad hoc subscriptions): add a token
  model and a `charge_token` method to `payments.gateways.PaymentGateway`, capture the
  token at the first booking payment (or at sign-up for FR-32), and charge it in
  `bookings.services.take_payment` instead of asking. Models used here don't change.
- **What "payment is taken" means without a stored card.** Choice: the cutoff moment
  itself. At the cutoff the Booking's `payment_taken_at` is set, credit is spent, and the
  user is asked for the rest; from then on cancelling is never free. A booking still unpaid
  at its start is not cancelled automatically: its Barcode reads Not paid at the gate, and
  an Admin can record cash or cancel it for the club. Why: the PRD ties the free window to
  the cutoff; cancelling someone's booking automatically is a bigger step than the PRD
  asks for. If the answer differs: add an automatic cancel for unpaid bookings to
  `take_due_payments` (e.g. at the late-cancel time).
- **Percent of what?** Question: "50% credit" of the price or of what was paid? Choice: of
  what was paid (card, cash and credit spent), rounded half a cent up. Nothing unpaid is
  owed once a booking is cancelled. Why: the policy says value is returned as credit; the
  ledger can only return money it holds, and nothing in the app chases debts. If the answer
  differs: post a booking charge for the kept part and track it as owed.
- **Paying early.** Choice: card payment is offered only from the cutoff (FR-34 "only at a
  club-configured time"). An Admin may record cash at any time once the booking is accepted;
  cash paid before the cutoff of a booking then cancelled in the free window comes back in
  full as credit (credit, never cash). Why: keeps the free window free. If the answer
  differs: allow `pay` before the cutoff in `payments.services.start_booking_payment`.
- **Late reschedule rules.** Choice: allowed `booking_reschedules_allowed` times per booking
  (counted from the log, window `late`), to a slot starting no later than
  `booking_reschedule_window_days` after the booking's current start; under the late-cancel
  hours not at all. Before the cutoff (and before payment was ever taken) moves are free and
  unlimited. A booking moved after payment was taken never gets the free window back. Why:
  the PRD's "Free, once, to a slot within 30 days" with the club's own numbers; anchoring on
  the current start keeps the user's 30 days. If the answer differs: change
  `policy.reschedule_outcome`.
- **Moving to fewer or more hours.** Choice: fewer hours: what was paid over the new price
  comes back as credit at once. More hours: the difference is owed and taken at the new
  slot's cutoff (or at once if that has passed) when the Admin accepts the move. Why: a free
  reschedule shouldn't cost the user the hours they gave up. If the answer differs: keep the
  excess as a club gain in `services.reschedule`.
- **When the club cancels.** Choice: any Admin of the club can cancel a pending or accepted
  booking until it ends, with a reason the user is told; the club's percent (default 100%)
  of what was paid comes back as credit. "Card refund on request" is not built: the policy
  row tells the user to ask the club, which refunds outside the app. An Admin declining a
  rescheduled booking that was paid returns the same club percent. Why: refunds need the
  PayFast refund API and the club's say on who may refund. If the answer differs: add a
  refund action that calls the gateway and posts a `refund` ledger entry.
- **No-shows.** Choice: an accepted booking that ended without a Paid scan of its Barcode is
  a no-show: the club's no-show percent (default 0) of what was paid comes back as credit,
  once (`Booking.settled_at`), and the log records it. Why: the policy's "or no-show" row,
  read from the gate scans. If the answer differs: change `services.settle`.
- **Credit used before card (FR-46).** Choice: the Booking User's credit at the booking's
  club is spent automatically, at the cutoff and again when they press Pay, but always
  leaves at least the gateway's smallest card amount (R 5 on PayFast) for the card so the
  rest can be paid. Credit is spent on the user's behalf by the app (recorded by no one).
  Why: FR-46 says it is used before card; leaving R 4 owed that no card can pay would strand
  the booking. If the answer differs: change `services._credit_to_spend`.
- **Card payments after a cancel.** Choice: a card payment PayFast confirms for a booking
  already cancelled or declined is recorded and comes back in full as credit; anything paid
  over the price comes back as credit too. Pending card payments are closed on cancel,
  reschedule and decline. Why: money the gateway took is never lost.
- **Who sees a payment.** Choice: `GET /api/v1/payments/{reference}/` and `me/payments/` serve
  whoever made the payment (Booking Users aren't Players). Others get 404 as before.

## Chunk 25: Finance tracker (backend)

- **What "received" means when credit is involved.** Question: FR-25 asks for received
  split by card and cash; credit spent and credit returned are neither. Choice: `received`
  is card plus cash taken, less refunds and reversals: money the club actually took.
  Credit spent is its own figure (`credit_spent`) and counts towards what a Team has paid
  (so outstanding matches the Team ledger), but not towards received. Credit given back
  from payments is `returned_as_credit`; it does not reduce received. Why: a payment
  returned as credit and spent again would otherwise be counted twice as income, and the
  chunk 8 decision keeps a Team's paid amount unchanged when credit is returned. If the
  answer differs (e.g. income net of credit returned, or credit spent as income): change
  `IncomeLine.received` in `backend/finance/services.py`; no model changes.
- **Expected is from the ledger.** Question: "Teams x fee" could be the current fee times
  the active Teams. Choice: the league fees actually charged (each Team's fee is fixed when
  it is confirmed, chunk 8), less reversed charges; `teams` counts active Teams. Why: the
  chunk prompt says every figure is computed from the ledger, and a later fee change doesn't
  rewrite what a Team owes. If the answer differs: compute expected from
  `Division.effective_league_fee` x active Teams in `season_summary`.
- **Outstanding with an overpaid Team.** Choice: outstanding is summed Team by Team, and a
  Team that paid more than it owes counts as owing nothing (it doesn't hide another Team's
  debt). The Team ledger still shows its own negative outstanding. If the answer differs:
  sum the raw `expected - paid` instead (`_team_figures`).
- **Credit held per Night and Division.** Question: Player and Booking User credit is held
  per Club (chunk 8) and moves between Teams, so it has no Division. Choice: Team credit is
  shown per Division (its Teams'), Player and Booking User credit club-wide only, and only
  in the unfiltered view (null with a Night or Division filter). Credit held is the balance
  now, not as of the Season's end. If the answer differs: attribute Player credit by the
  Fixture or Team of the payment it came from, in `finance/services.py`.
- **Booking income in a Season.** Question: bookings have no Season, Night or Division.
  Choice: a Season's booking income is from Bookings starting within the Season's dates
  (South African time), club-wide; it is left out (null) when a Night or Division filter is
  set. Friendly income goes by the Fixture's Season and Division. If the answer differs:
  change `booking_line` (e.g. by payment date) in `finance/services.py`.
- **What a "League" is in FR-27.** Question: the data model has no League apart from a
  Night's league and its Divisions. Choice: "compare across Leagues and Nights" is income per
  Season, Night by Night (`GET /clubs/{id}/finance/comparison/?seasons=`), with league,
  friendly and booking lines; the summary already compares Divisions within a Night. Why: no
  new model on a guess. If a League is something else (e.g. several leagues on one Night):
  that needs a League model and is a later change.
- **Season is required on the summary.** Choice: `season` is a required query parameter;
  there is no "current Season" default. Why: the UI filters by Season (Screens.md Admin 5)
  and the app has no rule for which Season is current. If the answer differs: default to
  the Season whose dates include today.

## Chunk 26: Finance tracker (UI)

- **Which Season Finances opens on.** Question: the summary needs a Season and the app has
  no "current Season" rule (chunk 25). Choice: the screen opens on the earliest-starting
  Season that hasn't ended (South African date), else the latest Season; the Admin can pick
  any other. Why: it matches the Fixtures list, which shows Seasons that haven't ended, and
  it only picks a filter, never a figure. If the answer differs: change `openingSeason` in
  `frontend/src/pages/finance/shared.tsx`.
- **The four FinanceSummary totals.** Question: the design shows "Due to date", "Received",
  "Outstanding" and "Season expected"; the chunk 25 API has one expected figure (league fees
  charged) and no due-to-date. Choice: Expected (league fees charged), Received (league card
  and cash), Outstanding (owed, in pending ink) and Team credit held. Friendly and booking
  money are their own income lines, with "All income received" (the API's `received`)
  below them. Why: no figure is computed in the app, and FR-49 keeps booking and friendly
  income apart from league income. If the answer differs: due-to-date and season-expected
  need new API figures (chunk 27's planner works week by week), then the card changes.
- **How a Team ledger is opened.** Choice: Finances lists the Season's active Teams in
  scope (from the existing team-payments list) and each opens its Team ledger. Withdrawn
  Teams are not listed, though the ledger endpoint serves them. Why: no API change in a UI
  chunk. If withdrawn Teams' ledgers must be reachable: add the Teams in scope to the
  summary, or a status filter to team-payments.
- **Ledger entry wording.** Choice: Fee charged, Payment, Credit given, Refund, and
  "Correction of entry N" for a reversal (with its reason); each line shows its entry
  number, the date and time in South African time, the Player if any, the amount, a Card /
  Cash / Credit chip, and "Recorded by" the Admin or "the app". Amounts are shown as the
  ledger stores them (above zero); the kind says which way the money went. If the answer
  differs: change `entryTitle` in `frontend/src/pages/finance/shared.tsx`.
- **Comparison.** Choice: a "Compare Seasons" screen, every Season by default, narrowed by
  multi-select Season chips; each Season shows received, the League, Friendlies and
  Bookings lines, and each Night's league and friendly income. If the answer differs (a
  table across Seasons, Leagues as something else): only `ComparisonPage.tsx` changes.

## Chunk 27: Outstanding list and income planner

- **How a Season fee becomes "expected week by week".** Question: the league fee is one
  charge per Team per Season (chunk 8), but FR-47 wants expected income per week from the
  fixture list. Choice: each Team's league fees charged are spread evenly over its
  Fixtures in the Season (to the cent, the odd cents on the last), in the week each kicks
  off. Cancelled Fixtures are left out; a Team with no Fixtures yet is "unscheduled" (in
  the Season's expected, in no week). Weeks are the Season's own: week 1 starts on its
  first day. Why: it uses only the fee as charged and the fixture list, and the Season's
  expected stays equal to the Finances summary's. If the answer differs (fees per match,
  calendar weeks Monday to Sunday): only `backend/finance/planner.py` changes.
- **What "received overlaid" means per week.** Choice: each Team's payments (card, cash
  and credit, never more than charged) cover its own Fixtures in date order; a week that
  has started and isn't covered is short. "Paid to date", "Behind" and the bars use this.
  Card and cash actually taken each week are also given per week ("received that week").
  Why: paying the Season upfront would otherwise show as one huge week, and one Team
  paying ahead must not hide another's shortfall. If the answer differs (raw takings per
  week as the bars): the API already gives `received` per week; the bars change.
- **Who counts as a Player who owes.** Question: the ledger charges Teams, not Players.
  Choice: a current Player of an active Team that owes owes their share (what is due over
  the Team's current Players, rounded up to the cent, as "Pay my share") less what they
  have paid towards it, never more than the Team still owes. Money paid for the whole
  Team isn't split across Players, so the Players' sum can exceed the Team's figure.
  Friendly fees and Booking Users are not on the list (no per-Player charges exist).
  Withdrawn Teams are left out (cash can't be recorded for them). If the answer differs:
  `backend/finance/outstanding.py`.
- **Who Remind reaches and what it says.** Choice: an Update notification (message only).
  A Team's Remind goes to its Captain and its current Players who still owe their share;
  a Player's Remind to that Player. Only those opted into the Team's Night receive it
  (targeting rule); the Admin is told who wasn't reached, and a Player not opted in has
  Remind turned off. The message names the Team, the amount and how to pay (in the app
  only if the club takes cards). No limit on how often an Admin may remind. If the answer
  differs (a limit, the Captain only, a new notification kind): `remind` in
  `backend/finance/outstanding.py` and `payment_reminder_recipients` in targeting.py.
- **What Mark cash paid records.** Choice: exactly what the row owes, as one cash ledger
  entry through `record_cash` (FR-22): for the Team (no Player) on a Team row, for that
  Player on a Player row, with the reason "Cash paid, marked on the Outstanding list".
  The app sends the amount it showed; if what is owed has changed, nothing is recorded
  (409) and the list reloads. A part payment uses the existing Record cash screen. The
  screen asks once more before recording. If the answer differs (an editable amount):
  the endpoint already takes `amount`; drop the equality check and add a field.
