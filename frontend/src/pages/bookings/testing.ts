// Shared by the booking screen tests: a signed-in Booking User, a club, free times, Bookings.

import { ME } from "../../test/fakeApi";

export const BOOKER = { ...ME, id: 9, name: "Hannah Hirer", is_booking_user: true, player: null };

export const CLUB = {
  id: 1,
  name: "Club A",
  hourly_fee: "600.00",
  fields: [
    { id: 3, name: "Pitch 3" },
    { id: 4, name: "Pitch 4" },
  ],
};

/** Pitch 3 free at 18:00 and 21:00, Pitch 4 not at all, for 2 hours. */
export const FREE = {
  date: "2026-10-27",
  hours: 2,
  hourly_fee: "600.00",
  price: "1200.00",
  fields: [
    { field: { id: 3, name: "Pitch 3" }, starts: ["2026-10-27T16:00:00Z", "2026-10-27T19:00:00Z"] },
    { field: { id: 4, name: "Pitch 4" }, starts: [] },
  ],
};

export function booking(overrides: object = {}) {
  return {
    id: 70,
    club: { id: 1, name: "Club A" },
    field: { id: 3, name: "Pitch 3" },
    starts_at: "2026-10-27T16:00:00Z",
    ends_at: "2026-10-27T18:00:00Z",
    hours: 2,
    hourly_fee: "600.00",
    price: "1200.00",
    status: "pending",
    created_at: "2026-10-23T10:00:00Z",
    decided_at: null,
    decline_reason: "",
    cancelled_at: null,
    is_over: false,
    can_cancel: true,
    can_reschedule: true,
    cancelled_by_club: false,
    paid: "0.00",
    outstanding: "1200.00",
    payment_due_at: "2026-10-26T16:00:00Z",
    payment_requested: false,
    can_pay: false,
    ...overrides,
  };
}

/** The club's policy rows, as the API words them (FR-45). */
export const ROWS = [
  { window: "free", when: "Before payment is taken (24h before)", cancel: "Free; nothing charged", reschedule: "Free" },
  { window: "late", when: "24h to 6h before", cancel: "50% back as credit", reschedule: "Free, once, to a slot within 30 days" },
  { window: "very_late", when: "Under 6h before, or no-show", cancel: "No credit", reschedule: "Not allowed" },
  {
    window: "club",
    when: "The club cancels (pitch, weather, operational)",
    cancel: "100% back as credit. Ask the club about a card refund.",
    reschedule: "Free",
  },
];

export const POLICY = { club: { id: 1, name: "Club A" }, payment_cutoff_hours: 24, rows: ROWS, credit: "0.00" };

export function outcome(overrides: { cancel?: object; reschedule?: object; credit?: string } = {}) {
  return {
    cancel: {
      window: "free",
      allowed: true,
      paid: "0.00",
      credit_percent: 100,
      credit: "0.00",
      kept: "0.00",
      summary: "Cancelling now is free. Nothing is charged.",
      ...overrides.cancel,
    },
    reschedule: {
      window: "free",
      allowed: true,
      reschedules_left: null,
      latest_start: null,
      summary: "Moving it now is free.",
      ...overrides.reschedule,
    },
    rows: ROWS,
    credit: overrides.credit ?? "0.00",
  };
}

export function clubBooking(overrides: object = {}) {
  const { can_cancel: _c, can_reschedule: _r, can_pay: _p, ...rest } = booking();
  return {
    ...rest,
    user: { id: 9, name: "Hannah Hirer", email: "hirer@example.com", phone: "082 555 0101" },
    decided_by: null,
    can_decide: true,
    can_club_cancel: true,
    club_cancel_summary: "Nothing has been paid, so nothing is charged or returned.",
    can_record_cash: false,
    ...overrides,
  };
}

export function bookingBarcode(overrides: object = {}) {
  return {
    id: 90,
    code: "BK24100815",
    display_code: "BK 2410 0815",
    mode: "booking",
    team: null,
    holder: "Booking: Hannah Hirer",
    season: null,
    fixture: null,
    booking: {
      id: 70,
      starts_at: "2026-10-27T16:00:00Z",
      ends_at: "2026-10-27T18:00:00Z",
      hours: 2,
      field: { id: 3, name: "Pitch 3" },
    },
    valid_until: "2026-10-27",
    issued_at: "2026-10-23T12:00:00Z",
    ...overrides,
  };
}
