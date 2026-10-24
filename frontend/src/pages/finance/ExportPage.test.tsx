import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as platform from "../../native/platform";
import { json } from "../../test/fakeApi";
import { openAs } from "../teams/testing";
import { thisMonthSoFar } from "./ExportPage";
import { ADMIN } from "./testing";

const PAGE = "/clubs/1/finances/export";
const EXPORT = "GET /api/v1/clubs/1/finance/export/";
const TITLE = "Export for accountant";

function stubDownload() {
  const createObjectURL = vi.fn((_blob: Blob) => "blob:ledger");
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() }));
  const names: string[] = [];
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    names.push(this.download);
  });
  return { createObjectURL, names };
}

async function pick(label: string, value: string) {
  const field = screen.getByLabelText(label);
  await userEvent.clear(field);
  if (value) await userEvent.type(field, value);
}

describe("ExportPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("starts on the South African month so far", () => {
    // 22:30 UTC on 31 Oct is already 1 Nov in South Africa.
    expect(thisMonthSoFar(new Date("2026-10-31T22:30:00Z"))).toEqual({ starts_on: "2026-11-01", ends_on: "2026-11-01" });
    expect(thisMonthSoFar(new Date("2026-10-24T08:00:00Z"))).toEqual({ starts_on: "2026-10-01", ends_on: "2026-10-24" });
  });

  it("downloads the period as Excel or CSV", async () => {
    const { createObjectURL, names } = stubDownload();
    const queries: URLSearchParams[] = [];
    await openAs(
      PAGE,
      {
        [EXPORT]: (request: Request) => {
          queries.push(new URL(request.url).searchParams);
          return new Response("Entry,Date", { status: 200, headers: { "Content-Type": "text/csv" } });
        },
      },
      TITLE,
      ADMIN,
    );
    expect(screen.getByRole("link", { name: "Finances" })).toHaveAttribute("href", "/clubs/1/finances");

    await pick("From", "2026-09-01");
    await pick("To", "2026-09-30");
    await userEvent.click(screen.getByRole("button", { name: "Download Excel" }));

    expect(await screen.findByText("Excel file downloaded")).toBeInTheDocument();
    expect(screen.getByText("Tue 1 Sep to Wed 30 Sep")).toBeInTheDocument();
    expect(Object.fromEntries(queries[0]!)).toEqual({ starts_on: "2026-09-01", ends_on: "2026-09-30", file_type: "xlsx" });
    expect(names).toEqual(["ledger-2026-09-01-to-2026-09-30.xlsx"]);
    expect(createObjectURL).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByRole("button", { name: "Download CSV" }));

    expect(await screen.findByText("CSV file downloaded")).toBeInTheDocument();
    expect(queries[1]!.get("file_type")).toBe("csv");
    expect(names[1]).toBe("ledger-2026-09-01-to-2026-09-30.csv");
  });

  it("shows the API's answer next to the field", async () => {
    stubDownload();
    await openAs(PAGE, { [EXPORT]: () => json(400, { ends_on: ["On or after the first day."] }) }, TITLE, ADMIN);

    await pick("From", "2026-09-30");
    await pick("To", "2026-09-01");
    await userEvent.click(screen.getByRole("button", { name: "Download CSV" }));

    expect(await screen.findByText("On or after the first day.")).toBeInTheDocument();
    expect(screen.getByLabelText("To")).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByText(/file downloaded/)).not.toBeInTheDocument();
  });

  it("asks for both days before asking the API", async () => {
    const { calls } = await openAs(PAGE, {}, TITLE, ADMIN);

    await pick("From", "");
    await userEvent.click(screen.getByRole("button", { name: "Download Excel" }));

    expect(await screen.findByText("Pick the first day.")).toBeInTheDocument();
    expect(calls.some((c) => c.path.endsWith("/finance/export/"))).toBe(false);
  });

  it("tells someone who isn't the club's Admin", async () => {
    await openAs(PAGE, { [EXPORT]: () => json(403, { detail: "Forbidden" }) }, TITLE);

    await userEvent.click(screen.getByRole("button", { name: "Download Excel" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Only this club's Admins can see its finances.");
  });

  it("asks the installed app's Admin to export from a browser", async () => {
    vi.spyOn(platform, "isNative").mockReturnValue(true);
    await openAs(PAGE, { [EXPORT]: () => new Response("x", { status: 200 }) }, TITLE, ADMIN);

    await userEvent.click(screen.getByRole("button", { name: "Download CSV" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Export from League App in a web browser.");
  });
});
