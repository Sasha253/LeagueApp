import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ADMIN_ME } from "../club/testing";
import { LIONS, member, openAs } from "./testing";

const DETAIL = "/api/v1/clubs/1/teams/7/";
const SIPHO = member({ player_id: 1, name: "Sipho Dlamini", is_captain: false });
const TEAM = {
  ...LIONS,
  requested_by_name: "Thandi Mokoena",
  requested_at: "2026-10-21T08:00:00Z",
  decided_by_name: "Ayanda Admin",
  decided_at: "2026-10-22T08:00:00Z",
  decline_reason: "",
  members: [SIPHO, member()],
};

describe("ClubTeamPage", () => {
  it("shows who asked, who confirmed, and the Players", async () => {
    await openAs("/clubs/1/teams/7", { [`GET ${DETAIL}`]: { status: 200, body: TEAM } }, "Red Lions", ADMIN_ME);

    expect(
      screen.getByText("Asked by Thandi Mokoena on Wed 21 Oct · Confirmed by Ayanda Admin on Thu 22 Oct"),
    ).toBeInTheDocument();
    const players = screen.getByRole("region", { name: /Players/ });
    expect(within(players).getByText("Sipho Dlamini")).toBeInTheDocument();
    expect(within(players).getByText("Captain")).toBeInTheDocument();
  });

  it("assigns a new Captain after asking", async () => {
    const after = {
      ...TEAM,
      captain_id: 1,
      captain_name: "Sipho Dlamini",
      members: [{ ...SIPHO, is_captain: true }, member({ is_captain: false })],
    };
    const { calls } = await openAs(
      "/clubs/1/teams/7",
      {
        [`GET ${DETAIL}`]: [
          { status: 200, body: TEAM },
          { status: 200, body: after },
        ],
        [`POST ${DETAIL}captain/`]: { status: 200, body: after },
      },
      "Red Lions",
      ADMIN_ME,
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Make Captain" }));
    expect(calls.some((c) => c.method === "POST")).toBe(false);
    await user.click(screen.getByRole("button", { name: "Make Sipho Dlamini Captain" }));

    expect(await screen.findByText("Sipho Dlamini is the Captain now.")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ player: 1 });
  });

  it("shows why the API refused a Captain", async () => {
    await openAs(
      "/clubs/1/teams/7",
      {
        [`GET ${DETAIL}`]: { status: 200, body: TEAM },
        [`POST ${DETAIL}captain/`]: { status: 400, body: { player: ["That Player isn't in this Team."] } },
      },
      "Red Lions",
      ADMIN_ME,
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Make Captain" }));
    await user.click(screen.getByRole("button", { name: "Make Sipho Dlamini Captain" }));

    expect(await screen.findByText("That Player isn't in this Team.")).toBeInTheDocument();
  });
});
