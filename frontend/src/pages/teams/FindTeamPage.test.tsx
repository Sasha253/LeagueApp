import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { json } from "../../test/fakeApi";
import { CLUB, joinRequest, LIONS, OLD_BOYS, openAs } from "./testing";

const NIGHTS = [
  { id: 11, club: CLUB, weekday: 1 },
  { id: 12, club: CLUB, weekday: 3 },
];

/** Answers the search with `teams`, and records each search's query. */
function search(teams: object[]) {
  const queries: string[] = [];
  const answer = (request: Request) => {
    queries.push(new URL(request.url).search);
    return json(200, teams);
  };
  return { queries, answer };
}

function routes(found: ReturnType<typeof search>, extra: object = {}) {
  return {
    "GET /api/v1/nights/": { status: 200, body: NIGHTS },
    "GET /api/v1/teams/": found.answer,
    "GET /api/v1/me/teams/": { status: 200, body: [] },
    "GET /api/v1/me/join-requests/": { status: 200, body: [] },
    ...extra,
  };
}

describe("FindTeamPage", () => {
  it("searches by name and Night, then by the Night's Divisions", async () => {
    const found = search([LIONS, OLD_BOYS]);
    await openAs("/teams/find", routes(found), "Find a team");
    const user = userEvent.setup();

    const results = await screen.findByRole("list", { name: "Teams found" });
    expect(within(results).getByText("Red Lions")).toBeInTheDocument();
    expect(within(results).getByText("Captain: Pieter Botha · 6 players")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Team name"), "lions");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await user.click(screen.getByRole("button", { name: "Tue" }));
    await user.click(await screen.findByRole("button", { name: "Division 1" }));

    expect(found.queries).toEqual(["", "?q=lions", "?q=lions&night=11", "?q=lions&night=11&division=4"]);
    expect(screen.getByRole("button", { name: "Division 1" })).toHaveAttribute("aria-pressed", "true");
  });

  it("asks to join and waits for the Captain", async () => {
    const found = search([LIONS]);
    const { calls } = await openAs(
      "/teams/find",
      routes(found, {
        "GET /api/v1/me/join-requests/": [
          { status: 200, body: [] },
          { status: 200, body: [joinRequest()] },
        ],
        "POST /api/v1/teams/7/join/": { status: 201, body: joinRequest() },
      }),
      "Find a team",
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Ask to join Red Lions" }));

    expect(await screen.findByText("Request sent to Red Lions")).toBeInTheDocument();
    expect(screen.getByText(/You'll join when Thandi Mokoena accepts/)).toBeInTheDocument();
    const results = screen.getByRole("list", { name: "Teams found" });
    expect(await within(results).findByText("Waiting for the Captain")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST").map((c) => c.path)).toEqual(["/api/v1/teams/7/join/"]);
  });

  it("shows why the API refused a request to join", async () => {
    const found = search([LIONS]);
    await openAs(
      "/teams/find",
      routes(found, {
        "POST /api/v1/teams/7/join/": {
          status: 409,
          body: { detail: "You're already in a Team in this Division this Season." },
        },
      }),
      "Find a team",
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Ask to join Red Lions" }));

    expect(await screen.findByText("You're already in a Team in this Division this Season.")).toBeInTheDocument();
  });

  it("shows the Teams you're already in", async () => {
    const found = search([LIONS]);
    await openAs(
      "/teams/find",
      routes(found, {
        "GET /api/v1/me/teams/": {
          status: 200,
          body: [{ id: 1, team: LIONS, joined_at: "2026-10-20T10:00:00Z", left_at: null, is_captain: false }],
        },
      }),
      "Find a team",
    );

    const results = await screen.findByRole("list", { name: "Teams found" });
    expect(await within(results).findByText("You're in")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ask to join Red Lions" })).not.toBeInTheDocument();
  });

  it("says when nothing matches", async () => {
    await openAs("/teams/find", routes(search([])), "Find a team");

    expect(await screen.findByText("No Teams match. Try another name or Night.")).toBeInTheDocument();
  });
});
