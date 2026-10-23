import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { json } from "../../test/fakeApi";
import { ADMIN_ME } from "../club/testing";
import { LIONS, member, OLD_BOYS, openAs } from "./testing";

const LIST = "/api/v1/clubs/1/teams/";

function adminTeam(team: typeof LIONS, overrides: object = {}) {
  return {
    ...team,
    requested_by_name: team.captain_name,
    requested_at: "2026-10-21T08:00:00Z",
    decided_by_name: null,
    decided_at: null,
    decline_reason: "",
    members: [member({ player_id: team.captain_id, name: team.captain_name })],
    ...overrides,
  };
}

const REQUESTED = adminTeam(LIONS, { status: "requested" });
const ACTIVE = adminTeam(OLD_BOYS);

/** Answers the list by its `status` query: `requested` in turn, then `active`. */
function byStatus(requested: object[][], active: object[][]) {
  const seen = { requested: 0, active: 0 };
  return (request: Request) => {
    const status = new URL(request.url).searchParams.get("status") as "requested" | "active";
    const answers = status === "requested" ? requested : active;
    const body = answers[Math.min(seen[status]++, answers.length - 1)];
    return json(200, body);
  };
}

describe("ClubTeamsPage", () => {
  it("lists Team requests, then the club's Teams", async () => {
    await openAs(
      "/clubs/1/teams",
      { [`GET ${LIST}`]: byStatus([[REQUESTED]], [[ACTIVE]]) },
      "Team requests",
      ADMIN_ME,
    );

    const waiting = await screen.findByRole("list", { name: "Waiting for you" });
    expect(within(waiting).getByText("Red Lions")).toBeInTheDocument();
    expect(within(waiting).getByText("Asked by Thandi Mokoena on Wed 21 Oct")).toBeInTheDocument();
    const teams = screen.getByRole("region", { name: "Teams" });
    expect(within(teams).getByRole("link", { name: /Old Boys/ })).toHaveAttribute("href", "/clubs/1/teams/8");
  });

  it("confirms a Team request", async () => {
    const { calls } = await openAs(
      "/clubs/1/teams",
      {
        [`GET ${LIST}`]: byStatus([[REQUESTED], []], [[], [{ ...REQUESTED, status: "active" }]]),
        [`POST ${LIST}7/confirm/`]: { status: 200, body: { ...REQUESTED, status: "active" } },
      },
      "Team requests",
      ADMIN_ME,
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Confirm Red Lions" }));

    expect(await screen.findByText("No Team requests waiting.")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Teams" })).getByText("Red Lions")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST").map((c) => c.path)).toEqual([`${LIST}7/confirm/`]);
  });

  it("declines a Team request with a reason", async () => {
    const { calls } = await openAs(
      "/clubs/1/teams",
      {
        [`GET ${LIST}`]: byStatus([[REQUESTED], []], [[]]),
        [`POST ${LIST}7/decline/`]: { status: 200, body: { ...REQUESTED, status: "declined" } },
      },
      "Team requests",
      ADMIN_ME,
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Decline Red Lions" }));
    const form = screen.getByRole("form", { name: "Decline Red Lions" });
    await user.type(within(form).getByLabelText("Reason (optional)"), "Division 2 is full this Season.");
    await user.click(within(form).getByRole("button", { name: "Decline Red Lions" }));

    expect(await screen.findByText("No Team requests waiting.")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ reason: "Division 2 is full this Season." });
  });

  it("shows why the API refused to confirm", async () => {
    await openAs(
      "/clubs/1/teams",
      {
        [`GET ${LIST}`]: byStatus([[REQUESTED]], [[]]),
        [`POST ${LIST}7/confirm/`]: { status: 409, body: { detail: "This Division is full this Season." } },
      },
      "Team requests",
      ADMIN_ME,
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Confirm Red Lions" }));

    expect(await screen.findByText("This Division is full this Season.")).toBeInTheDocument();
  });

  it("tells someone who isn't the club's Admin", async () => {
    await openAs(
      "/clubs/1/teams",
      { [`GET ${LIST}`]: { status: 403, body: { detail: "You do not have permission to perform this action." } } },
      "Team requests",
    );

    expect((await screen.findAllByText("Only this club's Admins can see its Teams.")).length).toBeGreaterThan(0);
  });
});
