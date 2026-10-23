import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ME } from "../../test/fakeApi";
import { CLUB, LIONS, openAs } from "./testing";

const SPRING = { id: 5, club: CLUB, name: "Spring 2026", starts_on: "2026-08-04", ends_on: "2026-11-24" };
const DIVISIONS = [
  { id: 3, name: "Division 2", weekday: 1, min_players: 5, effective_league_fee: "350.00", max_teams: 8, teams: 4, is_open: true },
  { id: 4, name: "Division 1", weekday: 1, min_players: 5, effective_league_fee: "350.00", max_teams: 2, teams: 2, is_open: false },
  { id: 6, name: "Division 3", weekday: 3, min_players: 6, effective_league_fee: null, max_teams: null, teams: 0, is_open: false },
];

function routes(extra: object = {}) {
  return {
    "GET /api/v1/seasons/": { status: 200, body: [SPRING] },
    "GET /api/v1/seasons/5/divisions/": { status: 200, body: DIVISIONS },
    ...extra,
  };
}

describe("RequestTeamPage", () => {
  it("shows each Division with its fee and room, and which are closed", async () => {
    await openAs("/teams/new", routes(), "Request a Team");
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Spring 2026 · Club A" }));
    expect(screen.getByText("Tue 4 Aug to Tue 24 Nov")).toBeInTheDocument();

    const open = await screen.findByRole("button", { name: /Tuesday · Division 2/ });
    expect(within(open).getByText("R 350 league fee · 4 of 8 Teams · min 5 players")).toBeInTheDocument();
    expect(open).toBeEnabled();
    const full = screen.getByRole("button", { name: /Tuesday · Division 1/ });
    expect(full).toBeDisabled();
    expect(within(full).getByText("Full")).toBeInTheDocument();
    const unpriced = screen.getByRole("button", { name: /Thursday · Division 3/ });
    expect(unpriced).toBeDisabled();
    expect(within(unpriced).getByText("Not open yet")).toBeInTheDocument();
  });

  it("sends the request to the Admin and waits", async () => {
    const { calls } = await openAs(
      "/teams/new",
      routes({
        "POST /api/v1/teams/": { status: 201, body: { ...LIONS, status: "requested", captain_id: 1, players: 1 } },
      }),
      "Request a Team",
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Spring 2026 · Club A" }));
    const send = screen.getByRole("button", { name: "Send to Admin" });
    expect(send).toBeDisabled();
    await user.click(await screen.findByRole("button", { name: /Tuesday · Division 2/ }));
    expect(screen.getByRole("button", { name: /Tuesday · Division 2/ })).toHaveAttribute("aria-pressed", "true");
    await user.type(screen.getByLabelText("Team name"), " Red Lions ");
    await user.click(send);

    expect(await screen.findByText("Red Lions is waiting for the Admin")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Red Lions" })).toHaveAttribute("href", "/teams/7");
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ season: 5, division: 3, name: "Red Lions" });
    // "me" is read again: the Player now captains a Team.
    expect(calls.filter((c) => c.path === "/api/v1/auth/me/")).toHaveLength(2);
  });

  it("shows why the API refused the request", async () => {
    await openAs(
      "/teams/new",
      routes({
        "POST /api/v1/teams/": { status: 400, body: { name: ["A Team in this Division already has that name."] } },
      }),
      "Request a Team",
      ME,
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Spring 2026 · Club A" }));
    await user.click(await screen.findByRole("button", { name: /Tuesday · Division 2/ }));
    await user.type(screen.getByLabelText("Team name"), "Red Lions");
    await user.click(screen.getByRole("button", { name: "Send to Admin" }));

    expect(await screen.findByText("A Team in this Division already has that name.")).toBeInTheDocument();
  });

  it("says when no Season is open", async () => {
    await openAs("/teams/new", routes({ "GET /api/v1/seasons/": { status: 200, body: [] } }), "Request a Team");

    expect(await screen.findByText("No Season is open for Teams right now.")).toBeInTheDocument();
  });
});
