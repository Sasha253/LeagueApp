import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ME } from "../../test/fakeApi";
import { ADMIN, AUTUMN, SPRING, summary } from "../finance/testing";
import { openAs } from "../teams/testing";

const SEASONS = "GET /api/v1/clubs/1/seasons/";
const SUMMARY = "GET /api/v1/clubs/1/finance/summary/";

describe("ClubHomePage", () => {
  it("shows the running Season's money beside everything the Admin can add", async () => {
    const { router } = await openAs(
      "/clubs/1",
      { [SEASONS]: { status: 200, body: [SPRING, AUTUMN] }, [SUMMARY]: { status: 200, body: summary() } },
      "Club home",
      ADMIN,
    );

    const card = await screen.findByRole("region", { name: "Finances, Spring 2026 · All Nights" });
    expect(within(card).getByText("R 28,000")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Income lines" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "All finances" })).toHaveAttribute("href", "/clubs/1/finances");

    const add = screen.getByRole("region", { name: "Add" });
    for (const [name, href] of [
      ["Team", "/clubs/1/teams/new"],
      ["Player", "/clubs/1/players/invite"],
      ["Fixture", "/clubs/1/fixtures/new"],
      ["Season", "/clubs/1/setup/seasons"],
      ["Night or Division", "/clubs/1/setup/nights"],
      ["Field", "/clubs/1/setup/fields"],
      ["Admin or Referee", "/clubs/1/setup/people"],
    ]) {
      expect(within(add).getByRole("link", { name: new RegExp(`^${name}`) })).toHaveAttribute("href", href);
    }
    expect(screen.queryByRole("list", { name: "Add a club" })).not.toBeInTheDocument();

    const run = screen.getByRole("region", { name: "Run the club" });
    await userEvent.click(within(run).getByRole("link", { name: /^Tonight/ }));
    expect(router.state.location.pathname).toBe("/clubs/1/tonight");
  });

  it("asks for a Season before it can show money", async () => {
    await openAs("/clubs/1", { [SEASONS]: { status: 200, body: [] } }, "Club home", ADMIN);

    expect(await screen.findByText("No Seasons yet. Add a Season to see its finances here.")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Add" })).toBeInTheDocument();
  });

  it("lets a superuser add a club too", async () => {
    await openAs(
      "/clubs/1",
      {
        "GET /api/v1/clubs/1/": { status: 200, body: { id: 1, name: "Club A" } },
        [SEASONS]: { status: 200, body: [] },
      },
      "Club home",
      { ...ME, is_superuser: true },
    );

    const addClub = await screen.findByRole("list", { name: "Add a club" });
    expect(within(addClub).getByRole("link", { name: /^Club/ })).toHaveAttribute("href", "/clubs/new");
    expect(screen.getByRole("link", { name: "All clubs" })).toHaveAttribute("href", "/clubs");
  });

  it("says so when the user isn't this club's Admin", async () => {
    await openAs("/clubs/1", { [SEASONS]: { status: 403, body: { detail: "No." } } }, "Club home");

    expect(await screen.findByText("Only this club's Admins can open its home.")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Add" })).not.toBeInTheDocument();
  });
});
