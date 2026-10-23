// Shared by the payment screen tests: a Team's payment options, a Payment and who has paid.

import { CLUB, LIONS } from "../teams/testing";

export { CLUB, LIONS };

export const TEAM = { id: 7, name: "Red Lions" };
export const REFERENCE = "6f1c2c43-5d0c-4b8e-9d55-0e1d2f3a4b5c";
export const CHECKOUT_URL = "https://sandbox.payfast.co.za/eng/process?merchant_id=10000100&signature=abc";

export function options(overrides: object = {}) {
  return {
    team: TEAM,
    due: "350.00",
    outstanding: "350.00",
    is_paid: false,
    card_enabled: true,
    minimum_card_amount: "5.00",
    suggested_amount: "70.00",
    my_credit: "0.00",
    team_credit: null,
    ...overrides,
  };
}

export function payment(overrides: object = {}) {
  return {
    reference: REFERENCE,
    team: TEAM,
    amount: "70.00",
    credit_used: "none",
    credit_amount: "0.00",
    card_amount: "70.00",
    provider: "payfast",
    status: "pending",
    created_at: "2026-10-23T17:00:00Z",
    completed_at: null,
    checkout: { url: CHECKOUT_URL, action: "https://sandbox.payfast.co.za/eng/process", form_fields: [] },
    ...overrides,
  };
}

export function summary(overrides: object = {}) {
  return {
    team: TEAM,
    due: "350.00",
    paid: "150.00",
    outstanding: "200.00",
    is_paid: false,
    players: [
      { player_id: 1, name: "Sipho Dlamini", is_captain: false, in_team: true, paid: "100.00", has_paid: true },
      { player_id: 2, name: "Thandi Mokoena", is_captain: true, in_team: true, paid: "0.00", has_paid: false },
      { player_id: 9, name: "Lerato Khumalo", is_captain: false, in_team: false, paid: "20.00", has_paid: true },
    ],
    paid_for_team: "30.00",
    team_credit: "40.00",
    ...overrides,
  };
}
