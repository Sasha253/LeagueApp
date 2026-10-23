import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ME } from "../../test/fakeApi";
import { openAs } from "../teams/testing";
import { summary, TEAM } from "./testing";

const ADMIN = { ...ME, id: 50, name: "Club Admin", player: null, club_roles: [{ club_id: 1, club_name: "Club A", role: "admin" as const }] };
const LIST = "GET /api/v1/clubs/1/team-payments/";
const SUMMARY = "GET /api/v1/teams/7/payments/summary/";
const CASH = "POST /api/v1/teams/7/cash-payments/";

function row(overrides: object = {}) {
  return {
    team: TEAM,
    season: { id: 5, name: "Spring 2026" },
    division: { id: 3, name: "Division 2" },
    due: "350.00",
    paid: "150.00",
    outstanding: "200.00",
    is_paid: false,
    ...overrides,
  };
}

describe("ClubPaymentsPage", () => {
  it("lists which Teams have paid", async () => {
    await openAs(
      "/clubs/1/payments",
      {
        [LIST]: {
          status: 200,
          body: [row(), row({ team: { id: 8, name: "Old Boys" }, paid: "350.00", outstanding: "0.00", is_paid: true })],
        },
      },
      "Payments",
      ADMIN,
    );

    const teams = await screen.findByRole("list", { name: "Teams" });
    const [lions, boys] = within(teams).getAllByRole("link");
    expect(lions).toHaveAttribute("href", "/clubs/1/payments/7");
    expect(within(lions!).getByText("Division 2 · Spring 2026 · R 150 of R 350")).toBeInTheDocument();
    expect(within(lions!).getByText("R 200 to go", { exact: false })).toBeInTheDocument();
    expect(within(boys!).getByText("Paid", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Club A")).toBeInTheDocument();
  });

  it("says when there are no Teams", async () => {
    await openAs("/clubs/1/payments", { [LIST]: { status: 200, body: [] } }, "Payments", ADMIN);
    expect(await screen.findByText("No active Teams yet.")).toBeInTheDocument();
  });

  it("tells a non-Admin the list is for Admins", async () => {
    await openAs("/clubs/1/payments", { [LIST]: { status: 403, body: { detail: "No." } } }, "Payments");
    expect(await screen.findByText("Only this club's Admins can see its Teams.")).toBeInTheDocument();
  });
});

describe("ClubTeamPaymentPage", () => {
  it("shows who has paid and records cash for one Player", async () => {
    const { calls } = await openAs(
      "/clubs/1/payments/7",
      {
        [SUMMARY]: [
          { status: 200, body: summary({ team_credit: null }) },
          { status: 200, body: summary({ team_credit: null, paid: "220.00", outstanding: "130.00" }) },
        ],
        [CASH]: { status: 201, body: {} },
      },
      "Red Lions",
      ADMIN,
    );
    const user = userEvent.setup();

    expect(screen.getByRole("img", { name: "R 150 of R 350 paid" })).toBeInTheDocument();
    expect(screen.queryByText("Team credit")).not.toBeInTheDocument();
    const form = screen.getByRole("form", { name: "Record cash" });
    const payers = within(form).getByRole("group", { name: "Paid by" });
    expect(within(payers).queryByRole("button", { name: "Lerato Khumalo" })).not.toBeInTheDocument();
    await user.click(within(payers).getByRole("button", { name: "Sipho Dlamini" }));
    await user.type(within(form).getByLabelText("Cash received (R)"), "70");
    await user.type(within(form).getByLabelText("Note (optional)"), "Handed to Pieter");
    await user.click(within(form).getByRole("button", { name: "Record R 70 cash" }));

    expect(await screen.findByText("R 70 cash recorded for Sipho Dlamini.")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ amount: "70", player_id: 1, reason: "Handed to Pieter" });
    expect(await screen.findByRole("img", { name: "R 220 of R 350 paid" })).toBeInTheDocument();
  });

  it("records cash for the whole Team and shows the backend's refusal", async () => {
    const { calls } = await openAs(
      "/clubs/1/payments/7",
      {
        [SUMMARY]: { status: 200, body: summary({ team_credit: null }) },
        [CASH]: { status: 409, body: { detail: "That is more than the Team still owes." } },
      },
      "Red Lions",
      ADMIN,
    );
    const user = userEvent.setup();
    const form = screen.getByRole("form", { name: "Record cash" });

    await user.click(within(form).getByRole("button", { name: "Record cash" }));
    expect(within(form).getByText("Enter an amount in rand, like 70 or 70.50.")).toBeInTheDocument();

    await user.type(within(form).getByLabelText("Cash received (R)"), "500");
    await user.click(within(form).getByRole("button", { name: "Record R 500 cash" }));

    expect(await screen.findByText("That is more than the Team still owes.")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ amount: "500", player_id: null, reason: "" });
  });

  it("has no cash to record once the Team owes nothing", async () => {
    await openAs(
      "/clubs/1/payments/7",
      { [SUMMARY]: { status: 200, body: summary({ paid: "350.00", outstanding: "0.00", is_paid: true, team_credit: null }) } },
      "Red Lions",
      ADMIN,
    );

    expect(screen.getByText("Red Lions owes nothing, so there is no cash to record.")).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Record cash" })).not.toBeInTheDocument();
  });
});
