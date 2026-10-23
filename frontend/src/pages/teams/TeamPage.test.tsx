import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { json, ME } from "../../test/fakeApi";
import { joinRequest, LIONS, member, openAs } from "./testing";

const TEAM = "GET /api/v1/teams/7/";
const MEMBERS = "GET /api/v1/teams/7/members/";
const CAPTAIN = { ...ME, id: 2, name: "Thandi Mokoena", captain_of: [7] };
const SIPHO = member({ player_id: 1, name: "Sipho Dlamini", is_captain: false, position: "goalkeeper" });

describe("TeamPage", () => {
  it("shows the Players to a Player in the Team, who can leave it after asking", async () => {
    const { calls, router } = await openAs(
      "/teams/7",
      {
        [TEAM]: { status: 200, body: LIONS },
        [MEMBERS]: { status: 200, body: [SIPHO, member()] },
        "POST /api/v1/teams/7/leave/": { status: 200, body: {} },
        "GET /api/v1/me/teams/": { status: 200, body: [] },
        "GET /api/v1/me/join-requests/": { status: 200, body: [] },
      },
      "Red Lions",
    );
    const user = userEvent.setup();

    const squad = screen.getByRole("region", { name: /Players/ });
    expect(await within(squad).findByText("Sipho Dlamini (you)")).toBeInTheDocument();
    expect(within(squad).getByText("Goalkeeper · Joined Tue 20 Oct")).toBeInTheDocument();
    expect(within(squad).getByText("Captain")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Asking to join" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Leave team" }));
    expect(calls.some((c) => c.method === "POST")).toBe(false);
    await user.click(screen.getByRole("button", { name: "Leave Red Lions" }));

    await screen.findByRole("heading", { name: "Teams" });
    expect(router.state.location.pathname).toBe("/teams");
  });

  it("lets the Captain accept and decline Players asking to join", async () => {
    const pending = [joinRequest(), joinRequest({ id: 41, player_id: 9, player_name: "Lerato Khumalo", position: null })];
    const { calls } = await openAs(
      "/teams/7",
      {
        [TEAM]: { status: 200, body: LIONS },
        [MEMBERS]: [
          { status: 200, body: [member()] },
          { status: 200, body: [SIPHO, member()] },
        ],
        "GET /api/v1/teams/7/join-requests/": [
          { status: 200, body: pending },
          { status: 200, body: [pending[1]] },
          { status: 200, body: [] },
        ],
        "POST /api/v1/join-requests/40/accept/": { status: 200, body: joinRequest({ status: "accepted" }) },
        "POST /api/v1/join-requests/41/decline/": { status: 200, body: joinRequest({ id: 41, status: "declined" }) },
      },
      "Red Lions",
      CAPTAIN,
    );
    const user = userEvent.setup();

    const asking = await screen.findByRole("region", { name: "Asking to join" });
    expect(await within(asking).findByText("Outfield · Asked Thu 22 Oct")).toBeInTheDocument();
    await user.click(within(asking).getByRole("button", { name: "Accept Sipho Dlamini" }));

    const squad = screen.getByRole("region", { name: /Players/ });
    expect(await within(squad).findByText("Sipho Dlamini")).toBeInTheDocument();
    await user.click(await within(asking).findByRole("button", { name: "Decline Lerato Khumalo" }));

    expect(await within(asking).findByText("No one is asking to join right now.")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST").map((c) => c.path)).toEqual([
      "/api/v1/join-requests/40/accept/",
      "/api/v1/join-requests/41/decline/",
    ]);
    expect(screen.queryByRole("button", { name: "Leave team" })).not.toBeInTheDocument();
  });

  it("shows why the API refused to accept a Player", async () => {
    await openAs(
      "/teams/7",
      {
        [TEAM]: { status: 200, body: LIONS },
        [MEMBERS]: { status: 200, body: [member()] },
        "GET /api/v1/teams/7/join-requests/": { status: 200, body: [joinRequest()] },
        "POST /api/v1/join-requests/40/accept/": {
          status: 409,
          body: { detail: "This Player joined another Team in this Division first." },
        },
      },
      "Red Lions",
      CAPTAIN,
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Accept Sipho Dlamini" }));

    expect(await screen.findByText("This Player joined another Team in this Division first.")).toBeInTheDocument();
  });

  it("sends an answer once, even on a double tap", async () => {
    let finish: (response: Response) => void = () => {};
    const { calls } = await openAs(
      "/teams/7",
      {
        [TEAM]: { status: 200, body: LIONS },
        [MEMBERS]: { status: 200, body: [member()] },
        "GET /api/v1/teams/7/join-requests/": { status: 200, body: [joinRequest()] },
        "POST /api/v1/join-requests/40/accept/": () => new Promise<Response>((resolve) => (finish = resolve)),
      },
      "Red Lions",
      CAPTAIN,
    );
    const user = userEvent.setup();

    const accept = await screen.findByRole("button", { name: "Accept Sipho Dlamini" });
    await user.click(accept);
    expect(accept).toBeDisabled();
    expect(screen.getByRole("button", { name: "Decline Sipho Dlamini" })).toBeDisabled();
    await user.click(accept);
    finish(json(200, joinRequest({ status: "accepted" })));

    await screen.findByRole("button", { name: "Accept Sipho Dlamini" });
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(1);
  });

  it("tells the Captain a new Team waits for the Admin", async () => {
    await openAs(
      "/teams/7",
      {
        [TEAM]: { status: 200, body: { ...LIONS, status: "requested" } },
        [MEMBERS]: { status: 200, body: [member()] },
      },
      "Red Lions",
      CAPTAIN,
    );

    expect(screen.getAllByText("Waiting for the Admin").length).toBeGreaterThan(0);
    expect(screen.queryByRole("region", { name: "Asking to join" })).not.toBeInTheDocument();
  });

  it("keeps the Players private from someone not in the Team", async () => {
    await openAs(
      "/teams/7",
      {
        [TEAM]: { status: 200, body: LIONS },
        [MEMBERS]: { status: 403, body: { detail: "Only Players in this Team can see who is in it." } },
      },
      "Red Lions",
    );

    expect(await screen.findByText("Only Players in this Team can see who is in it.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Leave team" })).not.toBeInTheDocument();
  });
});
