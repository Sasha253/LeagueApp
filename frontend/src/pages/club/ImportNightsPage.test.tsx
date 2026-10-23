import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as platform from "../../native/platform";
import { openAsAdmin } from "./testing";

const IMPORTS = "/api/v1/clubs/1/imports/nights-divisions";
const PAGE = "/clubs/1/setup/nights/import";
const TITLE = "Import Nights and Divisions";
const FILE = () => new File(["Night,Division\nTuesday,Division 1\n"], "nights.csv", { type: "text/csv" });

const ROW = {
  row: 2,
  night: 1,
  division: "Division 1",
  min_players: 6,
  league_fee: "350.00",
  action: "create",
  new_night: true,
  changes: [],
  errors: [],
};
const SUMMARY = { rows: 2, nights_created: 1, divisions_created: 1, divisions_updated: 0, unchanged: 1, errors: 0 };
const PREVIEW = {
  committed: false,
  summary: SUMMARY,
  rows: [ROW, { ...ROW, row: 3, division: "Division 2", min_players: 5, league_fee: null, action: "unchanged", new_night: false }],
};
const WITH_ERRORS = {
  committed: false,
  summary: { ...SUMMARY, divisions_created: 0, unchanged: 0, errors: 1 },
  rows: [{ ...ROW, night: null, action: "error", new_night: false, errors: ['Night "Someday" isn\'t a weekday.'] }],
};

async function choose() {
  await userEvent.upload(screen.getByLabelText("Choose a spreadsheet"), FILE());
}

afterEach(() => vi.restoreAllMocks());

describe("ImportNightsPage", () => {
  it("previews the file, imports it on confirm and links back to Nights", async () => {
    // jsdom's File loses its name on the way through fetch, so check what goes in the form.
    const append = vi.spyOn(FormData.prototype, "append");
    const { calls } = await openAsAdmin(
      PAGE,
      {
        [`POST ${IMPORTS}/preview/`]: { status: 200, body: PREVIEW },
        [`POST ${IMPORTS}/commit/`]: { status: 200, body: { ...PREVIEW, committed: true } },
      },
      TITLE,
    );

    await choose();

    expect(await screen.findByText("1 new Division, 1 unchanged, 1 new Night")).toBeInTheDocument();
    const rows = within(screen.getByRole("list", { name: "Rows" })).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Tuesday · Division 1");
    expect(rows[0]).toHaveTextContent("Row 2 · Minimum 6 players · R 350 per Team · new Night");
    expect(rows[0]).toHaveTextContent("Status: New");
    expect(rows[1]).toHaveTextContent("Minimum 5 players · club fee");
    expect(rows[1]).toHaveTextContent("Status: No change");

    await userEvent.click(screen.getByRole("button", { name: "Import 1 Division" }));

    expect(await screen.findByText("Imported")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See Nights and Divisions" })).toHaveAttribute(
      "href",
      "/clubs/1/setup/nights",
    );
    const sent = calls.filter((c) => c.method === "POST");
    expect(sent.map((c) => c.path)).toEqual([`${IMPORTS}/preview/`, `${IMPORTS}/commit/`]);
    expect(sent.every((c) => Object.keys(c.body as object).join() === "file")).toBe(true);
    expect(append).toHaveBeenCalledTimes(2);
    expect(append).toHaveBeenLastCalledWith("file", expect.any(File), "nights.csv");
  });

  it("shows row errors and offers no import until the file is fixed", async () => {
    await openAsAdmin(PAGE, { [`POST ${IMPORTS}/preview/`]: { status: 200, body: WITH_ERRORS } }, TITLE);

    await choose();

    expect(await screen.findByText("1 row has errors")).toBeInTheDocument();
    expect(screen.getByText('Night "Someday" isn\'t a weekday.')).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Import/ })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Choose another file" }));
    expect(screen.getByLabelText("Choose a spreadsheet")).toBeInTheDocument();
  });

  it("shows the rows again when the commit finds errors", async () => {
    await openAsAdmin(
      PAGE,
      {
        [`POST ${IMPORTS}/preview/`]: { status: 200, body: PREVIEW },
        [`POST ${IMPORTS}/commit/`]: { status: 400, body: WITH_ERRORS },
      },
      TITLE,
    );

    await choose();
    await userEvent.click(await screen.findByRole("button", { name: "Import 1 Division" }));

    expect(await screen.findByText("1 row has errors")).toBeInTheDocument();
    expect(screen.queryByText("Imported")).not.toBeInTheDocument();
  });

  it("says why a file can't be used", async () => {
    await openAsAdmin(
      PAGE,
      { [`POST ${IMPORTS}/preview/`]: { status: 400, body: { file: ["Upload an .xlsx or .csv file."] } } },
      TITLE,
    );

    await choose();

    expect(await screen.findByRole("alert")).toHaveTextContent("Upload an .xlsx or .csv file.");
    expect(screen.getByLabelText("Choose a spreadsheet")).toBeInTheDocument();
  });

  it("downloads the template in the browser", async () => {
    const createObjectURL = vi.fn(() => "blob:template");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const { calls } = await openAsAdmin(
      PAGE,
      {
        [`GET ${IMPORTS}/template/`]: () =>
          new Response("Night,Division", { status: 200, headers: { "Content-Type": "text/csv" } }),
      },
      TITLE,
    );

    await userEvent.click(screen.getByRole("button", { name: "CSV template" }));

    await vi.waitFor(() => expect(click).toHaveBeenCalled());
    expect(createObjectURL).toHaveBeenCalled();
    expect(calls.find((c) => c.method === "GET" && c.path.endsWith("/template/"))).toBeTruthy();
  });

  it("asks the installed app's Admin to download the template in a browser", async () => {
    vi.spyOn(platform, "isNative").mockReturnValue(true);
    await openAsAdmin(
      PAGE,
      { [`GET ${IMPORTS}/template/`]: () => new Response("x", { status: 200 }) },
      TITLE,
    );

    await userEvent.click(screen.getByRole("button", { name: "Excel template" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Download the template from League App in a web browser.");
  });
});
