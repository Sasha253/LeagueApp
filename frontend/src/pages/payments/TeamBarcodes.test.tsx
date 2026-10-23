import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ME } from "../../test/fakeApi";
import { openAs } from "../teams/testing";
import { adminBarcode, summary } from "./testing";

const ADMIN = { ...ME, id: 50, name: "Club Admin", player: null, club_roles: [{ club_id: 1, club_name: "Club A", role: "admin" as const }] };
const SUMMARY = "GET /api/v1/teams/7/payments/summary/";
const LIST = "GET /api/v1/teams/7/barcodes/";
const ISSUE = "POST /api/v1/teams/7/barcodes/";
const PAID = { status: 200, body: summary({ team_credit: null, paid: "350.00", outstanding: "0.00", is_paid: true }) };

const revoked = adminBarcode({
  id: 30,
  code: "AB12CD34EF",
  display_code: "AB 12CD 34EF",
  state: "revoked",
  reason: "This Barcode was revoked: Lost phone",
  revoked_at: "2026-10-23T18:00:00Z",
  revoke_reason: "Lost phone",
  issued_by: { id: 50, name: "Club Admin" },
  scans: 1,
});

describe("Team Payment Barcodes (Admin)", () => {
  it("lists each Barcode with its state, what it is for and how often it was scanned", async () => {
    await openAs(
      "/clubs/1/payments/7",
      { [SUMMARY]: PAID, [LIST]: { status: 200, body: [adminBarcode(), revoked] } },
      "Red Lions",
      ADMIN,
    );

    const list = await screen.findByRole("list", { name: "Payment Barcodes" });
    const [valid, old] = within(list).getAllByRole("listitem");
    expect(within(valid!).getByText("RK 2710 4419")).toBeInTheDocument();
    expect(within(valid!).getByText("Valid")).toBeInTheDocument();
    expect(within(valid!).getByText("Match Tue 27 Oct · 19:40")).toBeInTheDocument();
    expect(within(valid!).getByText("Issued Fri 23 Oct · 19:00 on payment · scanned 0 times")).toBeInTheDocument();
    expect(within(old!).getByText("Revoked")).toBeInTheDocument();
    expect(within(old!).getByText("This Barcode was revoked: Lost phone")).toBeInTheDocument();
    expect(within(old!).getByText("Issued Fri 23 Oct · 19:00 by Club Admin · scanned 1 time")).toBeInTheDocument();
    expect(within(old!).queryByRole("button", { name: "Revoke" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reissue Payment Barcode" })).toBeInTheDocument();
  });

  it("issues one and shows the backend's refusal", async () => {
    const { calls } = await openAs(
      "/clubs/1/payments/7",
      {
        [SUMMARY]: PAID,
        [LIST]: [
          { status: 200, body: [] },
          { status: 200, body: [adminBarcode({ issued_by: { id: 50, name: "Club Admin" } })] },
        ],
        [ISSUE]: [
          { status: 409, body: { detail: "This Team has no match coming up." } },
          { status: 201, body: adminBarcode() },
        ],
      },
      "Red Lions",
      ADMIN,
    );
    const user = userEvent.setup();

    expect(await screen.findByText("None yet. One is issued when Red Lions has paid.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Issue Payment Barcode" }));
    expect(await screen.findByText("This Team has no match coming up.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Issue Payment Barcode" }));
    expect(await screen.findByText("New Payment Barcode sent to the Captain of Red Lions.")).toBeInTheDocument();
    expect(await screen.findByText("RK 2710 4419")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST" && c.path === "/api/v1/teams/7/barcodes/")).toHaveLength(2);
  });

  it("revokes one with a reason", async () => {
    const { calls } = await openAs(
      "/clubs/1/payments/7",
      {
        [SUMMARY]: PAID,
        [LIST]: [
          { status: 200, body: [adminBarcode()] },
          { status: 200, body: [adminBarcode({ state: "revoked", revoked_at: "2026-10-23T18:00:00Z", reason: "This Barcode was revoked: Lost phone" })] },
        ],
        "POST /api/v1/barcodes/31/revoke/": { status: 200, body: {} },
      },
      "Red Lions",
      ADMIN,
    );
    const user = userEvent.setup();

    const list = await screen.findByRole("list", { name: "Payment Barcodes" });
    await user.click(within(list).getByRole("button", { name: "Revoke" }));
    await user.click(within(list).getByRole("button", { name: "Revoke" }));
    expect(screen.getByText("Say why it no longer counts.")).toBeInTheDocument();
    expect(calls.some((c) => c.path.endsWith("/revoke/"))).toBe(false);

    await user.type(screen.getByLabelText("Why revoke it?"), "Lost phone");
    await user.click(within(list).getByRole("button", { name: "Revoke" }));
    expect(await screen.findByText("This Barcode was revoked: Lost phone")).toBeInTheDocument();
    expect(calls.find((c) => c.path === "/api/v1/barcodes/31/revoke/")?.body).toEqual({ reason: "Lost phone" });
    expect(screen.getByRole("button", { name: "Issue Payment Barcode" })).toBeInTheDocument();
  });
});
