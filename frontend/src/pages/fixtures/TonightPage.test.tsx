import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ADMIN_ME } from "../club/testing";
import { openAs } from "../teams/testing";
import { adminFixture } from "./testing";

const TONIGHT = "/api/v1/clubs/1/tonight/";
const DECIDE = "/api/v1/clubs/1/readiness/12/decide/";

function team(id: number, name: string, overrides: object = {}) {
  return {
    team: { id, name },
    confirmed: 5,
    min_players: 5,
    below_minimum: false,
    due: "350.00",
    paid: "350.00",
    outstanding: "0.00",
    unpaid: false,
    readiness: null,
    ...overrides,
  };
}

function readiness(overrides: object = {}) {
  return {
    id: 12,
    outcome: "pending",
    reason: "unpaid",
    checked_at: "2026-10-27T11:40:00Z",
    confirmed: 6,
    min_players: 5,
    outstanding: "140.00",
    decided_by_name: null,
    decided_at: null,
    note: "",
    ...overrides,
  };
}

/** Red Lions (paid) vs Old Boys, who owe R 140 and wait for the Admin at T-6h. */
function atRisk(overrides: object = {}) {
  return {
    fixture: adminFixture({ status: "confirming" }),
    checked: true,
    waiting: true,
    at_risk: true,
    teams: [
      team(7, "Red Lions", { readiness: readiness({ id: 11, outcome: "playing", reason: "", outstanding: "0.00" }) }),
      team(8, "Old Boys", { confirmed: 6, paid: "210.00", outstanding: "140.00", unpaid: true, readiness: readiness() }),
    ],
    ...overrides,
  };
}

function ready() {
  return {
    fixture: adminFixture({
      id: 31,
      status: "ready",
      kick_off: "2026-10-27T16:20:00Z",
      pitch: { id: 10, name: "Pitch 1" },
      home_team: { id: 1, name: "Sharks" },
      away_team: { id: 2, name: "Gunners" },
    }),
    checked: true,
    waiting: false,
    at_risk: false,
    teams: [team(1, "Sharks"), team(2, "Gunners")],
  };
}

async function open(routes: object) {
  return openAs("/clubs/1/tonight", routes as never, "Tonight", ADMIN_ME);
}

describe("TonightPage", () => {
  it("puts the match at risk on top and the rest by pitch and time", async () => {
    await open({ [`GET ${TONIGHT}`]: { status: 200, body: [ready(), atRisk()] } });

    const card = await screen.findByRole("article", { name: "Red Lions vs Old Boys" });
    expect(within(card).getByText("At risk")).toBeInTheDocument();
    expect(card).toHaveTextContent("19:40");
    expect(card).toHaveTextContent("6 of 5 · R 210 of R 350");
    expect(card).toHaveTextContent("Old Boys still owes R 140 at the T-6h check. You decide if they play.");
    expect(screen.getByRole("heading", { name: "At risk · 1" })).toBeInTheDocument();

    const rows = within(screen.getByRole("list", { name: "By pitch and time" })).getAllByRole("listitem");
    expect(rows).toHaveLength(1);
    expect(rows[0]).toHaveTextContent("18:20");
    expect(rows[0]).toHaveTextContent("Sharks vs Gunners");
    expect(rows[0]).toHaveTextContent("Pitch 1 · Division 2 · both paid");
    expect(rows[0]).toHaveTextContent("Ready");
  });

  it("lets an unpaid Team play", async () => {
    const decided = atRisk({
      fixture: adminFixture({ status: "ready" }),
      waiting: false,
      at_risk: false,
    });
    const { calls } = await open({
      [`GET ${TONIGHT}`]: [
        { status: 200, body: [atRisk()] },
        { status: 200, body: [decided] },
      ],
      [`POST ${DECIDE}`]: { status: 200, body: decided },
    });

    await userEvent.click(await screen.findByRole("button", { name: "Let Old Boys play" }));

    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ decision: "play" });
    const rows = within(await screen.findByRole("list", { name: "By pitch and time" })).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Red Lions vs Old Boys");
    expect(screen.queryByRole("button", { name: "Let Old Boys play" })).not.toBeInTheDocument();
  });

  it("asks once more before ruling a Team out", async () => {
    const { calls } = await open({
      [`GET ${TONIGHT}`]: { status: 200, body: [atRisk()] },
      [`POST ${DECIDE}`]: { status: 200, body: atRisk() },
    });

    await userEvent.click(await screen.findByRole("button", { name: "Rule Old Boys out" }));
    expect(calls.some((c) => c.method === "POST")).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: "Rule out" }));

    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ decision: "out" });
  });

  it("shows why a ruling was refused", async () => {
    await open({
      [`GET ${TONIGHT}`]: { status: 200, body: [atRisk()] },
      [`POST ${DECIDE}`]: { status: 409, body: { detail: "Old Boys has already been ruled playing." } },
    });

    await userEvent.click(await screen.findByRole("button", { name: "Let Old Boys play" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("already been ruled playing");
  });

  it("explains a Team that is out or still short before the check", async () => {
    const out = atRisk({
      fixture: adminFixture({ id: 32, status: "one_team_out" }),
      waiting: false,
      at_risk: false,
    });
    const before = {
      ...atRisk({ checked: false, waiting: false }),
      teams: [
        team(7, "Red Lions", { confirmed: 3, below_minimum: true }),
        team(8, "Old Boys", { paid: "0.00", outstanding: "350.00", unpaid: true }),
      ],
    };
    await open({ [`GET ${TONIGHT}`]: { status: 200, body: [before, out] } });

    const card = await screen.findByRole("article", { name: "Red Lions vs Old Boys" });
    expect(card).toHaveTextContent("Short 2");
    expect(card).toHaveTextContent("Red Lions needs 2 more by T-6h or they're out.");
    expect(card).toHaveTextContent("Old Boys still owes R 350.");
    expect(within(card).queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByRole("list", { name: "By pitch and time" })).toHaveTextContent("One team out");
  });

  it("says when there are no matches tonight", async () => {
    await open({ [`GET ${TONIGHT}`]: { status: 200, body: [] } });
    expect(await screen.findByText("No matches tonight.")).toBeInTheDocument();
  });

  it("tells someone who isn't an Admin of the club", async () => {
    await open({ [`GET ${TONIGHT}`]: { status: 403, body: { detail: "No." } } });
    expect(await screen.findByText("Only this club's Admins can see its Fixtures.")).toBeInTheDocument();
  });
});
