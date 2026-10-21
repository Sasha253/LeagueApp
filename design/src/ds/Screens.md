# Screens

Every screen the app needs, by role, built from the PRD. One account can hold several roles (a Captain is also a Player); the tab bar shows the tabs for the roles the account holds. Sample data for mockups: Tuesday Night league, Division 2, Pitch 3, Red Lions vs Old Boys, kick-off 19:40, R 70 per player, R 350 per team, minimum 5 players.

## Tabs by role

| Role | Tabs (left to right) |
| --- | --- |
| Player | Matches · Teams · Inbox · Profile |
| Captain | Matches · My team · Inbox · Profile |
| Admin | Tonight · Fixtures · Requests · Scan · More |
| Referee | Tonight · Scan · Inbox · Profile |
| Booking User | Book · My bookings · Inbox · Profile |

## Shared

1. **Sign in / sign up**: phone or email, then pick roles (Player, Goalkeeper or both). One field per step.
2. **Choose Nights**: multi-select chips (Mon to Sun) for which Nights to get notifications for.
3. **Inbox**: every notification as a list; unanswered Confirmations and requests pinned on top with a pending chip. Filters: All, Needs reply, Updates.
4. **Notification detail**: a `ConfirmationCard` full screen for actionable types; a plain message for Updates.
5. **Profile and settings**: positions, Nights, theme (Night, Day, System), payment methods, credit balance.

## Player

1. **Matches (home)**: next match as a hero `MatchCard` with the reply buttons, then upcoming fixtures, then "Games you can join" (Player and Goalkeeper Requests, friendlies).
2. **Match detail**: kick-off in `scoreboard`, pitch, opponent, `SquadProgress`, squad list with each player's status, your reply (changeable until T-6h), Pay my share.
3. **Pay my share**: amount stepper (defaults to the per-player share), card or saved card, credit applied first, Pay R 70. Note that cash to the club is also accepted.
4. **Find a team**: search by team, Night, Division; Request to join.
5. **Join request sent**: waiting state until the Captain confirms.

## Captain

1. **My team**: squad list with confirmed / waiting / declined per match, `PaymentProgress` for the season or match, Remind unpaid.
2. **Create team request**: table of available Nights and Divisions as selectable rows; Send to Admin.
3. **Join requests**: list of Players asking to join, Accept / Decline each.
4. **Request a player**: pick Player or Goalkeeper and how many; preview of who will be notified ("Players on Tuesday not in either team").
5. **Cancel or postpone**: reason, choice of cancel or postpone, Send to Admin; shows that the Admin must approve.
6. **Payment Barcode**: `PaymentTicket` full screen at max brightness, valid for this match only.

## Admin (manager)

1. **Tonight**: timeline of tonight's matches by pitch and time, each with both teams' `SquadProgress` and paid state; matches at risk (under minimum or unpaid at T-6h) on top.
2. **Fixtures**: by Night and Division; reschedule (date/time/pitch picker, shows who gets notified and whether Confirmations go out now), cancel, mark friendly-eligible.
3. **Requests**: tabs for Team creation, Captain assignment, Cancellations, Bookings; each a `ConfirmationCard` with Approve / Decline.
4. **Rule a team out at T-6h**: for unpaid teams, Mark paid (cash) or Rule out, with the fallback that follows (replacement search, friendly if eligible, credit).
5. **Finances** (phase 1 finance tracker, opened from More and from a money summary row on Tonight): filter by Season, Night and Division; `FinanceSummary` at the top (due to date, received, outstanding, season expected, plus the week-by-week planner); then an Outstanding list (Teams and Players who owe, largest first, Remind and Mark cash paid); then income lines for League, Friendlies and Bookings; Export to CSV / Excel.
6. **Team ledger**: `PaymentProgress` for the Team, then every entry newest first (date, Player, amount, method chip: Card, Cash or Credit, recorded by). Corrections add a reversing entry with a reason; nothing is edited in place.
7. **Import Nights and Divisions**: upload a spreadsheet, preview rows, confirm.
8. **Settings**: per-Division minimum players, fees, payment cutoff for bookings, cancellation policy thresholds.
9. **Scan**: shared scanner (below).

## Referee

1. **Tonight**: only matches on the Referee's pitch.
2. **Scan**: full-screen camera with a framed scan area and torch toggle; result sheet shows team, match, and a large status: Paid (confirmed) or Not paid (cancelled) with the reason. Manual code entry fallback.

## Booking User

1. **Book a field**: day picker, field list, time slots as chips, hours stepper, live price (hourly fee × hours), policy summary, Request booking.
2. **Booking requested**: pending until an Admin approves.
3. **My bookings**: upcoming with status; open one for the entry Barcode (`PaymentTicket`), Reschedule, Cancel (shows the policy outcome before confirming: free, 50% credit or no credit).

## Key moments to design first

1. Player Confirmation at T-36h (Inbox → `ConfirmationCard` → "You're in!").
2. Captain short of players at T-8h → Request a player → a Player from another team accepts.
3. Referee scanning a ticket at the gate, Paid and Not paid results.
4. Admin's Tonight view with one match at risk, and the Finances view mid-season.
5. Booking a field and seeing the cancellation outcome.
