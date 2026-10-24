import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { openAs } from "../teams/testing";
import { ADMIN, ledger } from "./testing";

const LEDGER = "GET /api/v1/clubs/1/finance/teams/7/";

describe("TeamLedgerPage", () => {
  it("shows the Team's payments and every entry newest first", async () => {
    await openAs("/clubs/1/finances/teams/7", { [LEDGER]: { status: 200, body: ledger() } }, "Red Lions", ADMIN);

    expect(screen.getByText("Club A · Spring 2026 · Tuesday · Division 2")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Finances" })).toHaveAttribute("href", "/clubs/1/finances");
    expect(screen.getByRole("img", { name: "R 150 of R 350 paid" })).toBeInTheDocument();
    expect(screen.getByText("R 200 to go", { exact: false })).toBeInTheDocument();
    const method = screen.getByRole("region", { name: "Paid by method" });
    expect(within(method).getByText("R 70")).toBeInTheDocument();
    expect(within(method).getByText("R 50")).toBeInTheDocument();
    expect(within(method).getByText("R 30")).toBeInTheDocument();

    const entries = within(screen.getByRole("list", { name: "Ledger entries" })).getAllByRole("listitem");
    expect(entries.map((row) => row.getAttribute("aria-label"))).toEqual([
      "Entry 14",
      "Entry 13",
      "Entry 11",
      "Entry 12",
      "Entry 10",
    ]);
    const [correction, cash, card, credit, charge] = entries;
    expect(within(correction!).getByText("Correction of entry 13")).toBeInTheDocument();
    expect(within(correction!).getByText("Typed R 20 too much")).toBeInTheDocument();
    expect(within(correction!).getByText("Entry 14 · Recorded by Ada Admin")).toBeInTheDocument();
    expect(within(correction!).getByText("Thu 22 Oct · 10:00")).toBeInTheDocument();
    expect(within(cash!).getByText("Payment")).toBeInTheDocument();
    expect(within(cash!).getByText("Cash")).toBeInTheDocument();
    expect(within(card!).getByText("Payment · Sipho Dlamini")).toBeInTheDocument();
    expect(within(card!).getByText("Card")).toBeInTheDocument();
    expect(within(card!).getByText("R 70")).toBeInTheDocument();
    expect(within(card!).getByText("Entry 11 · Recorded by the app")).toBeInTheDocument();
    expect(within(credit!).getByText("Credit")).toBeInTheDocument();
    expect(within(charge!).getByText("Fee charged")).toBeInTheDocument();
    expect(within(charge!).getByText("R 350")).toBeInTheDocument();
    expect(within(charge!).queryByText("Method:", { exact: false })).not.toBeInTheDocument();
    // Read-only: nothing to edit or delete.
    expect(screen.queryByRole("button", { name: /edit|delete/i })).not.toBeInTheDocument();
  });

  it("says when a Team has paid more than it owes", async () => {
    await openAs(
      "/clubs/1/finances/teams/7",
      { [LEDGER]: { status: 200, body: ledger({ paid: "420.00", outstanding: "-70.00", is_paid: true }) } },
      "Red Lions",
      ADMIN,
    );
    expect(screen.getByText("Red Lions has paid R 70 more than it owes.")).toBeInTheDocument();
    expect(screen.getByText("Paid", { exact: false, selector: ".la-chip" })).toBeInTheDocument();
  });

  it("says when nothing is on the account", async () => {
    await openAs("/clubs/1/finances/teams/7", { [LEDGER]: { status: 200, body: ledger({ entries: [] }) } }, "Red Lions", ADMIN);
    expect(screen.getByText("Nothing on this Team's account yet.")).toBeInTheDocument();
  });

  it("tells a non-Admin the ledger is for Admins", async () => {
    await openAs("/clubs/1/finances/teams/7", { [LEDGER]: { status: 403, body: { detail: "No." } } }, "Team ledger");
    expect(await screen.findByText("Only this club's Admins can see its finances.")).toBeInTheDocument();
  });
});
