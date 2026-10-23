import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ADMIN_ME } from "../club/testing";
import { openAs } from "../teams/testing";
import { adminFixture, fallback } from "./testing";

const DETAIL = "GET /api/v1/clubs/1/fixtures/30/";
const FRIENDLY = "/api/v1/clubs/1/fixtures/30/friendly/";
const ZOLA = { id: 41, name: "Zola" };
const NOMSA = { id: 42, name: "Nomsa" };

function friendly(overrides: object = {}) {
  return {
    fixture: {
      id: 30,
      kick_off: "2026-10-27T17:40:00Z",
      home_team: { id: 7, name: "Red Lions" },
      away_team: { id: 8, name: "Old Boys" },
      pitch: { id: 3, name: "Pitch 3" },
    },
    cause: "both_teams_out",
    remaining_team: null,
    is_on: true,
    can_change: true,
    money_fixed: false,
    default_fee: "200.00",
    payer_choices: ["borrowed_players", "club"],
    terms: null,
    due: "0.00",
    paid: "0.00",
    outstanding: "0.00",
    settled: false,
    payments: [],
    payers: [],
    captain_candidates: [NOMSA, ZOLA],
    barcode: { state: "no_captain", reason: "Set the friendly's fee first.", barcode: null },
    ...overrides,
  };
}

const SET = {
  fee: "150.00",
  payer: "borrowed_players",
  captain: { id: 41, name: "Zola" },
  set_by: { id: 1, name: "Ada Admin" },
  set_at: "2026-10-27T12:00:00Z",
};

function routes(friendlyAnswer: object | object[]) {
  return {
    [DETAIL]: { status: 200, body: adminFixture({ status: "friendly", fallback: fallback({ joined: [] }) }) },
    [`GET ${FRIENDLY}`]: Array.isArray(friendlyAnswer)
      ? friendlyAnswer.map((body) => ({ status: 200, body }))
      : { status: 200, body: friendlyAnswer },
  };
}

describe("Friendly fee (ClubFixturePage)", () => {
  it("starts the fee at the club's friendly fee and saves who pays and the Captain", async () => {
    const saved = friendly({ terms: SET, due: "150.00", outstanding: "150.00", payers: [NOMSA, ZOLA] });
    const { calls } = await openAs(
      "/clubs/1/fixtures/30",
      { ...routes([friendly(), saved]), [`POST ${FRIENDLY}`]: { status: 200, body: saved } },
      "Fixture",
      ADMIN_ME,
    );

    const fee = await screen.findByLabelText("Fee for the match (R)");
    expect(fee).toHaveValue("200.00");
    expect(screen.queryByRole("button", { name: "The Team's Players" })).not.toBeInTheDocument();
    await userEvent.clear(fee);
    await userEvent.type(fee, "150");
    await userEvent.click(screen.getByRole("button", { name: "The borrowed Players" }));
    await userEvent.click(screen.getByRole("button", { name: "Zola" }));
    await userEvent.click(screen.getByRole("button", { name: "Save the friendly's fee" }));

    expect(calls.find((c) => c.method === "POST")?.body).toEqual({
      fee: "150",
      payer: "borrowed_players",
      captain: 41,
    });
    const summary = await screen.findByRole("list", { name: "Friendly fee" });
    expect(await within(summary).findByText("R 150 · The borrowed Players")).toBeInTheDocument();
    expect(within(summary).getByText("R 0 of R 150 paid · R 150 to pay")).toBeInTheDocument();
  });

  it("asks who pays before saving", async () => {
    const { calls } = await openAs("/clubs/1/fixtures/30", routes(friendly()), "Fixture", ADMIN_ME);
    await userEvent.click(await screen.findByRole("button", { name: "Save the friendly's fee" }));
    expect(await screen.findByText("Choose who pays.")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("records cash from one of the payers", async () => {
    const owing = friendly({
      terms: SET,
      due: "150.00",
      outstanding: "150.00",
      payers: [NOMSA, ZOLA],
      barcode: { state: "unpaid", reason: "The friendly still owes R 150.", barcode: null },
    });
    const { calls } = await openAs(
      "/clubs/1/fixtures/30",
      { ...routes(owing), [`POST ${FRIENDLY}payments/`]: { status: 201, body: owing } },
      "Fixture",
      ADMIN_ME,
    );

    expect(await screen.findByText("The friendly still owes R 150.")).toBeInTheDocument();
    const form = screen.getByRole("form", { name: "Record cash" });
    await userEvent.type(within(form).getByLabelText("Cash received (R)"), "100");
    await userEvent.click(within(form).getByRole("button", { name: "Nomsa" }));
    await userEvent.click(within(form).getByRole("button", { name: "Record R 100 cash" }));

    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ player: 42, amount: "100", reason: "" });
  });

  it("shows the fee as fixed once paid, and the Barcode as issued", async () => {
    const paid = friendly({
      terms: SET,
      money_fixed: true,
      due: "150.00",
      paid: "150.00",
      settled: true,
      payments: [
        {
          id: 9,
          kind: "payment",
          method: "cash",
          amount: "150.00",
          player: ZOLA,
          recorded_by: { id: 1, name: "Ada Admin" },
          reason: "",
          created_at: "2026-10-27T13:00:00Z",
        },
      ],
      payers: [NOMSA, ZOLA],
      barcode: { state: "valid", reason: "", barcode: null },
    });
    await openAs("/clubs/1/fixtures/30", routes(paid), "Fixture", ADMIN_ME);

    expect(await screen.findByLabelText("Fee for the match (R)")).toBeDisabled();
    expect(screen.getByText("Payments have been recorded, so the fee and who pays are fixed.")).toBeInTheDocument();
    expect(screen.getByText("Zola shows it at the gate.")).toBeInTheDocument();
    const payments = screen.getByRole("list", { name: "Friendly payments" });
    expect(within(payments).getByText("Zola · R 150")).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Record cash" })).not.toBeInTheDocument();
  });

  it("isn't shown for a match that didn't become a friendly", async () => {
    const { calls } = await openAs(
      "/clubs/1/fixtures/30",
      { [DETAIL]: { status: 200, body: adminFixture() } },
      "Fixture",
      ADMIN_ME,
    );
    await screen.findByRole("list", { name: "History" });
    expect(screen.queryByRole("heading", { name: "Friendly fee" })).not.toBeInTheDocument();
    expect(calls.some((c) => c.path.endsWith("/friendly/"))).toBe(false);
  });
});
