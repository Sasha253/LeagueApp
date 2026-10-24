import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { json, type Routes } from "../../test/fakeApi";
import { openAs } from "../teams/testing";
import { names } from "./Outstanding";
import { reading } from "./Planner";
import { ADMIN, outstanding, plan, playerOwed, SPRING, summary, TUESDAY_NIGHT } from "./testing";

const PLANNER = "GET /api/v1/clubs/1/finance/planner/";
const OUTSTANDING = "GET /api/v1/clubs/1/finance/outstanding/";
const REMIND = "POST /api/v1/clubs/1/finance/outstanding/remind/";
const CASH = "POST /api/v1/clubs/1/finance/outstanding/cash/";

function routes(extra: Routes = {}): Routes {
  return {
    "GET /api/v1/clubs/1/seasons/": { status: 200, body: [SPRING] },
    "GET /api/v1/clubs/1/nights/": { status: 200, body: [TUESDAY_NIGHT] },
    "GET /api/v1/clubs/1/finance/summary/": { status: 200, body: summary() },
    "GET /api/v1/clubs/1/team-payments/": { status: 200, body: [] },
    [PLANNER]: { status: 200, body: plan() },
    [OUTSTANDING]: { status: 200, body: outstanding() },
    ...extra,
  };
}

const CASH_ENTRY = {
  id: 90,
  kind: "payment",
  method: "cash",
  category: "league",
  amount: "350.00",
  subject: "team",
  team: { id: 7, name: "Hammers" },
  player: null,
  fixture_id: null,
  booking_id: null,
  reverses_id: null,
  source_id: null,
  reason: "Cash paid, marked on the Outstanding list",
  recorded_by: { id: 50, name: "Club Admin" },
  created_at: "2026-10-20T11:50:00Z",
};

describe("Planner", () => {
  it("shows due to date, paid, behind and season expected, with a bar per week", async () => {
    await openAs("/clubs/1/finances", routes(), "Finances", ADMIN);

    const card = await screen.findByRole("region", { name: "Planner, Spring 2026 · All Nights" });
    expect(within(card).getByText("R 19,600")).toBeInTheDocument();
    expect(within(card).getByText("R 19,110")).toBeInTheDocument();
    expect(within(card).getByText("R 490")).toHaveClass("la-stat__value--owed");
    expect(within(card).getByText("R 28,000")).toBeInTheDocument();
    const bars = within(card).getByRole("img", { name: "Week 7 is R 140 short; season R 490 behind." });
    expect(bars.children).toHaveLength(10);
    expect(bars.children[6]).toHaveClass("la-planner__week--now");
    // Week 4: R 2,450 of R 2,800 paid.
    expect(bars.children[3]!.querySelector(".la-planner__got")).toHaveStyle({ height: "88%" });
    expect(bars.children[8]!.querySelector(".la-planner__got")).toBeNull();
  });

  it("asks for the Season's scope and lists the weeks on request", async () => {
    const { calls } = await openAs("/clubs/1/finances", routes(), "Finances", ADMIN);
    const card = await screen.findByRole("region", { name: "Planner, Spring 2026 · All Nights" });
    expect(calls.some((c) => c.path === "/api/v1/clubs/1/finance/planner/")).toBe(true);

    await userEvent.setup().click(within(card).getByRole("button", { name: "Show weeks" }));
    const weeks = within(card).getByRole("list", { name: "Weeks" });
    const rows = within(weeks).getAllByRole("listitem");
    expect(rows).toHaveLength(10);
    expect(within(rows[3]!).getByText("Tue 22 Sep to Mon 28 Sep · 4 matches")).toBeInTheDocument();
    expect(within(rows[3]!).getByText("R 2,450 paid · R 350 short · R 0 received that week")).toBeInTheDocument();
    expect(within(rows[6]!).getByText("Week 7 · this week")).toBeInTheDocument();
  });

  it("says when nothing is in a week yet", async () => {
    const empty = plan({
      weeks: plan().weeks.map((w) => ({ ...w, expected: "0.00", covered: "0.00", short: "0.00" })),
      unscheduled: "700.00",
    });
    await openAs("/clubs/1/finances", routes({ [PLANNER]: { status: 200, body: empty } }), "Finances", ADMIN);
    expect(
      await screen.findByText("No league fees fall in a week yet: they are spread over the fixture list."),
    ).toBeInTheDocument();
    expect(screen.getByText("R 700 is from Teams with no fixtures yet, so it is in no week.")).toBeInTheDocument();
  });

  it("reads before the Season and when on track", () => {
    const before = plan({ weeks: plan().weeks.map((w) => ({ ...w, is_due: false, is_current: false })) });
    expect(reading(before)).toBe("The Season starts Tue 1 Sep; nothing is due yet.");
    const fine = plan({ behind: "0.00", weeks: plan().weeks.map((w) => ({ ...w, short: "0.00" })) });
    expect(reading(fine)).toBe("Week 7 is paid; season on track.");
  });
});

describe("Outstanding list", () => {
  it("lists Teams and then Players who owe, largest first", async () => {
    await openAs("/clubs/1/finances", routes(), "Finances", ADMIN);

    const teams = await screen.findByRole("list", { name: "Outstanding teams" });
    const [hammers, boys] = within(teams).getAllByRole("listitem");
    expect(within(hammers!).getByText("Hammers")).toBeInTheDocument();
    expect(within(hammers!).getByText("R 350")).toHaveClass("la-owed__amount");
    expect(within(hammers!).getByText("Tuesday · Division 2 · Short since week 4 · Owed by the Team")).toBeInTheDocument();
    expect(
      within(boys!).getByText("Tuesday · Division 2 · Short since week 7 · Werner Smit and Dylan Jacobs unpaid"),
    ).toBeInTheDocument();

    await userEvent.setup().click(screen.getByRole("button", { name: "Players · 2" }));
    const players = screen.getByRole("list", { name: "Outstanding players" });
    const [werner, dylan] = within(players).getAllByRole("listitem");
    expect(within(werner!).getByText("Old Boys · Share R 70, paid R 0")).toBeInTheDocument();
    expect(within(werner!).getByRole("button", { name: "Remind" })).toBeEnabled();
    expect(within(dylan!).getByText("Doesn't get notifications for this Night.")).toBeInTheDocument();
    expect(within(dylan!).getByRole("button", { name: "Remind" })).toBeDisabled();
  });

  it("reminds a Team and says who was not reached", async () => {
    const { calls } = await openAs(
      "/clubs/1/finances",
      routes({
        [REMIND]: {
          status: 200,
          body: { sent_to: [{ id: 21, name: "Werner Smit" }], not_reached: [{ id: 22, name: "Dylan Jacobs" }] },
        },
      }),
      "Finances",
      ADMIN,
    );
    const teams = await screen.findByRole("list", { name: "Outstanding teams" });
    const boys = within(teams).getAllByRole("listitem")[1]!;

    await userEvent.setup().click(within(boys).getByRole("button", { name: "Remind" }));

    expect(await screen.findByText("Reminder sent to Werner Smit.")).toBeInTheDocument();
    expect(
      screen.getByText("Dylan Jacobs doesn't get notifications for this Night, so wasn't told."),
    ).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ team_id: 8, player_id: null });
  });

  it("marks cash paid after asking, then loads the figures again", async () => {
    const { calls } = await openAs(
      "/clubs/1/finances",
      routes({
        [CASH]: { status: 201, body: CASH_ENTRY },
        [OUTSTANDING]: [
          { status: 200, body: outstanding() },
          { status: 200, body: outstanding({ teams: outstanding().teams.slice(1) }) },
        ],
      }),
      "Finances",
      ADMIN,
    );
    const user = userEvent.setup();
    const teams = await screen.findByRole("list", { name: "Outstanding teams" });
    const hammers = within(teams).getAllByRole("listitem")[0]!;

    await user.click(within(hammers).getByRole("button", { name: "Mark cash paid" }));
    expect(calls.some((c) => c.method === "POST")).toBe(false);
    await user.click(within(hammers).getByRole("button", { name: "Record R 350 cash" }));

    expect(await screen.findByText("R 350 cash recorded for Hammers.")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ team_id: 7, player_id: null, amount: "350.00" });
    expect(await screen.findByRole("button", { name: "Teams · 1" })).toBeInTheDocument();
    const summaries = calls.filter((c) => c.path === "/api/v1/clubs/1/finance/summary/");
    expect(summaries.length).toBeGreaterThan(1);
  });

  it("keeps a Player's cash for that Player and shows a refusal", async () => {
    const { calls } = await openAs(
      "/clubs/1/finances",
      routes({
        [OUTSTANDING]: { status: 200, body: outstanding({ teams: [], players: [playerOwed()] }) },
        [CASH]: { status: 409, body: { detail: "What is owed is now R 35. Check it and try again." } },
      }),
      "Finances",
      ADMIN,
    );
    const user = userEvent.setup();
    expect(await screen.findByText("No Team owes anything here.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Players · 1" }));
    await user.click(screen.getByRole("button", { name: "Mark cash paid" }));
    await user.click(screen.getByRole("button", { name: "Record R 70 cash" }));

    expect(await screen.findByText("What is owed is now R 35. Check it and try again.")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ team_id: 8, player_id: 21, amount: "70.00" });
  });

  it("offers Retry when the list doesn't load", async () => {
    await openAs(
      "/clubs/1/finances",
      routes({ [OUTSTANDING]: (_request: Request) => json(500, {}) }),
      "Finances",
      ADMIN,
    );
    expect(await screen.findByText("Couldn't load the Outstanding list")).toBeInTheDocument();
  });
});

describe("names", () => {
  it("joins names in plain English", () => {
    expect(names(["Thandi"])).toBe("Thandi");
    expect(names(["Thandi", "Sipho"])).toBe("Thandi and Sipho");
    expect(names(["Thandi", "Sipho", "Pieter"])).toBe("Thandi, Sipho and Pieter");
  });
});
