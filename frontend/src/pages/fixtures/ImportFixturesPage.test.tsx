import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ADMIN_ME } from "../club/testing";
import { openAs } from "../teams/testing";

const IMPORTS = "/api/v1/clubs/1/imports/fixtures";
const PAGE = "/clubs/1/fixtures/import";
const TITLE = "Import fixtures";
const SEASONS = {
  "GET /api/v1/seasons/": {
    status: 200,
    body: [{ id: 5, club: { id: 1, name: "Club A" }, name: "Spring 2026", starts_on: "2026-09-01", ends_on: "2026-12-15" }],
  },
};
const FILE = () => new File(["Date,Time\n"], "fixtures.csv", { type: "text/csv" });

const ROW = {
  row: 2,
  kick_off: "2026-10-27T19:40:00+02:00",
  night: 1,
  division: "Division 2",
  pitch: "Pitch 3",
  home: "Red Lions",
  away: "Old Boys",
  friendly_eligible: true,
  action: "create",
  changes: [],
  errors: [],
};
const SUMMARY = { rows: 2, fixtures_created: 1, fixtures_updated: 0, unchanged: 1, errors: 0 };
const PREVIEW = {
  committed: false,
  summary: SUMMARY,
  rows: [ROW, { ...ROW, row: 3, home: "City Rovers", friendly_eligible: false, action: "unchanged" }],
};
const WITH_ERRORS = {
  committed: false,
  summary: { ...SUMMARY, fixtures_created: 0, unchanged: 0, errors: 1 },
  rows: [{ ...ROW, away: "Nobody FC", action: "error", errors: ['Division 2 has no Team "Nobody FC" in Spring 2026.'] }],
};

async function pickSeasonAndFile() {
  await userEvent.click(await screen.findByRole("button", { name: "Spring 2026" }));
  await userEvent.upload(screen.getByLabelText("Choose a spreadsheet"), FILE());
}

afterEach(() => vi.restoreAllMocks());

describe("ImportFixturesPage", () => {
  it("needs a Season before a file", async () => {
    await openAs(PAGE, SEASONS, TITLE, ADMIN_ME);

    expect(await screen.findByLabelText("Pick a Season, then a spreadsheet")).toBeDisabled();
  });

  it("previews the file for the Season, imports it on confirm and links back", async () => {
    const append = vi.spyOn(FormData.prototype, "append");
    const { calls } = await openAs(
      PAGE,
      {
        ...SEASONS,
        [`POST ${IMPORTS}/preview/`]: { status: 200, body: PREVIEW },
        [`POST ${IMPORTS}/commit/`]: { status: 200, body: { ...PREVIEW, committed: true } },
      },
      TITLE,
      ADMIN_ME,
    );

    await pickSeasonAndFile();

    expect(await screen.findByText("1 new Fixture, 1 unchanged")).toBeInTheDocument();
    const rows = within(screen.getByRole("list", { name: "Rows" })).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Red Lions vs Old Boys");
    expect(rows[0]).toHaveTextContent("Row 2 · Tue 27 Oct · 19:40 · Pitch 3 · Tuesday · Division 2 · Friendly-eligible");
    expect(rows[0]).toHaveTextContent("Status: New");
    expect(rows[1]).toHaveTextContent("Status: No change");

    await userEvent.click(screen.getByRole("button", { name: "Import 1 Fixture" }));

    expect(await screen.findByText("Imported")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See fixtures" })).toHaveAttribute("href", "/clubs/1/fixtures");
    const sent = calls.filter((c) => c.method === "POST");
    expect(sent.map((c) => c.path)).toEqual([`${IMPORTS}/preview/`, `${IMPORTS}/commit/`]);
    expect(sent.every((c) => (c.body as { season: string }).season === "5")).toBe(true);
    expect(append).toHaveBeenCalledWith("season", "5");
    expect(append).toHaveBeenLastCalledWith("file", expect.any(File), "fixtures.csv");
  });

  it("shows row errors and offers no import until the file is fixed", async () => {
    await openAs(PAGE, { ...SEASONS, [`POST ${IMPORTS}/preview/`]: { status: 200, body: WITH_ERRORS } }, TITLE, ADMIN_ME);

    await pickSeasonAndFile();

    expect(await screen.findByText("1 row has errors")).toBeInTheDocument();
    expect(screen.getByText('Division 2 has no Team "Nobody FC" in Spring 2026.')).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Import/ })).not.toBeInTheDocument();
  });

  it("shows the rows when the commit finds errors", async () => {
    await openAs(
      PAGE,
      {
        ...SEASONS,
        [`POST ${IMPORTS}/preview/`]: { status: 200, body: PREVIEW },
        [`POST ${IMPORTS}/commit/`]: { status: 400, body: WITH_ERRORS },
      },
      TITLE,
      ADMIN_ME,
    );
    await pickSeasonAndFile();

    await userEvent.click(await screen.findByRole("button", { name: "Import 1 Fixture" }));

    expect(await screen.findByText("1 row has errors")).toBeInTheDocument();
  });

  it("shows a file or Season the API refuses", async () => {
    await openAs(
      PAGE,
      { ...SEASONS, [`POST ${IMPORTS}/preview/`]: { status: 400, body: { season: ["This Season has ended."] } } },
      TITLE,
      ADMIN_ME,
    );

    await pickSeasonAndFile();

    expect(await screen.findByRole("alert")).toHaveTextContent("This Season has ended.");
  });

  it("says to add a Season when there is none", async () => {
    await openAs(PAGE, { "GET /api/v1/seasons/": { status: 200, body: [] } }, TITLE, ADMIN_ME);

    expect(await screen.findByText("No Season to import into")).toBeInTheDocument();
  });
});
