# Chunk 23: Bookings

Unattended run, 2026-10-23. PRD: FR-28 to FR-31 (Bookings), the Booking notification
(Notifications table), the Booking User role, NFR Barcode integrity. Payments and the
cancellation policy (FR-32 to FR-34, FR-44 to FR-46) are chunk 24.

## Plan

Backend:
- Club setting `match_length_minutes` (data, empty until the Admin sets it, like the fees):
  how long a league match holds its pitch from kick-off, so a booking can be checked
  against Fixtures. Bookings need it and the booking hourly fee (`missing` lists both).
- New `bookings` app:
  - `Booking`: club, field, Booking User, start (UTC, on the hour in South African time),
    hours (1 to 24, ending by midnight of its day), end, the hourly fee fixed when it was
    requested and the price (hourly fee x hours, Decimal rand), status (pending, accepted,
    declined, cancelled), who decided and when, decline reason, cancelled at.
  - `BookingEvent`: append-only log of every request, reschedule, accept, decline and
    cancel, with the slot and who did it (chunk 24 counts late reschedules from it).
  - `services.py`: availability (free start times per field for a day and a number of
    hours), request, accept, decline, cancel, reschedule. No clash with a pending or
    accepted Booking or a Fixture that isn't cancelled on the same field; the field row is
    locked so two requests can't take one slot.
- Notifications: `Notification.booking`; a Booking Notification (Confirm / Decline) to every
  Admin of the club on a request or a reschedule; answering it accepts or declines. The
  Booking User gets an Update when it is accepted or declined; the Admins an Update when an
  accepted booking is cancelled. Pushes carry `booking_id`.
- Barcodes: a third exclusive subject, `Barcode.booking` (mode `booking`, no Season),
  signed over the booking. Issued on accept; revoked on cancel or reschedule. Valid while
  the booking is accepted, not over, and paid (the price is still owed until chunk 24
  takes payments, so the gate says "Not paid" unless the price is R 0). At the gate: only
  on the booking's day, once per booking, only for the club's Admins (PRD: Referees
  check Teams).
- API:
  - `GET /api/v1/bookings/clubs/` (Booking User): clubs taking bookings, with the hourly fee.
  - `GET /api/v1/bookings/availability/?club=&date=&hours=[&booking=]`: free start times
    per field and the price.
  - `GET/POST /api/v1/me/bookings/`, `GET /api/v1/me/bookings/{id}/`,
    `POST .../cancel/`, `POST .../reschedule/`, `GET .../barcode/`.
  - `GET /api/v1/clubs/{club_id}/bookings/` (Admin, filter by status),
    `GET .../{id}/`, `POST .../{id}/accept/`, `POST .../{id}/decline/`.
- `npm run gen:api`.

Frontend:
- Book a field (`/book`): club, day, hours stepper, field list with time chips, price from
  the API, Request booking; then "Booking requested".
- My bookings (`/bookings`) and a booking (`/bookings/:id`): status, Barcode (PaymentTicket
  when valid, else why not), Reschedule (same picker), Cancel (asks once more).
- Admin: club Bookings (`/clubs/:clubId/bookings`) with Accept / Decline; links from Profile.
- Notification screen links to the booking; club settings shows the match length.

Tests: pytest for every rule and permission (availability, clashes, hours, club isolation,
Booking User only, accept/decline/cancel/reschedule, notifications and their answers,
Barcode issue/revoke/validity/gate); Vitest for each new screen.

Later (not this chunk):
- Payment, price charged at the cutoff, the policy outcomes, credit, the policy shown before
  confirming (chunk 24); the club cancelling a booking (chunk 24 policy "club cancels").
- Fixture import and fixture reschedules checking against accepted Bookings.
- Booking income lines in Finances (finance tracker chunk).

## Built

Backend:
- `ClubSettings.match_length_minutes` (clubs migration 0006): empty until set, listed in
  `missing`; `takes_bookings` needs it and the booking hourly fee.
- `bookings` app: `Booking` and the append-only `BookingEvent` (migration 0001);
  `services.py` (availability, request, accept, decline, cancel, reschedule, the Booking
  Notification receiver), `money.py` (price, paid, outstanding), read-only Django admin.
- `Notification.booking` (notifications migration 0003); pushes and the inbox carry
  `booking_id`; answering locks the Booking first.
- `Barcode.booking`, mode `booking`, `season` nullable for it, signed over the booking,
  one live per booking, one paid scan per Barcode without a match (barcodes migrations
  0004, 0005). `barcodes.services`: `issue_for_booking`, `revoke_for_booking`,
  `current_for_booking`, booking validity and the gate check (its day, once, Admins only).
  Scan answers and Barcodes gained `booking`.
- API: `GET /api/v1/bookings/clubs/`, `GET /api/v1/bookings/availability/`,
  `GET/POST /api/v1/me/bookings/`, `GET /api/v1/me/bookings/{id}/`,
  `POST .../cancel/`, `POST .../reschedule/`, `GET .../barcode/`,
  `GET /api/v1/clubs/{club_id}/bookings/[{id}/]`, `POST .../accept/`, `POST .../decline/`.
  `npm run gen:api` run.

Frontend:
- `pages/bookings/`: Book a field (`/book`: club, day picker, hours stepper, fields, start
  times, price from the API, Booking requested), My bookings (`/bookings`), a booking
  (`/bookings/:bookingId`: status, entry Barcode, Reschedule, Cancel with a second ask),
  the club's Bookings for Admins (`/clubs/:clubId/bookings`: Waiting / All, Accept,
  Decline with a reason). Profile links for Booking Users and Admins.
- Notification screen "Open the booking"; Scan result shows a booking's field and time;
  club settings has the match length; the stepper, day picker and slots in proposed.css.

Tests: `backend/bookings/tests/test_bookings.py` (37: availability, slot rules, clashes with
bookings and matches, the club setting, Booking User only, club isolation, accept /
decline from the screen and the inbox, a former Admin can't decide, cancel, reschedule,
push data, the log) and `test_barcodes.py` (9: Barcode on accept, unpaid until paid, R 0
valid, signature, gate once, Referee refused, wrong day, cancelled, other club). Vitest:
BookPage, MyBookingsPage, BookingPage, ClubBookingsPage, ClubSettingsPage, ScanPage and
NotificationPage cases.

## Not built

- Booking payments, the price charged at the cutoff, the cancellation and reschedule
  policy, credit, and showing the policy before confirming (chunk 24).
- The club cancelling a booking (policy "club cancels", chunk 24).
- Fixture import and fixture reschedules checking against accepted Bookings.
- Booking income lines in Finances (finance tracker chunk).
- Club opening hours (none configured; any hour is offered, every booking is approved).

## By hand

- Each club's Admin sets the match length and the booking hourly fee in Club setup >
  Settings before bookings open.
- Review docs/OPEN_QUESTIONS.md "Chunk 23: Bookings", especially the match length, whether
  a reschedule needs the Admin again, and that only Admins check bookings at the gate.

## Results

- make test: 877 passed
- make lint: ruff check and format clean
- npm test: 298 passed
- npm run build: built

## Review (2026-10-23, unattended)

Plan: read the commit against the chunk prompt and CLAUDE.md rules (Decimal money, club
isolation, settings as data, append-only logs, notification targeting, design-system UI,
tests, gen:api, scope), run the four checks, fix real defects only.

Checked and fine:
- Money is Decimal throughout (`bookings/money.py`); the price is decided in the backend
  and only shown by the app.
- Club isolation: club screens use `ClubAdminMixin`; `accept`/`decline` also check the
  Admin role (a former Admin answering an old Notification is refused); a Booking User
  only sees their own Bookings (others 404); a field must belong to the Booking's club;
  the gate only finds the scanning club's Barcodes.
- The hourly fee and match length are club settings (data); `BookingEvent` refuses
  update and delete; Booking Notifications go only to the club's Admins, Updates only to
  the Booking User (accept/decline) or the Admins (an accepted booking cancelled).
- UI uses `la-` components and tokens; the day picker, slots and stepper are listed in
  docs/DECISIONS.md as proposed components. `npm run gen:api` leaves no diff.
- Nothing from chunk 24 (payments, policy, credit) was built.

Fixed:
- Rescheduling showed the wrong price. The availability endpoint priced a reschedule at
  the club's current hourly fee, but `reschedule` keeps the fee the Booking was requested
  at. If the Admin changed the fee in between, the picker showed a price the Booking
  would not cost. `availability(..., exclude=booking)` now uses the Booking's own fee.
  Test: `test_availability_for_a_reschedule_prices_at_the_booking_fee`.

Not changed (noted):
- The app's hours stepper stops at 24 and the day picker shows 14 days. Both only limit
  what the screen offers; the backend enforces the real rules (1 to 24 hours, ending by
  midnight).
- If two gates scan one booking Barcode at the same moment, the loser's "used" reason
  says "once per match". The wording is a little off, but the result is right.

Review results:
- make test: 878 passed
- make lint: ruff check and format clean
- npm test: 298 passed
- npm run build: built
