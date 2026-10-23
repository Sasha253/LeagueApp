import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ME } from "../../test/fakeApi";
import { LIONS, member, openAs } from "../teams/testing";
import { summary } from "./testing";

const ROUTES = {
  "GET /api/v1/teams/7/": { status: 200, body: LIONS },
  "GET /api/v1/teams/7/members/": {
    status: 200,
    body: [member({ player_id: 1, name: "Sipho Dlamini", is_captain: false }), member()],
  },
};

describe("Team payments", () => {
  it("lets a Player in the Team pay their share, without showing who has paid", async () => {
    const { calls } = await openAs("/teams/7", ROUTES, "Red Lions");

    const payments = await screen.findByRole("region", { name: "Payments" });
    expect(within(payments).getByRole("link", { name: "Pay my share" })).toHaveAttribute("href", "/teams/7/pay");
    expect(calls.some((c) => c.path.endsWith("/payments/summary/"))).toBe(false);
  });

  it("shows the Captain who has paid, the Team total against what is due, and Team credit", async () => {
    await openAs(
      "/teams/7",
      { ...ROUTES, "GET /api/v1/teams/7/payments/summary/": { status: 200, body: summary() } },
      "Red Lions",
      { ...ME, id: 2, name: "Thandi Mokoena", captain_of: [7] },
    );

    const progress = await screen.findByRole("region", { name: "Team payments" });
    expect(within(progress).getByRole("img", { name: "R 150 of R 350 paid" })).toBeInTheDocument();
    expect(within(progress).getByText("R 200 to go", { exact: false })).toBeInTheDocument();
    const who = within(progress).getByRole("list", { name: "Who has paid" });
    const rows = within(who).getAllByRole("listitem");
    expect(rows.map((row) => row.textContent)).toEqual([
      "Sipho DlaminiStatus: R 100",
      "Thandi Mokoena CaptainStatus: Unpaid",
      "Lerato Khumalo Left the TeamStatus: R 20",
      "For the whole TeamStatus: R 30",
    ]);
    expect(screen.getByText("Team credit")).toBeInTheDocument();
    expect(screen.getByText("R 40")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Pay my share" })).toBeInTheDocument();
  });
});
