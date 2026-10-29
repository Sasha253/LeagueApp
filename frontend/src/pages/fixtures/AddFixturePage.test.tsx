import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { json } from "../../test/fakeApi";
import { ADMIN, SPRING, TUESDAY_NIGHT } from "../finance/testing";
import { LIONS, OLD_BOYS, openAs } from "../teams/testing";

const PITCH = { id: 11, name: "Pitch 3", referee: null, referee_name: null };

function routes(post: { status: number; body: unknown }) {
  return {
    "GET /api/v1/clubs/1/seasons/": { status: 200, body: [SPRING] },
    "GET /api/v1/clubs/1/nights/": { status: 200, body: [TUESDAY_NIGHT] },
    "GET /api/v1/clubs/1/fields/": { status: 200, body: [PITCH] },
    "GET /api/v1/clubs/1/teams/": (request: Request) => {
      const query = new URL(request.url).searchParams;
      const inDivision = query.get("status") === "active" && query.get("season") === "5" && query.get("division") === "3";
      return json(200, inDivision ? [LIONS, { ...OLD_BOYS, division: LIONS.division }] : []);
    },
    "POST /api/v1/clubs/1/fixtures/": post,
  };
}

async function fillIn() {
  await userEvent.click(await screen.findByRole("button", { name: "Division: Tue · Division 2" }));
  await userEvent.click(await screen.findByRole("button", { name: "Home: Red Lions" }));
  expect(screen.queryByRole("button", { name: "Away: Red Lions" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Away: Old Boys" }));
  await userEvent.click(screen.getByRole("button", { name: "Pitch: Pitch 3" }));
  fireEvent.change(screen.getByLabelText("Date"), { target: { value: "2026-11-03" } });
  fireEvent.change(screen.getByLabelText("Kick-off"), { target: { value: "19:40" } });
}

describe("AddFixturePage", () => {
  it("adds the Fixture at a South African kick-off and opens it", async () => {
    const { calls, router } = await openAs(
      "/clubs/1/fixtures/new",
      routes({ status: 201, body: { id: 90 } }),
      "Add a Fixture",
      ADMIN,
    );

    await fillIn();
    await userEvent.click(screen.getByRole("button", { name: "Friendly-eligible" }));
    await userEvent.click(screen.getByRole("button", { name: "Add Fixture" }));

    expect(calls.find((call) => call.method === "POST")?.body).toEqual({
      season: 5,
      division: 3,
      pitch: 11,
      home_team: 7,
      away_team: 8,
      kick_off: "2026-11-03T19:40:00+02:00",
      friendly_eligible: true,
    });
    expect(router.state.location.pathname).toBe("/clubs/1/fixtures/90");
  });

  it("shows the import's reasons when the API refuses", async () => {
    await openAs(
      "/clubs/1/fixtures/new",
      routes({ status: 400, body: { non_field_errors: ["Pitch 3 already has Red Lions vs Others at this kick-off."] } }),
      "Add a Fixture",
      ADMIN,
    );

    await fillIn();
    await userEvent.click(screen.getByRole("button", { name: "Add Fixture" }));

    expect(await screen.findByText("Pitch 3 already has Red Lions vs Others at this kick-off.")).toBeInTheDocument();
  });
});
