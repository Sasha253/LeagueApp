// Shared by the Finances screen tests: the finance tracker's answers as the API sends them.

import { ME } from "../../test/fakeApi";

export const ADMIN = {
  ...ME,
  id: 50,
  name: "Club Admin",
  player: null,
  club_roles: [{ club_id: 1, club_name: "Club A", role: "admin" as const }],
};

export function line(overrides: object = {}) {
  return { card: "0.00", cash: "0.00", received: "0.00", credit_spent: "0.00", returned_as_credit: "0.00", ...overrides };
}

export function figures(overrides: object = {}) {
  return {
    teams: 8,
    expected: "28000.00",
    outstanding: "490.00",
    team_credit_held: "420.00",
    league: line({ card: "15960.00", cash: "2450.00", received: "18410.00", credit_spent: "700.00" }),
    friendly: line({ card: "560.00", cash: "140.00", received: "700.00" }),
    ...overrides,
  };
}

export const SPRING = { id: 5, name: "Spring 2026", starts_on: "2026-09-01", ends_on: "2026-12-19" };
export const AUTUMN = { id: 4, name: "Autumn 2026", starts_on: "2026-03-01", ends_on: "2026-06-30" };

export const TUESDAY_NIGHT = {
  id: 2,
  weekday: 1 as const,
  divisions: [
    { id: 3, night: 2, name: "Division 2", min_players: 5 },
    { id: 6, night: 2, name: "Division 1", min_players: 5 },
  ],
};
export const THURSDAY_NIGHT = { id: 4, weekday: 3 as const, divisions: [{ id: 9, night: 4, name: "Division 1", min_players: 5 }] };

export function summary(overrides: object = {}) {
  return {
    season: { id: 5, name: "Spring 2026" },
    night: null,
    division: null,
    received: "19650.00",
    totals: figures(),
    booking: line({ card: "540.00", received: "540.00" }),
    credit_held: { team: "420.00", player: "210.00", booking_user: "90.00" },
    nights: [
      {
        ...figures(),
        night: { id: 2, weekday: 1 },
        divisions: [{ ...figures(), division: { id: 3, name: "Division 2" } }],
      },
    ],
    ...overrides,
  };
}

export function entry(overrides: object = {}) {
  return {
    id: 11,
    created_at: "2026-10-20T17:40:00Z",
    kind: "payment",
    method: "card",
    category: "league",
    amount: "70.00",
    subject: "team",
    team: { id: 7, name: "Red Lions" },
    player: { id: 1, name: "Sipho Dlamini" },
    fixture_id: null,
    reverses_id: null,
    reason: "",
    recorded_by_name: null,
    ...overrides,
  };
}

export function ledger(overrides: object = {}) {
  return {
    team: { id: 7, name: "Red Lions" },
    season: { id: 5, name: "Spring 2026" },
    division: { id: 3, name: "Division 2" },
    night: { id: 2, weekday: 1 },
    due: "350.00",
    paid: "150.00",
    outstanding: "200.00",
    paid_by_method: { card: "70.00", cash: "50.00", credit: "30.00" },
    is_paid: false,
    team_credit_held: "0.00",
    entries: [
      entry({ id: 14, kind: "reversal", method: "cash", amount: "20.00", reverses_id: 13, reason: "Typed R 20 too much", recorded_by_name: "Ada Admin", player: null, created_at: "2026-10-22T08:00:00Z" }),
      entry({ id: 13, method: "cash", amount: "70.00", recorded_by_name: "Ada Admin", player: null, created_at: "2026-10-21T17:00:00Z" }),
      entry(),
      entry({ id: 12, kind: "payment", method: "credit", amount: "30.00", player: { id: 2, name: "Thandi Mokoena" }, created_at: "2026-10-19T10:00:00Z" }),
      entry({ id: 10, kind: "charge", method: "", amount: "350.00", player: null, created_at: "2026-09-01T08:00:00Z" }),
    ],
    ...overrides,
  };
}

export function income(season: { id: number; name: string }, overrides: object = {}) {
  return {
    season,
    received: "19650.00",
    league: line({ card: "15960.00", cash: "2450.00", received: "18410.00" }),
    friendly: line({ cash: "700.00", received: "700.00" }),
    booking: line({ card: "540.00", received: "540.00" }),
    nights: [{ night: { id: 2, weekday: 1 }, league: line({ received: "18410.00" }), friendly: line({ received: "700.00" }) }],
    ...overrides,
  };
}
