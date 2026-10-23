import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ME } from "../../test/fakeApi";
import { openAs } from "../teams/testing";
import { barcode } from "./testing";

const CURRENT = "GET /api/v1/friendlies/30/barcode/";
const ZOLA = { ...ME, id: 41, name: "Zola" };

describe("FriendlyBarcodePage", () => {
  it("shows the friendly's ticket to its Captain", async () => {
    const friendly = barcode({ team: null, holder: "Friendly: Red Lions vs Old Boys" });
    await openAs(
      "/friendlies/30/barcode",
      { [CURRENT]: { status: 200, body: { state: "valid", reason: "", barcode: friendly } } },
      "Friendly Barcode",
      ZOLA,
    );

    const ticket = await screen.findByRole("region", { name: "Payment Barcode" });
    expect(within(ticket).getByText("Friendly: Red Lions vs Old Boys")).toBeInTheDocument();
    expect(within(ticket).getByText("Paid · valid for this match only")).toBeInTheDocument();
    expect(within(ticket).getByText("RK 2710 4419")).toBeInTheDocument();
  });

  it("says why there is none yet", async () => {
    await openAs(
      "/friendlies/30/barcode",
      {
        [CURRENT]: {
          status: 200,
          body: { state: "unpaid", reason: "The friendly still owes R 50.", barcode: null },
        },
      },
      "Friendly Barcode",
      ZOLA,
    );
    expect(await screen.findByText("The friendly still owes R 50.")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Payment Barcode" })).not.toBeInTheDocument();
  });
});
