// Shared by the Team screen tests: a signed-in Player, Teams and requests to join.

import { screen } from "@testing-library/react";
import { setTokens } from "../../api/auth";
import { fakeApi, ME, TOKENS, type Routes } from "../../test/fakeApi";
import { renderApp } from "../../test/renderApp";

export const CLUB = { id: 1, name: "Club A" };

export const LIONS = {
  id: 7,
  name: "Red Lions",
  club: CLUB,
  season: { id: 5, name: "Spring 2026" },
  division: { id: 3, name: "Division 2" },
  weekday: 1 as const,
  captain_id: 2,
  captain_name: "Thandi Mokoena",
  players: 4,
  status: "active" as const,
};

export const OLD_BOYS = {
  ...LIONS,
  id: 8,
  name: "Old Boys",
  division: { id: 4, name: "Division 1" },
  captain_id: 3,
  captain_name: "Pieter Botha",
  players: 6,
};

export function joinRequest(overrides: object = {}) {
  return {
    id: 40,
    team: LIONS,
    player_id: 1,
    player_name: "Sipho Dlamini",
    position: "outfield" as const,
    status: "pending" as const,
    created_at: "2026-10-22T10:00:00Z",
    decided_at: null,
    ...overrides,
  };
}

export function member(overrides: object = {}) {
  return {
    player_id: 2,
    name: "Thandi Mokoena",
    position: "outfield" as const,
    is_captain: true,
    joined_at: "2026-10-20T10:00:00Z",
    ...overrides,
  };
}

/** Opens `path` as `me` (a Player by default), with the API answering `routes`. */
export async function openAs(path: string, routes: Routes, heading: string, me: object = ME) {
  await setTokens(TOKENS);
  const api = fakeApi({ "GET /api/v1/auth/me/": { status: 200, body: me }, ...routes });
  const router = renderApp(path);
  await screen.findByRole("heading", { name: heading });
  return { ...api, router };
}
