import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ADMIN, SPRING, TUESDAY_NIGHT } from "../finance/testing";
import { LIONS, openAs } from "./testing";

const ROUTES = {
  "GET /api/v1/clubs/1/seasons/": { status: 200, body: [SPRING] },
  "GET /api/v1/clubs/1/nights/": { status: 200, body: [TUESDAY_NIGHT] },
};

async function fillIn() {
  await userEvent.click(await screen.findByRole("button", { name: "Tue · Division 2" }));
  await userEvent.type(screen.getByLabelText("Team name"), "Red Lions");
  await userEvent.type(screen.getByLabelText("Captain's email"), "thandi@example.com");
}

describe("AddTeamPage", () => {
  it("adds the Team with its Captain and opens it", async () => {
    const { calls, router } = await openAs(
      "/clubs/1/teams/new",
      { ...ROUTES, "POST /api/v1/clubs/1/teams/": { status: 201, body: { ...LIONS, members: [] } } },
      "Add a Team",
      ADMIN,
    );

    expect(await screen.findByRole("button", { name: "Spring 2026" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Add Team" })).toBeDisabled();
    await fillIn();
    await userEvent.click(screen.getByRole("button", { name: "Add Team" }));

    const sent = calls.find((call) => call.method === "POST");
    expect(sent?.body).toEqual({ season: 5, division: 3, name: "Red Lions", captain_email: "thandi@example.com" });
    expect(router.state.location.pathname).toBe("/clubs/1/teams/7");
  });

  it("shows why the API refused", async () => {
    await openAs(
      "/clubs/1/teams/new",
      {
        ...ROUTES,
        "POST /api/v1/clubs/1/teams/": {
          status: 400,
          body: { captain_email: ["No Player in League App has this email."] },
        },
      },
      "Add a Team",
      ADMIN,
    );

    await fillIn();
    await userEvent.click(screen.getByRole("button", { name: "Add Team" }));

    expect(await screen.findByText("No Player in League App has this email.")).toBeInTheDocument();
  });

  it("asks for a Season and Division first", async () => {
    await openAs(
      "/clubs/1/teams/new",
      { ...ROUTES, "GET /api/v1/clubs/1/nights/": { status: 200, body: [] } },
      "Add a Team",
      ADMIN,
    );

    expect(await screen.findByText("Nothing to add a Team to yet")).toBeInTheDocument();
  });
});
