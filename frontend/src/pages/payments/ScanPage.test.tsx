import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ME } from "../../test/fakeApi";
import { openAs } from "../teams/testing";

const scanner = vi.hoisted(() => ({ canScan: vi.fn(() => false), scanBarcode: vi.fn() }));
vi.mock("../../native/scanner", () => scanner);

const SCANS = "POST /api/v1/clubs/1/scans/";
const REFEREE = { ...ME, club_roles: [{ club_id: 1, club_name: "Club A", role: "referee" as const }] };

function today(time: string): string {
  const date = new Date().toLocaleDateString("en-CA", { timeZone: "Africa/Johannesburg" });
  return `${date}T${time}:00+02:00`;
}

function result(overrides: object = {}) {
  return {
    id: 1,
    paid: true,
    state: "valid",
    reason: "",
    scanned_at: today("19:21"),
    code: "RK27104419",
    display_code: "RK 2710 4419",
    team: { id: 7, name: "Red Lions" },
    holder: "Red Lions",
    fixture: {
      id: 3,
      kick_off: today("19:40"),
      home_team: { id: 7, name: "Red Lions" },
      away_team: { id: 8, name: "Old Boys" },
      pitch: { id: 2, name: "Pitch 3" },
    },
    mode: "match",
    valid_until: "2026-10-27",
    paid_amount: "350.00",
    paid_methods: ["card"],
    ...overrides,
  };
}

const NOT_PAID = result({
  paid: false,
  state: "used",
  reason: "Already scanned at 19:21 by Rita. A Barcode lets its Team in once per match.",
  paid_amount: null,
  paid_methods: [],
});

beforeEach(() => {
  scanner.canScan.mockReturnValue(false);
  scanner.scanBarcode.mockReset();
});

describe("ScanPage in a browser", () => {
  it("offers typing the code and shows a large Paid with the Team and match", async () => {
    const { calls } = await openAs("/clubs/1/scan", { [SCANS]: { status: 201, body: result() } }, "Scan", REFEREE);

    expect(screen.queryByRole("button", { name: "Open camera" })).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Barcode code"), "rk 2710 4419");
    await userEvent.click(screen.getByRole("button", { name: "Check code" }));

    const card = await screen.findByRole("region", { name: "Scan result" });
    expect(within(card).getByRole("status")).toHaveTextContent("Paid");
    expect(within(card).getByText("Red Lions")).toBeInTheDocument();
    expect(within(card).getByText("vs Old Boys · 19:40 · Pitch 3")).toBeInTheDocument();
    expect(within(card).getByText("RK 2710 4419")).toBeInTheDocument();
    expect(within(card).getByText("This match only")).toBeInTheDocument();
    expect(within(card).getByText("R 350 · card")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ code: "rk 2710 4419", method: "manual" });
    expect(scanner.scanBarcode).not.toHaveBeenCalled();
  });

  it("shows Not paid with the reason and what to do next", async () => {
    await openAs("/clubs/1/scan", { [SCANS]: { status: 201, body: NOT_PAID } }, "Scan", REFEREE);

    await userEvent.type(screen.getByLabelText("Barcode code"), "RK27104419");
    await userEvent.click(screen.getByRole("button", { name: "Check code" }));

    const card = await screen.findByRole("region", { name: "Scan result" });
    expect(within(card).getByRole("status")).toHaveTextContent("Not paid");
    expect(within(card).getByText(/Already scanned at 19:21 by Rita/)).toBeInTheDocument();
    expect(within(card).getByText("This Team has been let in already. Ask an Admin if that looks wrong.")).toBeInTheDocument();
    expect(within(card).queryByText("Paid", { selector: ".la-kv span" })).not.toBeInTheDocument();

    await userEvent.click(within(card).getByRole("button", { name: "Enter code" }));
    expect(screen.getByLabelText("Barcode code")).toHaveValue("");
  });

  it("says when no Barcode has the code", async () => {
    const unknown = result({
      paid: false,
      state: "not_found",
      reason: "No Barcode has this code.",
      code: "AB12345678",
      display_code: null,
      team: null,
      holder: null,
      fixture: null,
      mode: null,
      valid_until: null,
      paid_amount: null,
      paid_methods: [],
    });
    await openAs("/clubs/1/scan", { [SCANS]: { status: 201, body: unknown } }, "Scan", REFEREE);

    await userEvent.type(screen.getByLabelText("Barcode code"), "AB12345678");
    await userEvent.click(screen.getByRole("button", { name: "Check code" }));

    const card = await screen.findByRole("region", { name: "Scan result" });
    expect(within(card).getByText("Unknown Barcode")).toBeInTheDocument();
    expect(within(card).getByText("No Barcode has this code.")).toBeInTheDocument();
    expect(within(card).getByText("AB12345678")).toBeInTheDocument();
  });

  it("names a friendly's Barcode by its match", async () => {
    const friendly = result({ team: null, holder: "Friendly: Red Lions vs Old Boys" });
    await openAs("/clubs/1/scan", { [SCANS]: { status: 201, body: friendly } }, "Scan", REFEREE);

    await userEvent.type(screen.getByLabelText("Barcode code"), "RK27104419");
    await userEvent.click(screen.getByRole("button", { name: "Check code" }));
    const card = await screen.findByRole("region", { name: "Scan result" });
    expect(within(card).getByText("Friendly: Red Lions vs Old Boys")).toBeInTheDocument();
    expect(within(card).getByText("Red Lions vs Old Boys · 19:40 · Pitch 3")).toBeInTheDocument();
  });

  it("explains a 403 to someone who isn't the club's Admin or Referee", async () => {
    await openAs("/clubs/1/scan", { [SCANS]: { status: 403, body: { detail: "No." } } }, "Scan", ME);

    await userEvent.type(screen.getByLabelText("Barcode code"), "RK27104419");
    await userEvent.click(screen.getByRole("button", { name: "Check code" }));

    expect(await screen.findByText("Only this club's Admins and Referees can scan Payment Barcodes.")).toBeInTheDocument();
  });
});

describe("ScanPage in the installed app", () => {
  beforeEach(() => {
    scanner.canScan.mockReturnValue(true);
  });

  it("opens the camera straight away and checks what it read", async () => {
    scanner.scanBarcode.mockResolvedValueOnce({ kind: "code", code: "RK27104419" });
    const { calls } = await openAs("/clubs/1/scan", { [SCANS]: { status: 201, body: result() } }, "Scan", REFEREE);

    const card = await screen.findByRole("region", { name: "Scan result" });
    expect(within(card).getByRole("status")).toHaveTextContent("Paid");
    expect(scanner.scanBarcode).toHaveBeenCalledTimes(1);
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ code: "RK27104419", method: "camera" });

    scanner.scanBarcode.mockResolvedValueOnce({ kind: "cancelled" });
    await userEvent.click(within(card).getByRole("button", { name: "Scan next" }));
    expect(scanner.scanBarcode).toHaveBeenCalledTimes(2);
    expect(await screen.findByRole("button", { name: "Open camera" })).toBeInTheDocument();
  });

  it("stays on the scanner when the camera is closed, with Enter code instead", async () => {
    scanner.scanBarcode.mockResolvedValue({ kind: "cancelled" });
    await openAs("/clubs/1/scan", {}, "Scan", REFEREE);

    expect(await screen.findByRole("button", { name: "Open camera" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Enter code instead" }));
    expect(screen.getByLabelText("Barcode code")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Scan with camera" })).toBeInTheDocument();
  });

  it("falls back to typing the code when camera access is refused", async () => {
    scanner.scanBarcode.mockResolvedValue({ kind: "denied" });
    await openAs("/clubs/1/scan", {}, "Scan", REFEREE);

    expect(
      await screen.findByText("Camera access is off for League App. Allow it in Settings, or enter the code."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Barcode code")).toBeInTheDocument();
  });
});
