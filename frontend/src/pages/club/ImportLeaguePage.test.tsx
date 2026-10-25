import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as platform from "../../native/platform";
import { openAsAdmin } from "./testing";

const IMPORTS = "/api/v1/clubs/1/imports/league";
const PAGE = "/clubs/1/setup/import";
const TITLE = "Import from Excel";
const FILE = () => new File(["xlsx"], "league.xlsx");

const SEASON = {
  row: 2,
  name: "Summer",
  starts_on: "2026-11-02",
  ends_on: "2027-01-24",
  action: "create",
  changes: [],
  errors: [],
};
const DIVISION = {
  row: 2,
  night: 1,
  division: "Division 2",
  min_players: 6,
  league_fee: null,
  action: "create",
  new_night: true,
  changes: [],
  errors: [],
};
const FIXTURE = {
  row: 2,
  season: "Summer",
  kick_off: "2026-11-03T17:40:00Z",
  night: 1,
  division: "Division 2",
  pitch: "Pitch 3",
  home: "Red Lions",
  away: "Old Boys",
  friendly_eligible: true,
  action: "create",
  new_teams: ["Red Lions", "Old Boys"],
  changes: [],
  errors: [],
};
const SUMMARY = {
  rows: 4,
  seasons_created: 1,
  seasons_updated: 0,
  nights_created: 1,
  divisions_created: 1,
  divisions_updated: 0,
  teams_created: 2,
  fixtures_created: 1,
  fixtures_updated: 0,
  unchanged: 1,
  errors: 0,
};
const PREVIEW = {
  committed: false,
  summary: SUMMARY,
  seasons: [SEASON],
  divisions: [DIVISION],
  fixtures: [FIXTURE, { ...FIXTURE, row: 3, kick_off: "2026-11-03T18:30:00Z", new_teams: [], action: "unchanged" }],
};
const WITH_ERRORS = {
  committed: false,
  summary: { ...SUMMARY, seasons_created: 0, teams_created: 0, fixtures_created: 0, unchanged: 0, errors: 1 },
  seasons: [],
  divisions: [],
  fixtures: [{ ...FIXTURE, action: "error", new_teams: [], errors: ['The club has no pitch "Pitch 9".'] }],
};

async function choose() {
  await userEvent.upload(screen.getByLabelText("Choose a workbook"), FILE());
}

afterEach(() => vi.restoreAllMocks());

describe("ImportLeaguePage", () => {
  it("previews every sheet, imports on confirm and links to what it set up", async () => {
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

    expect(
      await screen.findByText(
        "1 new Season, 1 new Night, 1 new Division, 2 new Teams, 1 new Fixture, 1 unchanged",
      ),
    ).toBeInTheDocument();
    const seasons = within(screen.getByRole("region", { name: "Seasons" })).getAllByRole("listitem");
    expect(seasons[0]).toHaveTextContent("Summer");
    expect(seasons[0]).toHaveTextContent("Row 2 · Mon 2 Nov to Sun 24 Jan");
    const divisions = within(screen.getByRole("region", { name: "Nights and Divisions" })).getAllByRole("listitem");
    expect(divisions[0]).toHaveTextContent("Tuesday · Division 2");
    expect(divisions[0]).toHaveTextContent("Row 2 · Minimum 6 players · club fee · new Night");
    const fixtures = within(screen.getByRole("region", { name: "Fixtures" })).getAllByRole("listitem");
    expect(fixtures[0]).toHaveTextContent("Red Lions vs Old Boys");
    expect(fixtures[0]).toHaveTextContent(
      "Row 2 · Summer · Tue 3 Nov · 19:40 · Pitch 3 · Division 2 · Friendly-eligible · new Teams: Red Lions, Old Boys",
    );
    expect(fixtures[0]).toHaveTextContent("Status: New");
    expect(fixtures[1]).toHaveTextContent("Status: No change");

    await userEvent.click(screen.getByRole("button", { name: "Import 3 rows" }));

    expect(await screen.findByText("Imported")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Fixtures" })).toHaveAttribute("href", "/clubs/1/fixtures");
    expect(screen.getByRole("link", { name: "Seasons" })).toHaveAttribute("href", "/clubs/1/setup/seasons");
    const sent = calls.filter((c) => c.method === "POST");
    expect(sent.map((c) => c.path)).toEqual([`${IMPORTS}/preview/`, `${IMPORTS}/commit/`]);
    expect(sent.every((c) => Object.keys(c.body as object).join() === "file")).toBe(true);
    expect(append).toHaveBeenCalledTimes(2);
    expect(append).toHaveBeenLastCalledWith("file", expect.any(File), "league.xlsx");
  });

  it("shows row errors and offers no import until the file is fixed", async () => {
    await openAsAdmin(PAGE, { [`POST ${IMPORTS}/preview/`]: { status: 200, body: WITH_ERRORS } }, TITLE);

    await choose();

    expect(await screen.findByText("1 row has errors")).toBeInTheDocument();
    expect(screen.getByText('The club has no pitch "Pitch 9".')).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Seasons" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Import/ })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Choose another file" }));
    expect(screen.getByLabelText("Choose a workbook")).toBeInTheDocument();
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
    await userEvent.click(await screen.findByRole("button", { name: "Import 3 rows" }));

    expect(await screen.findByText("1 row has errors")).toBeInTheDocument();
    expect(screen.queryByText("Imported")).not.toBeInTheDocument();
  });

  it("says why a file can't be used", async () => {
    const message = "Upload an Excel workbook (.xlsx). The template shows its sheets.";
    await openAsAdmin(PAGE, { [`POST ${IMPORTS}/preview/`]: { status: 400, body: { file: [message] } } }, TITLE);

    await choose();

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByLabelText("Choose a workbook")).toBeInTheDocument();
  });

  it("downloads the template in the browser", async () => {
    const createObjectURL = vi.fn(() => "blob:template");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const { calls } = await openAsAdmin(
      PAGE,
      { [`GET ${IMPORTS}/template/`]: () => new Response("xlsx", { status: 200 }) },
      TITLE,
    );

    await userEvent.click(screen.getByRole("button", { name: "Excel template" }));

    await vi.waitFor(() => expect(click).toHaveBeenCalled());
    expect(createObjectURL).toHaveBeenCalled();
    expect(calls.find((c) => c.method === "GET" && c.path.endsWith("/template/"))).toBeTruthy();
  });

  it("asks the installed app's Admin to download the template in a browser", async () => {
    vi.spyOn(platform, "isNative").mockReturnValue(true);
    await openAsAdmin(PAGE, { [`GET ${IMPORTS}/template/`]: () => new Response("x", { status: 200 }) }, TITLE);

    await userEvent.click(screen.getByRole("button", { name: "Excel template" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Download the template from League App in a web browser.");
  });
});
