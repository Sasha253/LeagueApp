import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { joinRequest, LIONS, OLD_BOYS, openAs } from "./testing";

const MINE = "GET /api/v1/me/teams/";
const REQUESTS = "GET /api/v1/me/join-requests/";

describe("MyTeamsPage", () => {
  it("lists the Teams you're in, and the ones you were in", async () => {
    await openAs(
      "/teams",
      {
        [MINE]: {
          status: 200,
          body: [
            { id: 1, team: LIONS, joined_at: "2026-10-20T10:00:00Z", left_at: null, is_captain: false },
            { id: 2, team: { ...OLD_BOYS, name: "Old Boys" }, joined_at: "2026-01-20T10:00:00Z", left_at: "2026-05-01T10:00:00Z", is_captain: false },
          ],
        },
        [REQUESTS]: { status: 200, body: [] },
      },
      "Teams",
    );

    const link = await screen.findByRole("link", { name: /Red Lions/ });
    expect(link).toHaveAttribute("href", "/teams/7");
    expect(within(link).getByText("Tuesday · Division 2 · Spring 2026 · Club A")).toBeInTheDocument();
    expect(within(link).getByText("Captain: Thandi Mokoena · 4 players")).toBeInTheDocument();
    const before = screen.getByRole("region", { name: "Before" });
    expect(within(before).getByText("Old Boys")).toBeInTheDocument();
    expect(within(before).getByText("Left")).toBeInTheDocument();
  });

  it("shows a Team waiting for the Admin and that you captain it", async () => {
    await openAs(
      "/teams",
      {
        [MINE]: {
          status: 200,
          body: [
            { id: 1, team: { ...LIONS, status: "requested", captain_id: 1 }, joined_at: "2026-10-20T10:00:00Z", left_at: null, is_captain: true },
          ],
        },
        [REQUESTS]: { status: 200, body: [] },
      },
      "Teams",
    );

    const link = await screen.findByRole("link", { name: /Red Lions/ });
    expect(within(link).getByText("Waiting for the Admin")).toBeInTheDocument();
    expect(within(link).getByText(/You're the Captain/)).toBeInTheDocument();
  });

  it("offers Find a team and Request a Team when you have no Team", async () => {
    await openAs("/teams", { [MINE]: { status: 200, body: [] }, [REQUESTS]: { status: 200, body: [] } }, "Teams");

    expect(await screen.findByText(/You're not in a Team yet/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Find a team" })).toHaveAttribute("href", "/teams/find");
    expect(screen.getByRole("link", { name: "Request a Team" })).toHaveAttribute("href", "/teams/new");
  });

  it("withdraws a request to join", async () => {
    const { calls } = await openAs(
      "/teams",
      {
        [MINE]: { status: 200, body: [] },
        [REQUESTS]: [
          { status: 200, body: [joinRequest(), joinRequest({ id: 41, team: OLD_BOYS, status: "declined" })] },
          { status: 200, body: [joinRequest({ status: "withdrawn" }), joinRequest({ id: 41, team: OLD_BOYS, status: "declined" })] },
        ],
        "POST /api/v1/join-requests/40/withdraw/": { status: 200, body: joinRequest({ status: "withdrawn" }) },
      },
      "Teams",
    );
    const user = userEvent.setup();

    const requests = await screen.findByRole("region", { name: "Requests to join" });
    expect(within(requests).getByText("Waiting for the Captain")).toBeInTheDocument();
    expect(within(requests).getByText("Declined")).toBeInTheDocument();
    await user.click(within(requests).getByRole("button", { name: "Withdraw request to join Red Lions" }));

    await screen.findByRole("region", { name: "Requests to join" });
    expect(await screen.findByText("Old Boys")).toBeInTheDocument();
    expect(screen.queryByText("Red Lions")).not.toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(1);
  });

  it("tells a user who doesn't play that Teams are for Players", async () => {
    await openAs(
      "/teams",
      {
        [MINE]: { status: 403, body: { detail: "Only Players can do this." } },
        [REQUESTS]: { status: 403, body: { detail: "Only Players can do this." } },
      },
      "Teams",
    );

    expect(await screen.findByText(/Teams are for Players/)).toBeInTheDocument();
  });
});
