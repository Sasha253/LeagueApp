import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { openAs } from "../teams/testing";
import { myFixture } from "./testing";

const DETAIL = "GET /api/v1/fixtures/30/";

describe("FixturePage", () => {
  it("shows the match, your team and the opponent", async () => {
    await openAs("/fixtures/30", { [DETAIL]: { status: 200, body: myFixture() } }, "Match");

    expect(await screen.findByRole("article", { name: "Red Lions vs Old Boys" })).toHaveTextContent("19:40");
    expect(screen.getByText("Old Boys, against Red Lions")).toBeInTheDocument();
    expect(screen.getByText("Division 2 · Spring 2026 · Club A")).toBeInTheDocument();
    expect(screen.queryByText(/played as a friendly/)).not.toBeInTheDocument();
  });

  it("says when the match may become a friendly", async () => {
    await openAs(
      "/fixtures/30",
      { [DETAIL]: { status: 200, body: myFixture({ friendly_eligible: true, status: "one_team_out" }) } },
      "Match",
    );

    expect(await screen.findByText(/may be played as a friendly/)).toBeInTheDocument();
    expect(screen.getAllByText("One team out")).not.toHaveLength(0);
  });

  it("offers Retry when the match can't be loaded", async () => {
    await openAs("/fixtures/30", { [DETAIL]: { status: 404, body: { detail: "Not found." } } }, "Match");

    expect(await screen.findByText("Couldn't load the match")).toBeInTheDocument();
  });
});
