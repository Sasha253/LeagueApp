import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { json } from "../../test/fakeApi";
import { openAs } from "../teams/testing";
import { myFixture } from "./testing";

const LIST = "GET /api/v1/me/fixtures/";

/** Answers the list by its `when` query. */
function byWhen(upcoming: object[], past: object[]) {
  return (request: Request) =>
    json(200, new URL(request.url).searchParams.get("when") === "past" ? past : upcoming);
}

describe("MyFixturesPage", () => {
  it("shows upcoming matches as cards, in South African time", async () => {
    await openAs("/fixtures", { [LIST]: byWhen([myFixture({ friendly_eligible: true })], []) }, "My fixtures");

    const card = await screen.findByRole("article", { name: "Red Lions vs Old Boys" });
    expect(within(card).getByText("Tue 27 Oct · Pitch 3")).toBeInTheDocument();
    expect(within(card).getByText("19:40")).toBeInTheDocument();
    expect(within(card).getByText("Division 2")).toBeInTheDocument();
    expect(within(card).getByText("Friendly-eligible")).toBeInTheDocument();
    expect(card).toHaveTextContent("Status: Scheduled");
    expect(card.closest("a")).toHaveAttribute("href", "/fixtures/30");
  });

  it("lists past matches under Before", async () => {
    const past = myFixture({ id: 31, kick_off: "2026-10-20T17:40:00Z", status: "cancelled" });
    await openAs("/fixtures", { [LIST]: byWhen([], [past]) }, "My fixtures");

    const before = await screen.findByRole("region", { name: "Before" });
    const link = within(before).getByRole("link", { name: /Red Lions vs Old Boys/ });
    expect(link).toHaveTextContent("Tue 20 Oct · 19:40 · Pitch 3");
    expect(link).toHaveTextContent("Status: Cancelled");
    expect(link).toHaveAttribute("href", "/fixtures/31");
  });

  it("says when there are no fixtures yet", async () => {
    await openAs("/fixtures", { [LIST]: byWhen([], []) }, "My fixtures");

    expect(await screen.findByText(/No fixtures for your Teams yet/)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Before" })).not.toBeInTheDocument();
  });

  it("tells someone who doesn't play why there's nothing", async () => {
    await openAs("/fixtures", { [LIST]: { status: 403, body: { detail: "No." } } }, "My fixtures");

    expect(await screen.findAllByText(/Fixtures are for Players/)).not.toHaveLength(0);
  });

  it("lists the friendlies you captain, with their Barcode", async () => {
    const row = {
      fixture: {
        id: 30,
        kick_off: "2026-10-27T17:40:00Z",
        home_team: { id: 7, name: "Red Lions" },
        away_team: { id: 8, name: "Old Boys" },
        pitch: { id: 3, name: "Pitch 3" },
      },
      club: { id: 1, name: "Club A" },
      settled: false,
      outstanding: "50.00",
    };
    await openAs(
      "/fixtures",
      { [LIST]: byWhen([], []), "GET /api/v1/me/friendlies/": { status: 200, body: [row] } },
      "My fixtures",
    );

    const list = await screen.findByRole("list", { name: "Friendlies you captain" });
    expect(within(list).getByText("Red Lions vs Old Boys")).toBeInTheDocument();
    expect(within(list).getByText("Tue 27 Oct · 19:40 · Pitch 3 · Club A")).toBeInTheDocument();
    expect(within(list).getByText("R 50 still to pay")).toBeInTheDocument();
    expect(within(list).getByRole("link", { name: "Barcode" })).toHaveAttribute("href", "/friendlies/30/barcode");
  });
});
