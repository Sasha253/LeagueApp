import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { openAsAdmin } from "./testing";

const DIV_1 = { id: 31, night: 11, name: "Division 1", min_players: 5, league_fee: null, effective_league_fee: "350.00" };
const DIV_2 = { id: 32, night: 11, name: "Division 2", min_players: 6, league_fee: "400.00", effective_league_fee: "400.00" };
const TUESDAY = { id: 11, weekday: 1, divisions: [DIV_1, DIV_2] };
const FRIDAY = { id: 14, weekday: 4, divisions: [] };
const NIGHTS = "/api/v1/clubs/1/nights/";
const DIVISIONS = "/api/v1/clubs/1/divisions/";

describe("NightsPage", () => {
  it("shows each Night's Divisions with their minimum and fee", async () => {
    await openAsAdmin(
      "/clubs/1/setup/nights",
      { [`GET ${NIGHTS}`]: { status: 200, body: [TUESDAY] } },
      "Nights and Divisions",
    );

    const tuesday = await screen.findByRole("region", { name: "Tuesday" });
    expect(within(tuesday).getByText("Minimum 5 players · R 350 per Team (club fee)")).toBeInTheDocument();
    expect(within(tuesday).getByText("Minimum 6 players · R 400 per Team")).toBeInTheDocument();
    // A Night with Divisions can't be deleted, so no Delete for the Night itself.
    expect(within(tuesday).getAllByRole("button", { name: "Delete" })).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Import from a spreadsheet" })).toHaveAttribute(
      "href",
      "/clubs/1/setup/nights/import",
    );
  });

  it("adds a Night on a weekday not used yet", async () => {
    const { calls } = await openAsAdmin(
      "/clubs/1/setup/nights",
      {
        [`GET ${NIGHTS}`]: [{ status: 200, body: [TUESDAY] }, { status: 200, body: [TUESDAY, FRIDAY] }],
        [`POST ${NIGHTS}`]: { status: 201, body: FRIDAY },
      },
      "Nights and Divisions",
    );

    expect(await screen.findByRole("button", { name: "Add Friday" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add Tuesday" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add Friday" }));

    expect(await screen.findByRole("region", { name: "Friday" })).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ weekday: 4 });
  });

  it("adds a Division that starts from the club's minimum and fee", async () => {
    const { calls } = await openAsAdmin(
      "/clubs/1/setup/nights",
      {
        [`GET ${NIGHTS}`]: [{ status: 200, body: [FRIDAY] }, { status: 200, body: [FRIDAY] }],
        [`POST ${DIVISIONS}`]: { status: 201, body: { ...DIV_1, night: 14 } },
      },
      "Nights and Divisions",
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Add a Division to Friday" }));
    const form = screen.getByRole("form", { name: "New Division" });
    await user.type(within(form).getByLabelText("Name"), "Division 1");
    await user.click(within(form).getByRole("button", { name: "Save" }));

    await screen.findByRole("button", { name: "Add a Division to Friday" });
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({
      night: 14,
      name: "Division 1",
      league_fee: null,
    });
  });

  it("edits a Division's minimum and fee override", async () => {
    const { calls } = await openAsAdmin(
      "/clubs/1/setup/nights",
      {
        [`GET ${NIGHTS}`]: { status: 200, body: [TUESDAY] },
        [`PATCH ${DIVISIONS}31/`]: { status: 200, body: DIV_1 },
      },
      "Nights and Divisions",
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Edit Division 1" }));
    const form = screen.getByRole("form", { name: "Edit Division 1" });
    const minimum = within(form).getByLabelText("Minimum players");
    await user.clear(minimum);
    await user.type(minimum, "7");
    await user.type(within(form).getByLabelText("League fee per Team (R)"), "450");
    await user.click(within(form).getByRole("button", { name: "Save" }));

    await screen.findByRole("button", { name: "Edit Division 1" });
    expect(calls.find((c) => c.method === "PATCH")!.body).toEqual({
      night: 11,
      name: "Division 1",
      min_players: 7,
      league_fee: "450",
    });
  });

  it("shows why a delete was refused", async () => {
    await openAsAdmin(
      "/clubs/1/setup/nights",
      {
        [`GET ${NIGHTS}`]: { status: 200, body: [TUESDAY] },
        [`DELETE ${DIVISIONS}31/`]: { status: 409, body: { detail: "This is still in use, so it can't be deleted." } },
      },
      "Nights and Divisions",
    );
    const user = userEvent.setup();

    await user.click((await screen.findAllByRole("button", { name: "Delete" }))[0]!);
    await user.click(screen.getByRole("button", { name: "Delete Division 1" }));

    expect(await screen.findByText("This is still in use, so it can't be deleted.")).toBeInTheDocument();
  });
});
