import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { openAsAdmin, SETTINGS } from "./testing";

const SETTINGS_PATH = "GET /api/v1/clubs/1/settings/";

describe("ClubSetupPage", () => {
  it("links to every part of club setup", async () => {
    const { router } = await openAsAdmin("/clubs/1/setup", { [SETTINGS_PATH]: { status: 200, body: SETTINGS } }, "Club setup");

    for (const name of ["Settings", "Seasons", "Nights and Divisions", "Fields", "People"]) {
      expect(await screen.findByRole("link", { name: new RegExp(`^${name}`) })).toBeInTheDocument();
    }
    expect(screen.getByText("Club A")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("link", { name: /^Fields/ }));
    expect(router.state.location.pathname).toBe("/clubs/1/setup/fields");
  });

  it("asks the Admin to set the fees that are missing", async () => {
    await openAsAdmin(
      "/clubs/1/setup",
      { [SETTINGS_PATH]: { status: 200, body: { ...SETTINGS, missing: ["league_fee"] } } },
      "Club setup",
    );

    expect(await screen.findByText("Set your fees")).toBeInTheDocument();
    expect(screen.getByText("Still to set: League fee per Team.")).toBeInTheDocument();
  });

  it("says so when the user isn't this club's Admin", async () => {
    await openAsAdmin("/clubs/1/setup", { [SETTINGS_PATH]: { status: 403, body: { detail: "No." } } }, "Club setup");

    expect(await screen.findByText("Only this club's Admins can open club setup.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^Seasons/ })).not.toBeInTheDocument();
  });
});
