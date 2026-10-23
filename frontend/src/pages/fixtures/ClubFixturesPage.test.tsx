import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { json } from "../../test/fakeApi";
import { ADMIN_ME } from "../club/testing";
import { openAs } from "../teams/testing";
import { adminFixture } from "./testing";

const LIST = "GET /api/v1/clubs/1/fixtures/";
const SEASONS = { "GET /api/v1/clubs/1/seasons/": { status: 200, body: [{ id: 5, name: "Spring 2026", starts_on: "2026-09-01", ends_on: "2026-12-15" }] } };
const NIGHTS = {
  "GET /api/v1/clubs/1/nights/": {
    status: 200,
    body: [
      { id: 2, weekday: 1, divisions: [] },
      { id: 4, weekday: 3, divisions: [] },
    ],
  },
};

const EARLY = adminFixture({ id: 30, kick_off: "2026-10-27T16:30:00Z", friendly_eligible: true });
const LATE = adminFixture({ id: 31, kick_off: "2026-10-27T17:40:00Z", status: "confirming" });
const THURSDAY = adminFixture({
  id: 32,
  kick_off: "2026-10-29T17:40:00Z",
  weekday: 3,
  home_team: { id: 10, name: "City Rovers" },
  away_team: { id: 11, name: "Hat Trick FC" },
});

describe("ClubFixturesPage", () => {
  it("lists the club's fixtures day by day", async () => {
    await openAs(
      "/clubs/1/fixtures",
      { ...SEASONS, ...NIGHTS, [LIST]: { status: 200, body: [EARLY, LATE, THURSDAY] } },
      "Fixtures",
      ADMIN_ME,
    );

    const tuesday = await screen.findByRole("region", { name: "Tue 27 Oct" });
    const rows = within(tuesday).getAllByRole("link");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("18:30 · Pitch 3");
    expect(rows[0]).toHaveTextContent("Red Lions vs Old Boys");
    expect(rows[0]).toHaveTextContent("Tuesday · Division 2 · Friendly-eligible");
    expect(rows[0]).toHaveAttribute("href", "/clubs/1/fixtures/30");
    expect(rows[1]).toHaveTextContent("19:40 · Pitch 3");
    expect(rows[1]).toHaveTextContent("Status: Confirming");
    const thursday = screen.getByRole("region", { name: "Thu 29 Oct" });
    expect(within(thursday).getByRole("link")).toHaveTextContent("City Rovers vs Hat Trick FC");
    expect(screen.getByRole("link", { name: "Import fixtures" })).toHaveAttribute("href", "/clubs/1/fixtures/import");
  });

  it("asks the API for one Night's or one Season's fixtures", async () => {
    const asked: string[] = [];
    await openAs(
      "/clubs/1/fixtures",
      {
        ...SEASONS,
        ...NIGHTS,
        [LIST]: (request: Request) => {
          const query = new URL(request.url).searchParams;
          asked.push(query.toString());
          return json(200, query.get("night") === "4" ? [THURSDAY] : [EARLY, THURSDAY]);
        },
      },
      "Fixtures",
      ADMIN_ME,
    );
    await screen.findByRole("region", { name: "Tue 27 Oct" });

    await userEvent.click(screen.getByRole("button", { name: "Thursday" }));

    expect(await screen.findByRole("button", { name: "Thursday", pressed: true })).toBeInTheDocument();
    await screen.findByText("City Rovers vs Hat Trick FC");
    expect(screen.queryByRole("region", { name: "Tue 27 Oct" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Spring 2026" }));
    expect(asked).toEqual(["", "night=4", "season=5&night=4"]);
  });

  it("says when there are no fixtures", async () => {
    await openAs("/clubs/1/fixtures", { ...SEASONS, ...NIGHTS, [LIST]: { status: 200, body: [] } }, "Fixtures", ADMIN_ME);

    expect(await screen.findByText(/No fixtures here yet/)).toBeInTheDocument();
  });

  it("tells someone who isn't the club's Admin", async () => {
    await openAs("/clubs/1/fixtures", { [LIST]: { status: 403, body: { detail: "No." } } }, "Fixtures");

    expect(await screen.findByText("Only this club's Admins can see its Fixtures.")).toBeInTheDocument();
  });
});
