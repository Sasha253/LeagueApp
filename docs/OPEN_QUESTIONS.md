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
