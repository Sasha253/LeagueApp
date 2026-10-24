import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { json } from "../../test/fakeApi";
import { openAs } from "../teams/testing";
import { openingSeason } from "./shared";
import {
  ADMIN,
  AUTUMN,
  figures,
  line,
  outstanding,
  plan,
  SPRING,
  summary,
  THURSDAY_NIGHT,
  TUESDAY_NIGHT,
} from "./testing";

const SEASONS = "GET /api/v1/clubs/1/seasons/";
const NIGHTS = "GET /api/v1/clubs/1/nights/";
const SUMMARY = "GET /api/v1/clubs/1/finance/summary/";
const TEAMS = "GET /api/v1/clubs/1/team-payments/";
const PLANNER = "GET /api/v1/clubs/1/finance/planner/";
const OUTSTANDING = "GET /api/v1/clubs/1/finance/outstanding/";

function teamRow(id: number, name: string, division: { id: number; name: string }, overrides: object = {}) {
  return {
    team: { id, name },
    season: { id: 5, name: "Spring 2026" },
    division,
    due: "350.00",
    paid: "150.00",
    outstanding: "200.00",
    is_paid: false,
    ...overrides,
  };
}

const TEAM_ROWS = [
  teamRow(7, "Red Lions", { id: 3, name: "Division 2" }),
  teamRow(8, "Old Boys", { id: 9, name: "Division 1" }, { paid: "350.00", outstanding: "0.00", is_paid: true }),
  teamRow(12, "Last Season FC", { id: 3, name: "Division 2" }, { season: { id: 4, name: "Autumn 2026" } }),
];

let teamQueries: URLSearchParams[] = [];

function routes(queries: URLSearchParams[], answer: (query: URLSearchParams) => object = () => summary()) {
  return {
    [SEASONS]: { status: 200, body: [SPRING, AUTUMN] },
    [NIGHTS]: { status: 200, body: [TUESDAY_NIGHT, THURSDAY_NIGHT] },
    [PLANNER]: { status: 200, body: plan() },
    [OUTSTANDING]: { status: 200, body: outstanding() },
    [TEAMS]: (request: Request) => {
      teamQueries.push(new URL(request.url).searchParams);
      return json(200, TEAM_ROWS);
    },
    [SUMMARY]: (request: Request) => {
      const query = new URL(request.url).searchParams;
      queries.push(query);
      return json(200, answer(query));
    },
  };
}

describe("FinancesPage", () => {
  it("shows the running Season's totals, income lines and Divisions as rand", async () => {
    const queries: URLSearchParams[] = [];
    await openAs("/clubs/1/finances", routes(queries), "Finances", ADMIN);

    const card = await screen.findByRole("region", { name: "Finances, Spring 2026 · All Nights" });
    expect(queries[0]!.get("season")).toBe("5");
    expect(queries[0]!.has("night")).toBe(false);
    expect(within(card).getByText("R 28,000")).toBeInTheDocument();
    expect(within(card).getByText("R 18,410")).toBeInTheDocument();
    const owed = within(card).getByText("R 490");
    expect(owed).toHaveClass("la-stat__value--owed");
    expect(within(card).getByText("R 420")).toBeInTheDocument();

    const method = screen.getByRole("region", { name: "League money by method" });
    expect(within(method).getByText("R 15,960")).toBeInTheDocument();
    expect(within(method).getByText("R 2,450")).toBeInTheDocument();
    expect(within(method).getByText("R 700")).toBeInTheDocument();

    const lines = screen.getByRole("list", { name: "Income lines" });
    const [league, friendly, booking, all] = within(lines).getAllByRole("listitem");
    expect(within(league!).getByText("League")).toBeInTheDocument();
    expect(within(league!).getByText("Card R 15,960 · Cash R 2,450 · Credit used R 700")).toBeInTheDocument();
    expect(within(friendly!).getByText("R 700")).toBeInTheDocument();
    expect(within(booking!).getByText("Bookings")).toBeInTheDocument();
    expect(within(booking!).getByText("R 540")).toBeInTheDocument();
    expect(within(all!).getByText("R 19,650")).toBeInTheDocument();
    const credit = screen.getByRole("list", { name: "Credit held" });
    expect(within(credit).getByText("R 210")).toBeInTheDocument();
    expect(within(credit).getByText("R 90")).toBeInTheDocument();

    const tuesday = screen.getByRole("list", { name: "Tuesday" });
    expect(within(tuesday).getByText("Division 2")).toBeInTheDocument();
    expect(within(tuesday).getAllByText("8 Teams · R 18,410 received of R 28,000 · Friendlies R 700")).toHaveLength(2);
    expect(within(tuesday).getAllByText("R 490 to go", { exact: false })).toHaveLength(2);
  });

  it("lists the Season's Teams, each opening its Team ledger", async () => {
    teamQueries = [];
    await openAs("/clubs/1/finances", routes([]), "Finances", ADMIN);

    const teams = await screen.findByRole("list", { name: "Teams" });
    expect(teamQueries[0]!.get("season")).toBe("5");
    const links = within(teams).getAllByRole("link");
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", "/clubs/1/finances/teams/7");
    expect(within(links[0]!).getByText("Division 2 · R 150 of R 350")).toBeInTheDocument();
    expect(within(links[1]!).getByText("Paid", { exact: false })).toBeInTheDocument();
    expect(screen.queryByText("Last Season FC")).not.toBeInTheDocument();
  });

  it("filters by Season, Night and Division", async () => {
    const queries: URLSearchParams[] = [];
    await openAs(
      "/clubs/1/finances",
      routes(queries, (query) =>
        summary({
          season: query.get("season") === "4" ? { id: 4, name: "Autumn 2026" } : { id: 5, name: "Spring 2026" },
          night: query.get("night") ? { id: 2, weekday: 1 } : null,
          division: query.get("division") ? { id: 3, name: "Division 2" } : null,
          booking: query.get("night") ? null : line(),
          credit_held: { team: "0.00", player: query.get("night") ? null : "0.00", booking_user: query.get("night") ? null : "0.00" },
        }),
      ),
      "Finances",
      ADMIN,
    );
    const user = userEvent.setup();
    await screen.findByRole("region", { name: "Finances, Spring 2026 · All Nights" });
    expect(screen.queryByRole("group", { name: "Division" })).not.toBeInTheDocument();

    await user.click(within(screen.getByRole("group", { name: "Night" })).getByRole("button", { name: "Tuesday" }));
    await screen.findByRole("region", { name: "Finances, Spring 2026 · Tuesday" });
    expect(queries.at(-1)!.get("night")).toBe("2");
    expect(screen.getByText("Bookings belong to no Night or Division: clear the filter to see them.")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Credit held" })).not.toBeInTheDocument();
    // Only Tuesday's Teams.
    expect(within(screen.getByRole("list", { name: "Teams" })).getAllByRole("link")).toHaveLength(1);

    const divisions = screen.getByRole("group", { name: "Division" });
    await user.click(within(divisions).getByRole("button", { name: "Division 2" }));
    await screen.findByRole("region", { name: "Finances, Spring 2026 · Tuesday · Division 2" });
    expect(queries.at(-1)!.get("division")).toBe("3");

    await user.click(within(screen.getByRole("group", { name: "Season" })).getByRole("button", { name: "Autumn 2026" }));
    await screen.findByRole("region", { name: "Finances, Autumn 2026 · Tuesday · Division 2" });
    expect(queries.at(-1)!.get("season")).toBe("4");
    expect(screen.getByText("Last Season FC")).toBeInTheDocument();

    await user.click(within(screen.getByRole("group", { name: "Night" })).getByRole("button", { name: "All" }));
    await screen.findByRole("region", { name: "Finances, Autumn 2026 · All Nights" });
    expect(queries.at(-1)!.has("division")).toBe(false);
  });

  it("links to the Season comparison", async () => {
    await openAs("/clubs/1/finances", routes([]), "Finances", ADMIN);
    expect(screen.getByRole("link", { name: "Compare Seasons" })).toHaveAttribute("href", "/clubs/1/finances/compare");
  });

  it("says when the club has no Seasons", async () => {
    await openAs(
      "/clubs/1/finances",
      { [SEASONS]: { status: 200, body: [] }, [NIGHTS]: { status: 200, body: [] } },
      "Finances",
      ADMIN,
    );
    expect(await screen.findByText("No Seasons yet. Add a Season in Club setup to see its finances.")).toBeInTheDocument();
  });

  it("says when no Teams are in the Season", async () => {
    await openAs(
      "/clubs/1/finances",
      routes([], () => summary({ totals: figures({ teams: 0, expected: "0.00", outstanding: "0.00" }), nights: [] })),
      "Finances",
      ADMIN,
    );
    expect(await screen.findByText("No Teams in this Season here yet.")).toBeInTheDocument();
  });

  it("tells a non-Admin the finances are for Admins", async () => {
    await openAs(
      "/clubs/1/finances",
      { [SEASONS]: { status: 403, body: { detail: "No." } }, [NIGHTS]: { status: 403, body: { detail: "No." } } },
      "Finances",
    );
    expect(await screen.findByText("Only this club's Admins can see its finances.")).toBeInTheDocument();
  });

  it("offers Retry when the figures don't load", async () => {
    await openAs("/clubs/1/finances", { ...routes([]), [SUMMARY]: { status: 500, body: {} } }, "Finances", ADMIN);
    expect(await screen.findByText("Couldn't load the finances")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});

describe("openingSeason", () => {
  it("opens on the Season running now, else the latest", () => {
    expect(openingSeason([SPRING, AUTUMN], "2026-10-24")).toBe(5);
    expect(openingSeason([SPRING, AUTUMN], "2026-04-01")).toBe(4);
    expect(openingSeason([AUTUMN, SPRING], "2027-02-01")).toBe(5);
    expect(openingSeason([], "2026-10-24")).toBeNull();
  });
});
