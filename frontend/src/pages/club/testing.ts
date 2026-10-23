// Shared by the club setup screen tests: an Admin of Club A, signed in.

import { screen } from "@testing-library/react";
import { setTokens } from "../../api/auth";
import { fakeApi, ME, TOKENS, type Routes } from "../../test/fakeApi";
import { renderApp } from "../../test/renderApp";

export const ADMIN_ME = {
  ...ME,
  club_roles: [{ club_id: 1, club_name: "Club A", role: "admin" as const }],
};

export const SETTINGS = {
  league_fee: null,
  friendly_fee: null,
  booking_hourly_fee: null,
  match_length_minutes: null,
  division_min_players: 5,
  confirmation_hours_before: 36,
  confirmation_resend_after_hours: 12,
  readiness_hours_before: 6,
  replacement_close_hours_before: 2,
  booking_payment_cutoff_hours: 24,
  booking_late_cancel_hours: 6,
  booking_late_cancel_credit_percent: 50,
  booking_no_show_credit_percent: 0,
  booking_club_cancel_credit_percent: 100,
  booking_reschedule_window_days: 30,
  booking_reschedules_allowed: 1,
  payment_mode: "gateway",
  payment_provider: "payfast",
  missing: ["league_fee", "friendly_fee", "booking_hourly_fee", "match_length_minutes"],
  updated_at: "2026-10-23T10:00:00Z",
  updated_by_name: null,
};

/** Opens `path` as Club A's Admin, with the API answering `routes`. */
export async function openAsAdmin(path: string, routes: Routes, heading: string) {
  await setTokens(TOKENS);
  const api = fakeApi({ "GET /api/v1/auth/me/": { status: 200, body: ADMIN_ME }, ...routes });
  const router = renderApp(path);
  await screen.findByRole("heading", { name: heading });
  return { ...api, router };
}
