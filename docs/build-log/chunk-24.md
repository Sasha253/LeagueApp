# Chunk 24: Booking payments and cancellation policy

Unattended run, 2026-10-23. PRD: FR-32 to FR-34, FR-44 to FR-46 and the cancellation and
refund policy table. Builds on chunk 18 (PayFast), chunk 8 (ledger and credit) and
chunk 23 (Bookings).

## Plan

The chunk prompt asks how PayFast should hold card details for a later charge
(tokenisation) before building it. Nobody can answer during this run, so the most
conservative choice is taken: no card details or card tokens are held at all. At the
payment cutoff the app spends the Booking User's credit and asks them to pay the rest on
PayFast's hosted page (the chunk 18 flow). Tokenised charging can be added later behind the
gateway interface without changing the models used here (docs/OPEN_QUESTIONS.md).

Backend:
- `LedgerEntry.booking` (nullable): booking payments, credit spent on a booking and credit
  returned from one name the Booking. Subject Booking User, category `booking`.
- `ledger.services`: `record_booking_payment` (card or cash), `spend_booking_credit` (the
  app spends it, FR-46), `booking_paid` (payments less refunds, reversals and credit
  returned), `return_booking_payments` (part or all of what was paid, back as credit).
- `Payment.team` nullable and `Payment.booking`, exactly one of them. Payment start for a
  booking (credit first, the rest by card, at least the gateway minimum); the ITN records a
  booking payment; a card payment confirmed after the booking ended or was cancelled comes
  back in full as credit. `PaymentDetailView` and `me/payments/` serve any payer.
- `Booking.payment_requested_at` (cleared on reschedule) and `Booking.payment_taken_at`
  (set once, at the first cutoff); `BookingEvent` gains kinds `payment_due`,
  `club_cancelled`, `no_show` and a `window` (which policy window the change fell in).
- `bookings/policy.py`, the policy engine, from the club's settings only:
  windows `free` (before the cutoff, nothing taken yet), `late` (to the late-cancel hours),
  `very_late` (after that, until it starts), `club`. Cancel outcome: credit of the given
  percent of what was paid; reschedule outcome: free, free while late reschedules are left
  and the new slot is within the window days, or not allowed. Policy rows for showing.
- `bookings/services.py`: cancel and reschedule apply the policy; Admin cancel ("club
  cancels", reason needed, club percent as credit); decline of a paid rescheduled booking
  returns at the club percent; a reschedule to fewer hours returns what is overpaid as
  credit; `take_due_payments` (cutoff: spend credit, then ask for the rest; the Booking
  User gets an Update) and `settle_no_shows` (ended, accepted, never scanned in: the
  no-show percent as credit, once). Celery task `bookings.run_payments` on Beat.
- Admin records cash for a booking (FR-44, without the gateway).
- API: `GET /api/v1/bookings/policy/?club=` (the policy rows before booking),
  `GET /api/v1/me/bookings/{id}/outcome/` (current cancel and reschedule outcome, FR-45),
  `POST /api/v1/me/bookings/{id}/pay/`, `POST /api/v1/clubs/{club_id}/bookings/{id}/cancel/`,
  `POST /api/v1/clubs/{club_id}/bookings/{id}/cash/`. Booking answers gain paid,
  outstanding, payment due time, credit held and can_pay. `npm run gen:api`.

Frontend:
- Book a field: the policy shown before Request booking.
- A booking: what is paid and owed, Pay (credit first, then PayFast), the current
  cancellation outcome in the cancel step and the reschedule outcome before moving.
- Payment result screen handles a booking payment.
- Admin club Bookings: Record cash and Cancel for the club with a reason and its outcome.

Tests: pytest for each policy window and outcome, credit used first, cutoff task, ITN for
a booking, late payments, club cancels, no-show, cash, permissions and club isolation;
Vitest for the changed screens.

Later (not this chunk):
- Tokenised card charging at the cutoff (FR-32), card refunds on request when the club
  cancels, booking income in the finance tracker (chunk 25).

## Built

Backend:
- Migrations: bookings 0002 (`cancelled_by_club`, `payment_requested_at`, `payment_taken_at`,
  `settled_at`; `BookingEvent` kinds `club_cancelled`, `payment_due`, `no_show` and its
  `window`), ledger 0003 (`LedgerEntry.booking`), payments 0002 (`Payment.team` nullable,
  `Payment.booking`, exactly one; credit source `booking_user`).
- `ledger.services`: `booking_credit`, `record_booking_payment`, `spend_booking_credit`,
  `booking_payments`, `booking_paid`, `booking_outstanding`, `return_booking_payments`;
  credits and reversals carry the Booking.
- `bookings/policy.py`: windows, cancel and reschedule outcomes, the policy rows, all from
  the club's settings. `bookings/money.py` reads paid and owed from the ledger.
- `bookings/services.py`: cancel and reschedule apply the policy; `club_cancel`; decline of a
  paid move returns the club percent; fewer hours return the excess; `take_payment` /
  `take_due_payments` at the cutoff (credit first, then the user is asked);
  `record_cash`; `card_payment_recorded`; `settle` / `settle_ended` for no-shows.
  `bookings/tasks.py` `bookings.run_payments` on Celery Beat (`booking-payments`).
- `payments.services.start_booking_payment` (credit first, the rest by card, at least
  R 5 by card), the ITN records booking card payments (Booking locked first),
  `club_card_options`; PayFast's item name for a booking; payment detail and list for any
  payer.
- API: `GET /api/v1/bookings/policy/`, `GET /api/v1/me/bookings/{id}/outcome/`,
  `POST /api/v1/me/bookings/{id}/pay/`, `POST /api/v1/clubs/{club_id}/bookings/{id}/cancel/`,
  `POST /api/v1/clubs/{club_id}/bookings/{id}/cash/`. Bookings gained `paid`,
  `outstanding`, `payment_due_at`, `payment_requested`, `can_pay`, `cancelled_by_club`;
  club bookings `can_club_cancel`, `club_cancel_summary`, `can_record_cash`;
  `can_reschedule` follows the policy. Payments gained `booking`. `npm run gen:api` run.

Frontend:
- `bookings/shared.tsx`: `PolicyList` and `ClubPolicy` (built from `la-group` / `la-item`).
- Book a field shows "If plans change": the policy rows, when payment is taken and the
  user's credit, before Request booking (FR-45).
- A booking: paid and still to pay, when payment is taken, Pay (credit first, then
  PayFast via `native/browser.ts`), the cancel outcome in the confirm step, the reschedule
  outcome, the policy with the current row marked, the club-cancelled banner.
- Payment result screen handles a booking payment.
- Admin club Bookings: paid and owed, Record cash (starts at what is owed), Cancel for the
  club (the credit it returns, a reason required).

Tests: `backend/bookings/tests/test_payments_policy.py` (39: policy rows from settings,
windows and outcomes, the cutoff once only, pending not charged, credit first, credit
covering all, the R 5 card minimum, cash-only clubs, pay before due refused, card plus ITN,
a new payment closing the old, a card payment after a cancel, another user 404, late /
very late / free cancels, unpaid cancel, late reschedules once and within the window,
very late refused, free unlimited, fewer hours, a declined paid move, club cancels, another
club's Admin, Booking User refused admin actions, cash limits, no-shows once, a scan isn't
a no-show, the engine without a late window). Vitest: `BookingPayments.test.tsx` (7), new
BookPage and PaymentResultPage cases, existing booking tests updated.

## Not built

- Tokenised card charging at the cutoff and payment credentials at sign-up (FR-32): needs
  the answer on how PayFast should hold card details (docs/OPEN_QUESTIONS.md).
- Card refunds on request when the club cancels (PayFast refund API).
- Automatic cancellation of bookings still unpaid at their start.
- Booking income in the finance tracker (chunk 25).

## By hand

- Answer the tokenisation question in docs/OPEN_QUESTIONS.md "Chunk 24" and review the
  other provisional choices there (percent of what was paid, no-shows, late reschedules).
- Run Celery Beat (`make beat`) and a worker (`make worker`) so payments are taken at the
  cutoff; PayFast sandbox or live keys and `PAYFAST_NOTIFY_URL` in the environment for card
  payments.
- Each club checks its booking policy values in Club setup > Settings.

## Results

- make test: 916 passed
- make lint: ruff check and format clean
- npm test: 307 passed
- npm run build: built

## Review (2026-10-24)

Independent review of 9525c53 against the chunk prompt and CLAUDE.md. Money is Decimal
throughout; every policy number comes from ClubSettings; ledger changes are new entries
only (credits returned through `return_as_credit`, never edits); club endpoints go through
`ClubAdminMixin` and the services re-check `is_admin` for the Booking's club; Booking User
endpoints are scoped to the user's own Bookings; notifications go only to the Booking User
or that club's Admins. The tokenisation question was answered conservatively (no stored
card details, hosted PayFast page) and logged; accepted as not a blocker.

Fixed (an earlier interrupted review started the first two; finished here):
- `can_pay` said yes whenever payment was due and something was owed, so a cash-only club
  showed a Pay button that always answered 409, and a cash-only club whose user held
  enough credit was not offered paying from credit consistently. New
  `services.can_pay_in_app` applies the same rules as `payments.start_booking_payment`
  (credit covers it, or the club takes cards for at least the gateway minimum). Tests: a
  cash-only club has no Pay button; a cash-only club can be paid from credit.
- The club-cancelled banner said "What you paid came back as credit", which is wrong when
  nothing was paid or the club's percent is under 100. It now says any credit returned is
  used first, and points to the Update that gives the reason.
- A booking whose payment is due but can't be paid in the app (cash-only club, or less
  than the card minimum) showed "Still to pay" with no instruction. It now shows
  "Payment due" with "Pay R … to the club before you play." Vitest case added.

No API shape changed, so `npm run gen:api` was not needed.

Review results:
- make test: 917 passed
- make lint: ruff check and format clean
- npm test: 308 passed
- npm run build: built
