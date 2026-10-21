# League Management Mobile App — PRD

Transcribed from `docs/League_Management_App_PRD.pdf` (Oct 20, 2026, @Sasha). The PDF is the
source: if the two ever differ, the PDF wins. Decisions made since are in `docs/DECISIONS.md`.

## Overview

A mobile app that automates running a social football league: team sign-up, fixture
confirmation, cancellations and rescheduling, payments, field bookings and player sourcing,
with every team payment tracked in a built-in finance view.

**Problem.** League managers (Admins at Old Parks) spend hours chasing teams to confirm
fixtures and pay, and lose revenue when matches fall through at short notice. Captains
struggle to know who will turn up. Payment is tracked by hand, often with physical tokens at
the gate.

**Solution.** Role-based push notifications drive every step of the match lifecycle. Matches
that cannot go ahead are cancelled, replaced or converted to friendlies automatically, hours or
days in advance. Payment is taken in-app (or confirmed by Admin for cash) and proven at the
gate with a scannable Payment Barcode.

**Target customer.** Venue operators and league managers running weekly 5-a-side style
leagues across multiple nights and divisions, who may already have a website, fixtures system
or accounting package.

## Goals and success metrics

The app succeeds when scheduled fixtures reliably happen, teams pay without being chased, and
Admin workload drops.

| Goal | Metric | Target |
| --- | --- | --- |
| Fixtures happen as scheduled | % of scheduled slots that end in a played match (league, replacement or friendly) | TBD |
| Teams pay on time | % of teams with a valid Payment Barcode before kick-off | TBD |
| Less admin effort | Admin hours per night spent on confirmations, payments and rescheduling | TBD |
| Recover lost revenue | Friendly-match and booking income per month | TBD |
| Players respond | % of Confirmation Notifications answered before the 6-hour cutoff | TBD |

### Non-goals (v1)

- Replacing an existing league website or results platform; we integrate with it instead.
- Full accounting in phase 1 (expenses, invoices, VAT, bank reconciliation); the finance
  tracker covers income only and exports it for the club's accountant.
- Removing cash payments; cash stays supported through Admin confirmation.

### Phasing

Phase 1 ships the match lifecycle with a basic in-app finance tracker; Xero moves to phase 2,
so a club can launch with no accounting setup or extra subscription.

| Area | Phase 1 | Phase 2 |
| --- | --- | --- |
| Team payments | Tracked in the in-app finance tracker | Also synced to Xero |
| Booking and friendly income | Shown in the finance tracker | Also synced to Xero |
| Accountant hand-off | CSV / Excel export | Xero, or other packages through Xero |

## User roles and permissions

Five roles; a Captain is also a Player, and a Player can be an outfield Player, a Goalkeeper,
or both.

| Role | Who | Can do |
| --- | --- | --- |
| Admin | League managers at Old Parks | Load available Nights and Divisions (e.g. from Excel); confirm or decline Captain requests to create a Team; assign a Captain to a Team; accept Captain cancellation requests; cancel or reschedule fixtures; confirm or decline Booking Notifications; scan Barcodes to confirm Team and Booking User payment; confirm cash payments (no-gateway mode) |
| Referee | Match officials per pitch | Scan a Barcode to confirm a Team has paid |
| Captain | Team lead (also a Player) | Request creation of a Team by choosing an available Night and Division; confirm Player requests to join; send a cancel/postpone request to Admin; receive the Payment Barcode; raise a Player or Goalkeeper Request when short |
| Player | Registered player | Search for and request to join a Team; choose which Nights to get notifications for; accept or decline Confirmation Notifications; receive Reminder and Player Request Notifications; join another Team's match via a Player/Goalkeeper Request |
| Booking User | Casual field hirer | Pick an available time, field and number of hours; cancel or reschedule the booking; receive a Barcode for entry once approved |

**Visibility rule:** Player Requests are shown only to outfield Players and Goalkeeper
Requests only to Goalkeepers, matching each user's chosen position.

## Notifications

Push notifications are the app's core mechanism: each one informs a user and, where it carries
a button, triggers the next step in the background.

| Type | Content | Action | Recipients |
| --- | --- | --- | --- |
| Confirmation | Both team names, date and time | Confirm / Decline | Players of a scheduled or newly joinable match |
| Reminder | Date, time and field | None | Players, Captains, Admins, Referees |
| General | Message (e.g. match cancelled) | Button to find a match in another Team | Players of a cancelled Team |
| Update | Message only | None | Players, Admins, Referees affected by a change |
| Player Request | Confirmation format | Accept / Decline to join another Team's match | Outfield Players not in either opposing Team |
| Goalkeeper Request | Confirmation format | Accept / Decline to join another Team's match | Goalkeepers not in either opposing Team |
| Booking | Booking details | Confirm / Decline | Admins |

### Targeting rules

- Players only receive notifications for the Nights they opted into.
- On a reschedule, only the Admin of the registered Night and the Referee of the affected
  pitch are notified.
- A Player who answered a Confirmation incorrectly can change their answer in the app.

## Match lifecycle

Every fixture runs on two timed checkpoints (T-36h and T-6h before kick-off); a team that drops
out triggers a replacement match, and failing that a friendly where the Admin allows it.

A fixture that cannot go ahead is first re-offered to another Team, then opened as a friendly
only if the Admin has listed it as friendly-eligible; otherwise it is cancelled and paid
Players receive credit.

### Confirmation and readiness

1. **FR-1** Send a Confirmation Notification to every Player of both Teams 36 hours before kick-off.
2. **FR-2** Resend the Confirmation once if the Player has not accepted or declined.
3. **FR-3** Let a Player change their accept/decline answer in the app at any time before the cutoff.
4. **FR-4** Send a Reminder Notification (date, time, field) 6 hours before kick-off.
5. **FR-5** At T-6h, cancel a Team's participation if fewer Players have confirmed than the
   Division's minimum (configurable per Division; default 5).
6. **FR-6** A Team may only play with a valid Payment Barcode. At T-6h the Admin (manager)
   decides whether an unpaid Team is out, including Teams still expected to pay cash at the gate.

### Admin reschedule (the process restarts)

1. **FR-7** Send an Update Notification to Players of both rescheduled Teams.
2. **FR-8** Send an Update Notification to the Admin of the registered Night and the Referee of
   the affected pitch only.
3. **FR-9** If the new time is within 36 hours, send Confirmation Notifications immediately.

### Both Teams cancel → friendly, only if the Admin has listed the match as friendly-eligible

1. **FR-10** General Notification to Players of the cancelled Teams (match cancelled, with a
   button to find a match elsewhere).
2. **FR-11** Confirmation Notification to all Players outside the two Teams (match free to join).
3. **FR-12** Notification to Admins and Referees.

### One Team cancels → find another opponent

1. **FR-13** General Notification to Players of the cancelled Team.
2. **FR-14** Update Notification to the remaining Team (opponent withdrew, finding a new match).
3. **FR-15** Offer the slot to eligible Teams; the first Team to accept becomes the new
   opponent and its Players get Confirmation Notifications.
4. **FR-16** Update Notification to Admins and Referees.
5. **FR-17** If no replacement is found and the Admin has listed the match as friendly-eligible,
   fall back to a friendly (otherwise cancel it and apply FR-43): General Notification to the
   cancelled Team, Confirmation to all Players outside it, Update to Admins and Referees.

### Captain-initiated cancellation

1. **FR-18** A Captain can request a cancellation or postponement; it takes effect only once an
   Admin accepts it.

## Payments, authorisation and accounting

A Team is authorised to play only when its Captain holds a valid Payment Barcode, issued
automatically on payment or by an Admin for cash.

### Payment gateway

1. **FR-19** Players enter card details and choose how much they pay; contributions sum to the
   Team total.
2. **FR-20** Once the Team total reaches the amount due, the Team is marked paid.
3. **FR-21** Captains see which Players have paid; Admins see which Teams have paid.
4. **FR-22** Cash paid to the club remains an option alongside card payment.

### Barcode authorisation

| Mode | How the Barcode is issued | Validity |
| --- | --- | --- |
| With payment gateway | Generated automatically when the Team has paid | Per match |
| Without payment gateway | Admin confirms payment in the app; Barcode sent to the Captain | Rest of the Season |

5. **FR-23** Referees and Admins scan the Barcode at the entrance; the app shows whether the
   Team has paid.
6. **FR-24** Friendly matches charge a specified fee, paid by the borrowed Players, the Team's
   Players or the club/manager, as the Admin sets per match; a Captain is assigned to receive
   the Barcode and have it verified.

### Cancellations and credit

**FR-43** When a paid match is cancelled, each Player's payment becomes credit towards a future
match; no card refund is issued.

### Finance tracker (phase 1)

Admins get a Finances view that shows what each Team owes, what has come in, and what is still
outstanding, without any outside accounting software.

7. **FR-25** Season totals per Night and Division: expected (Teams × fee), received, outstanding
   and credit held, split by card and cash.
8. **FR-26** Team ledger: amount due, paid and outstanding, with every payment line (date,
   Player, amount, method: card, cash or credit) and who recorded it.
9. **FR-27** Compare income across Leagues and Nights.
10. **FR-47** Planner: expected income week by week for the season, built from the fixture list,
    with received income overlaid so shortfalls show early.
11. **FR-48** Outstanding list: Teams and Players who owe, largest first, with Remind and Mark
    cash paid on each.
12. **FR-49** Booking and friendly income shown as separate lines beside league income.
13. **FR-50** Credits, refunds and corrections are added as ledger entries with a reason; entries
    are never edited or deleted, only reversed.
14. **FR-51** Export any period to CSV or Excel for the club's accountant.

Xero integration (season and booking income synced automatically, 50% off the first three
months) moves to phase 2.

## Bookings

Casual users can hire a field for a chosen number of hours; an Admin approves each booking and
the user enters with a Barcode.

1. **FR-28** Booking Users choose from available fields and times and the number of hours to play.
2. **FR-29** Admins receive a Booking Notification and accept or decline.
3. **FR-30** On acceptance, send a Barcode to the Booking User for scanning at entry.
4. **FR-31** Booking Users can cancel or reschedule the time, field and hours booked.

With payment gateway only:

5. **FR-32** Booking Users sign up with payment credentials.
6. **FR-33** Price = hourly fee × hours booked.
7. **FR-34** Payment is taken only at a club-configured time before kick-off, leaving a free
   cancellation window.

### Cancellation and refund policy (proposed defaults, configurable per club)

Booking Users can cancel free until payment is taken; after that, value is returned as credit,
never cash, except when the club cancels.

| When | Booking User cancels | Booking User reschedules |
| --- | --- | --- |
| Before the payment cutoff (default 24h before) | Free; nothing charged | Free |
| Cutoff to 6h before | 50% credit | Free, once, to a slot within 30 days |
| Under 6h before, or no-show | No credit | Not allowed |
| Club cancels (pitch, weather, operational) | 100% credit, or card refund on request | Free |

- **FR-44** Apply the policy automatically with the payment gateway; without it, the Admin
  applies the same rules when confirming payment.
- **FR-45** Show the policy and the user's current cancellation outcome before they confirm a
  booking or a cancellation.
- **FR-46** Credit is held against the user's account and used before card payment on their
  next booking.

## Player sourcing, tables and integrations

Captains short of players can borrow from other Teams, which keeps turn-up rates and the league
schedule stable.

### Players for another Team's match

1. **FR-35** A Captain who expects to be short creates a Player or Goalkeeper Request
   Notification for the match.
2. **FR-36** It goes to all Players (or Goalkeepers) not in either opposing Team, filtered by
   their chosen Nights.
3. **FR-37** The first to accept joins the match; once the slot is filled the request closes.
4. **FR-38** Team members can see who has confirmed for the match, so the Captain knows early if
   the Team is short.

### League tables

The app can show Leagues, Fixtures, Match Results, Match Videos, Team Rankings, Best goals and
Top scorers. Most clubs already publish these, so v1 integrates with the existing platform
rather than replacing it.

### Integrations

- **FR-39** Import Nights and Divisions from the Admin's existing tool (e.g. Excel).
- **FR-40** Integrate with the club's current website or fixtures system via its developer.
- **FR-41** Phase 1: in-app finance tracker with CSV / Excel export. Phase 2: accounting via
  Xero; other platforms and accounting packages connect through Xero.
- **FR-42** Club-configurable parameters at setup (fees, cutoffs, Nights, Divisions, payment
  window).

## Non-functional requirements

- **Lightweight and embeddable:** small footprint; integrates with software the club already uses.
- **Security:** card data handled by a PCI-compliant payment gateway, never stored by the app;
  payment data in secure cloud infrastructure.
- **Timeliness:** scheduled notifications (T-36h, T-6h) must fire on time; delivery failures
  need a fallback.
- **Barcode integrity:** Barcodes must be unique, tied to a Team or Booking, and impossible to
  reuse or forge.
- **Configurability:** fees, cutoffs and payment windows are set per club without code changes.
- **Platforms:** iOS and Android.

## Decisions

| Question | Decision |
| --- | --- |
| Resending unanswered Confirmations | Resend once |
| Minimum players per Team | Configurable per Division (default 5) |
| Who rules a Team unpaid at T-6h | The Admin (manager) |
| Choosing a replacement opponent | First Team to accept |
| When to fall back to a friendly | Only when the Admin lists the match as friendly-eligible |
| Who pays for a friendly | Borrowed Players, the Team's Players or the club/manager, set per match |
| Barcode validity with the gateway | Per match |
| Payments for a cancelled match | Credit towards a future match |
| Booking cancellation and refunds | Proposed policy in Bookings |
| Existing platforms and accounting | Phase 1: in-app finance tracker and export; phase 2: Xero |
