import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ADMIN } from "../finance/testing";
import { LIONS, OLD_BOYS, openAs } from "./testing";

const TEAMS = "GET /api/v1/clubs/1/teams/";
const INVITES = "GET /api/v1/clubs/1/team-invites/";
const OPEN = {
  id: 30,
  team: 7,
  team_name: "Red Lions",
  email: "new@example.com",
  created_at: "2026-10-27T17:40:00Z",
  accepted: false,
};

describe("InvitePlayerPage", () => {
  it("invites someone new, who joins when they sign up", async () => {
    const { calls } = await openAs(
      "/clubs/1/players/invite?team=7",
      {
        [TEAMS]: { status: 200, body: [LIONS, OLD_BOYS] },
        [INVITES]: [{ status: 200, body: [] }, { status: 200, body: [OPEN] }],
        "POST /api/v1/clubs/1/team-invites/": { status: 201, body: OPEN },
      },
      "Invite a Player",
      ADMIN,
    );

    expect(await screen.findByRole("button", { name: "Red Lions, Division 2, Spring 2026" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(await screen.findByText("No open invites.")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Email"), "new@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Invite" }));

    expect(calls.find((call) => call.method === "POST")?.body).toEqual({ team: 7, email: "new@example.com" });
    expect(await screen.findByText("Invite sent")).toBeInTheDocument();
    expect(screen.getByText("new@example.com joins Red Lions when they sign up as a Player.")).toBeInTheDocument();
    const waiting = screen.getByRole("region", { name: "Waiting to sign up" });
    expect(await within(waiting).findByText("new@example.com")).toBeInTheDocument();
    expect(within(waiting).getByText("Red Lions · invited Tue 27 Oct · 19:40")).toBeInTheDocument();
  });

  it("says when a Player is in the Team at once", async () => {
    await openAs(
      "/clubs/1/players/invite",
      {
        [TEAMS]: { status: 200, body: [LIONS] },
        [INVITES]: { status: 200, body: [] },
        "POST /api/v1/clubs/1/team-invites/": {
          status: 201,
          body: { ...OPEN, email: "sipho@example.com", accepted: true },
        },
      },
      "Invite a Player",
      ADMIN,
    );

    await userEvent.click(await screen.findByRole("button", { name: "Red Lions, Division 2, Spring 2026" }));
    await userEvent.type(screen.getByLabelText("Email"), "sipho@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Invite" }));

    expect(await screen.findByText("In Red Lions")).toBeInTheDocument();
    expect(screen.getByText("sipho@example.com is now a Player in Red Lions.")).toBeInTheDocument();
  });

  it("cancels an open invite after asking", async () => {
    const { calls } = await openAs(
      "/clubs/1/players/invite",
      {
        [TEAMS]: { status: 200, body: [LIONS] },
        [INVITES]: [{ status: 200, body: [OPEN] }, { status: 200, body: [] }],
        "DELETE /api/v1/clubs/1/team-invites/30/": { status: 204 },
      },
      "Invite a Player",
      ADMIN,
    );

    await userEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel invite for new@example.com" }));

    expect(calls.some((call) => call.method === "DELETE")).toBe(true);
    expect(await screen.findByText("No open invites.")).toBeInTheDocument();
  });

  it("asks for a Team first", async () => {
    await openAs(
      "/clubs/1/players/invite",
      { [TEAMS]: { status: 200, body: [] }, [INVITES]: { status: 200, body: [] } },
      "Invite a Player",
      ADMIN,
    );

    expect(await screen.findByText("No active Teams yet")).toBeInTheDocument();
  });
});
