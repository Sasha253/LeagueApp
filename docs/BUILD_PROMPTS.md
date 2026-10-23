# Build prompts

One prompt per Claude Code session, run in order. Each chunk builds on the ones before it.
Start a fresh session for each chunk, paste the prompt, and review the plan before letting it
code. Chunks marked **(UI)** follow a backend chunk and only build screens.

## Rules for every chunk

Every prompt below ends with "Follow the chunk rules in docs/BUILD_PROMPTS.md". They are:

1. Read CLAUDE.md, the PRD sections named in the prompt, and docs/DECISIONS.md.
2. Show a short plan first: models, endpoints, screens, tests. Wait for my OK.
3. Build only this chunk. Anything found that belongs to a later chunk goes in the plan's
   "later" list, not in the code.
4. If the PRD does not answer something, ask me. Record the answer in docs/DECISIONS.md.
5. Write tests with the code: pytest for every rule and permission, Vitest for every screen.
6. After any API change, run `npm run gen:api`.
7. Before saying done, run `make test`, `make lint`, `npm test` and `npm run build` and show
   the results.
8. End with: what was built, what was not, and anything I need to do by hand.

---

## 1. Capacitor shell for App Store and Google Play

```
Wrap the frontend with Capacitor so the app installs from the App Store and Google Play
(see the 2026-10-23 platform decision in docs/DECISIONS.md).
- Add Capacitor (current major) to frontend/, with app id za.co.leagueapp (one app for
  every club, so no club's name) and the iOS and Android projects in frontend/ios and
  frontend/android.
- Add npm scripts: cap:sync (build then sync), cap:ios, cap:android. Add them to CLAUDE.md
  Commands.
- Make the API base URL come from a Vite env variable so a device can reach the backend;
  update Django CORS and allowed hosts for capacitor://localhost and https://localhost.
- Respect safe areas (notch, home bar) using design-system tokens only.
- Create frontend/src/native/ with a platform helper (isNative) and a browser fallback, as
  CLAUDE.md requires.
- Check what the iOS build needs on this Mac (CocoaPods is not installed) and tell me the
  exact commands to run; do not install global tools yourself.
Done when npm run build and cap sync succeed and the home page renders in the Android
emulator or iOS simulator.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 2. Accounts, roles and token auth

```
Build user accounts and roles. PRD: "User roles and permissions".
- Custom user model: email login, name, phone. Roles: Admin, Referee, Captain, Player,
  Booking User (a user can hold several; Captain is always also a Player).
- The app serves many clubs, so Admin and Referee are held per Club, never app-wide (see
  the 2026-10-23 multi-club decision). Settle its open questions before coding.
- Player profile: position (outfield, goalkeeper or both) and the Nights they opt into for
  notifications (Night model may be a stub here; chunk 3 fills it in).
- Token auth that works inside Capacitor (no session cookies): register, login, logout,
  refresh, "me" endpoint. Store the token with Capacitor Preferences behind
  frontend/src/native/, with a localStorage fallback in the browser.
- DRF permission classes per role, reused by every later chunk.
- Screens: sign up, log in, profile (position, Night opt-ins) from the designs.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 3. Club setup and configurable values

```
Build club configuration. PRD: FR-42 and NFR Configurability.
- Models: Club, Season, Night, Division (minimum players, default 5), Field/Pitch (with its
  Referee), and a club settings record for every configurable value: league fee per Team,
  friendly fee default, booking hourly fee, cutoffs (T-36h, T-6h), resend delay, booking
  payment cutoff, booking cancellation thresholds and credit percentages, payment mode
  (gateway or cash-only).
- Every Season, Night, Division, Field and settings record belongs to one Club. A new Club
  starts from the PRD defaults, seeded as data (a data migration or a defaults record),
  never as constants in code.
- Admin API and screens to view and edit them. Only that Club's Admins; a test proves an
  Admin of one Club cannot read or change another Club's data.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 4. Import Nights and Divisions from Excel

```
Build the Admin import of Nights and Divisions. PRD: FR-39.
- Upload .xlsx or .csv, validate every row, show a preview with row-level errors, then
  commit in one transaction. Re-importing the same file must not create duplicates.
- Propose the column layout and add a downloadable template.
- Admin screen: upload, preview, confirm.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 5. Teams (backend)

```
Build Teams, backend only. PRD: Captain and Admin rows of the roles table.
- Captain requests a new Team for a Night and Division; Admin confirms or declines.
- Admin can assign or change a Team's Captain.
- Player searches Teams and asks to join; the Captain confirms or declines.
- Team membership history (a Player can be in several Teams).
- Endpoints and permissions for all of the above, with tests.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 6. Teams (UI)

```
Build the Team screens on the chunk 5 API, from the designs in design/.
- Captain: request a Team, see pending requests, confirm Players.
- Admin: Team requests queue, assign Captain.
- Player: search Teams, ask to join, see my Teams.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 7. Fixtures and Admin fixture import

```
Build Fixtures. PRD: "Match lifecycle" intro and FR-53.
- Fixture model: Night, Division, pitch, kick-off (UTC), home and away Team,
  friendly-eligible flag, and a status state machine (scheduled, confirming, ready, one team
  out, replacement offered, friendly, cancelled, played). Only allowed transitions; every
  transition logged with who or what caused it.
- Admin Excel import of a Season's Fixtures, same flow as chunk 4.
- Admin can mark a Fixture friendly-eligible.
- Screens: fixture list per Night, fixture detail, my fixtures for Players and Captains.
Times shown in Africa/Johannesburg, 24-hour, dates as "Tue 27 Oct".
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 8. Ledger and credit

```
Build the money core, no payment gateway yet. PRD: FR-43, FR-46, FR-50, FR-52.
- Append-only LedgerEntry: Decimal rand amount, type (charge, payment, credit, refund,
  reversal), method (card, cash, credit), subject (Team, Player, Booking User), related
  Fixture or Booking, reason, recorded by, created at. No update or delete through the
  ORM, the API or Django admin; corrections are reversal entries.
- Amount due per Team per Season from the club's league fee.
- Credit wallets: Player credit (usable for any Team the Player plays for) and Team credit
  (only that Team's Captain can spend or manage it). Credit returns to whoever paid.
- Service functions other chunks call: charge, record payment, issue credit, spend credit,
  reverse. Balances are computed from entries.
- Read-only API: my credit (Player), Team credit (Captain of that Team), Team balance.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 9. Notifications (backend and push sending)

```
Build the notification engine, backend side. PRD: "Notifications" and "Targeting rules".
- Notification model with the seven types, content, action buttons, recipient, read and
  answered state.
- One targeting service that every later chunk uses to pick recipients. Cover every rule
  in the PRD with tests: Night opt-ins, Player vs Goalkeeper Requests, reschedule to that
  Night's Admin and that pitch's Referee only.
- Device token registration endpoint. Sending through Firebase Cloud Messaging with
  firebase-admin (credentials from env), behind an interface with a fake sender for tests.
- Delivery failure fallback (NFR Timeliness): propose one (for example retry, then SMS or
  email) and ask me before building it.
- Inbox API: list, mark read, answer an action.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 10. Push and inbox in the app (UI)

```
Build the app side of notifications on the chunk 9 API.
- Ask for push permission and register the device token with
  @capacitor/push-notifications behind frontend/src/native/ (no-op in the browser).
- Tapping a notification or its action button opens the right screen.
- Inbox screen from the designs, with unread state.
- Tell me exactly what I must set up by hand: Firebase project, google-services.json,
  GoogleService-Info.plist, APNs key.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 11. Celery Beat and the timed checkpoints

```
Add Celery with Celery Beat and Redis, and the timed checkpoints. PRD: FR-1, FR-2, FR-4,
NFR Timeliness.
- Redis in docker-compose.yml; make worker and make beat targets; add them to CLAUDE.md.
- A periodic task that finds Fixtures reaching T-36h and T-6h (from club settings) and runs
  each checkpoint exactly once per Fixture, even if the task runs twice or late.
- T-36h: Confirmation to every Player of both Teams. Resend once to non-responders
  (delay from settings). T-6h: Reminder to Players, Captains, Admins, Referees.
- Tests use a frozen clock.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 12. Answering Confirmations

```
Build Confirmation answers. PRD: FR-3, FR-38.
- Player accepts or declines from the notification or the fixture screen and can change
  the answer until the T-6h cutoff; the backend enforces the cutoff.
- Team members see who has confirmed, declined or not answered, and whether the Team is
  below the Division minimum.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 13. T-6h readiness

```
Build the T-6h readiness check. PRD: FR-5, FR-6, and the lifecycle diagram.
- At T-6h a Team below its Division minimum is out.
- Unpaid Teams (from the chunk 8 ledger) go to an Admin decision queue: play (for example
  cash at the gate) or out. Nothing is decided automatically.
- Outcome moves the Fixture to ready, one team out, or both teams out. Chunks 14 and 15
  handle what happens next; here, only set the status and hand off.
- Admin screen: the T-6h queue for tonight.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 14. One Team out: replacement opponent

```
Build the replacement flow. PRD: FR-13 to FR-16.
- General Notification to the out Team's Players (with "find a match"), Update to the
  remaining Team, Update to Admins and Referees.
- Offer the slot to eligible Teams (ask me what "eligible" means if the PRD does not say);
  the first Team to accept wins, safe against two Teams accepting at once.
- New opponent's Players get Confirmations.
- If no Team accepts in time, hand off to chunk 15.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 15. Friendly fallback or cancellation

```
Build the friendly fallback. PRD: FR-10 to FR-12, FR-17, FR-43.
- Both Teams out, or no replacement found: if the Fixture is friendly-eligible, open it as
  a friendly with the right notifications; otherwise cancel it.
- On cancel, every payment becomes credit to whoever paid (Player or Team, FR-52) through
  the chunk 8 ledger services.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 16. Reschedules and Captain requests

```
Build reschedules and Captain requests. PRD: FR-7 to FR-9, FR-18.
- Admin reschedules a Fixture: Update to both Teams' Players, and only that Night's Admin
  and that pitch's Referee (FR-8). If the new time is within 36 hours, send Confirmations
  now. The lifecycle restarts.
- Captain requests cancellation or postponement; nothing changes until an Admin accepts.
- Screens for both sides.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 17. Player and Goalkeeper Requests

```
Build borrowing Players. PRD: FR-35 to FR-37 and the visibility rule.
- Captain raises a Player or Goalkeeper Request for a Fixture.
- Sent only to the right position, not in either Team, filtered by Night opt-ins.
- First to accept joins; the request closes when filled, safe against races.
- Check docs/DECISIONS.md open questions 1 and 2 (borrowed Player fees, Captain told when
  filled) and ask me before building them.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 18. PayFast payments (backend)

```
Build card payments with PayFast, backend only. PRD: FR-19 to FR-22, NFR Security.
- A PaymentGateway interface (Peach and Yoco come later) with a PayFast implementation:
  create a payment for a Player's chosen contribution, ITN webhook with signature check,
  source check and server-side validation, idempotent on repeat ITNs. Sandbox from env.
- Each confirmed payment is a ledger entry. Team marked paid when its total reaches the
  amount due. Spending Player or Team credit first is an option.
- Admin records cash payments (FR-22).
- Card data never touches our servers.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 19. Payments (UI)

```
Build the payment screens on the chunk 18 API.
- Player: choose amount, apply credit, pay. Open PayFast with @capacitor/browser behind
  frontend/src/native/ and return to the app afterwards.
- Captain: who has paid, Team total vs due, Team credit.
- Admin: which Teams have paid, record cash.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 20. Payment Barcodes

```
Build Payment Barcodes. PRD: "Barcode authorisation" table, NFR Barcode integrity.
- Issued automatically when a Team is paid (valid per match, gateway mode) or by an Admin
  for cash (valid rest of the Season, cash mode). Tied to one Team or Booking.
- Signed, unguessable, single subject; revocable; every scan logged.
- Captain sees the Barcode in the app.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 21. Gate scanning

```
Build the gate scanner. PRD: FR-23.
- Referee and Admin scan with the device camera through a native Capacitor barcode plugin
  behind frontend/src/native/ (manual code entry as the browser fallback).
- Backend verifies: valid, paid, right Fixture or Booking, not reused where single-use.
- Large clear result screen: paid or not paid, Team name, reason.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 22. Friendly fees

```
Build friendly fees. PRD: FR-24, FR-49.
- Admin sets the fee and who pays per friendly: borrowed Players, the Team's Players, or
  the club/manager.
- Admin assigns the Captain who receives the Barcode.
- Friendly income recorded as its own ledger category.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 23. Bookings

```
Build field bookings. PRD: FR-28 to FR-31.
- Booking User picks field, start time and hours from availability (no clash with
  Fixtures or other Bookings).
- Admin gets a Booking Notification and accepts or declines; on accept the Booking User
  gets a Barcode (chunk 20) that chunk 21 can scan.
- Booking User can cancel or reschedule (policy outcomes come in chunk 24).
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 24. Booking payments and cancellation policy

```
Build booking payments and the policy. PRD: FR-32 to FR-34, FR-44 to FR-46, policy table.
- Price = hourly fee × hours, charged through PayFast at the club's payment cutoff
  (Celery Beat task). Ask me how PayFast should hold card details for a later charge
  (tokenisation) before building it.
- Policy engine from club settings: cancel and reschedule outcomes per time window, club
  cancellations, credit returned to the Booking User, credit used before card.
- Show the policy and the user's current outcome before they confirm.
- Without the gateway, the Admin applies the same outcomes when confirming payment.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 25. Finance tracker (backend)

```
Build the finance tracker API. PRD: FR-25, FR-26, FR-27, FR-49.
- Season totals per Night and Division: expected (Teams × fee), received, outstanding,
  credit held, split by card and cash.
- Team ledger lines: date, Player, amount, method, recorded by.
- Comparison across Leagues and Nights. Booking and friendly income as separate lines.
- All figures computed from the ledger, Admins only.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 26. Finance tracker (UI)

```
Build the Finances screens on the chunk 25 API, from the designs in design/.
Totals, Team ledger, comparison, and income lines. Money shown as "R 18,550".
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 27. Outstanding list and income planner

```
Build FR-47 and FR-48.
- Outstanding list: Teams and Players who owe, largest first, with Remind (sends a
  notification) and Mark cash paid (ledger entry) on each row.
- Planner: expected income week by week from the fixture list, received income overlaid.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 28. Accountant export

```
Build FR-51: export any date range of ledger entries to CSV and Excel for the club's
accountant. Propose the columns and ask me before building.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## 29. Store release

```
Prepare the App Store and Google Play release.
- App icons and splash screens from the design system, app name, version and build numbers.
- Android signing (keystore from env, never committed) and an iOS signing checklist.
- Permission texts (camera, notifications) and a privacy policy page.
- A checklist against App Review Guideline 4.2 and Google Play policy, and the store listing
  fields I must fill in.
- Steps to ship a TestFlight build and a Play internal testing build.
Follow the chunk rules in docs/BUILD_PROMPTS.md.
```

## Not yet planned

- **FR-40** website and fixtures system integration, and league tables. These depend on
  each club's platform; plan them once the first club's system is known.
- **Phase 2:** Xero, Peach Payments, Yoco.
