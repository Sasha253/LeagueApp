import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ME } from "../../test/fakeApi";
import { LIONS, member, openAs } from "../teams/testing";
import { barcode } from "./testing";

const CAPTAIN = { ...ME, id: 2, name: "Thandi Mokoena", captain_of: [7] };
const CURRENT = "GET /api/v1/teams/7/barcode/";

describe("BarcodePage", () => {
  it("shows the Captain's ticket for this match, with a real barcode of the code", async () => {
    await openAs(
      "/teams/7/barcode",
      { [CURRENT]: { status: 200, body: { state: "valid", reason: "", barcode: barcode() } } },
      "Payment Barcode",
      CAPTAIN,
    );

    const ticket = await screen.findByRole("region", { name: "Payment Barcode" });
    expect(within(ticket).getByText("Tue 27 Oct · 19:40 · Pitch 3")).toBeInTheDocument();
    expect(within(ticket).getByText("Red Lions")).toBeInTheDocument();
    expect(within(ticket).getByText("Paid · valid for this match only")).toBeInTheDocument();
    expect(within(ticket).getByText("RK 2710 4419")).toBeInTheDocument();
    const bars = within(ticket).getByRole("img", { name: "Barcode RK 2710 4419" });
    // Start, 10 characters, check and Stop: 3 bars each, Stop 4.
    expect(bars.querySelectorAll("rect")).toHaveLength(12 * 3 + 4);
  });

  it("says a Season Barcode is valid until the Season's last day", async () => {
    const season = barcode({ mode: "season", fixture: null, valid_until: "2026-12-19" });
    await openAs(
      "/teams/7/barcode",
      { [CURRENT]: { status: 200, body: { state: "valid", reason: "", barcode: season } } },
      "Payment Barcode",
      CAPTAIN,
    );

    expect(await screen.findByText("Spring 2026 Season")).toBeInTheDocument();
    expect(screen.getByText("Paid · valid until Sat 19 Dec")).toBeInTheDocument();
  });

  it("explains an unpaid Team has none yet, and offers Pay my share", async () => {
    await openAs(
      "/teams/7/barcode",
      {
        [CURRENT]: {
          status: 200,
          body: { state: "unpaid", reason: "Red Lions still owes R 200.", barcode: null },
        },
      },
      "Payment Barcode",
      CAPTAIN,
    );

    expect(await screen.findByText("Red Lions still owes R 200.")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Payment Barcode" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Pay my share" })).toHaveAttribute("href", "/teams/7/pay");
  });

  it("tells the Captain to ask an Admin when it was revoked", async () => {
    await openAs(
      "/teams/7/barcode",
      {
        [CURRENT]: {
          status: 200,
          body: { state: "revoked", reason: "This Barcode was revoked: Lost phone", barcode: null },
        },
      },
      "Payment Barcode",
      CAPTAIN,
    );

    expect(await screen.findByText("This Barcode was revoked: Lost phone")).toBeInTheDocument();
    expect(screen.getByText("Ask an Admin of the club for a new one.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Pay my share" })).not.toBeInTheDocument();
  });

  it("is linked from the Team screen for the Captain only", async () => {
    const routes = {
      "GET /api/v1/teams/7/": { status: 200, body: LIONS },
      "GET /api/v1/teams/7/members/": { status: 200, body: [member()] },
      "GET /api/v1/teams/7/payments/summary/": { status: 404, body: {} },
    };
    await openAs("/teams/7", routes, "Red Lions", CAPTAIN);
    expect(await screen.findByRole("link", { name: "Payment Barcode" })).toHaveAttribute("href", "/teams/7/barcode");
  });

  it("isn't linked for a Player who isn't the Captain", async () => {
    const routes = {
      "GET /api/v1/teams/7/": { status: 200, body: LIONS },
      "GET /api/v1/teams/7/members/": {
        status: 200,
        body: [member({ player_id: 1, name: "Sipho Dlamini", is_captain: false }), member()],
      },
    };
    await openAs("/teams/7", routes, "Red Lions");
    await screen.findByRole("link", { name: "Pay my share" });
    expect(screen.queryByRole("link", { name: "Payment Barcode" })).not.toBeInTheDocument();
  });
});
