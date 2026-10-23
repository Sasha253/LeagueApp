import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { openAs } from "../teams/testing";
import { myFixture, squad } from "./testing";

const DETAIL = "GET /api/v1/fixtures/30/";
const SQUAD = "GET /api/v1/fixtures/30/squad/";
const ANSWER = "POST /api/v1/fixtures/30/answer/";

const reply = () => screen.getByRole("article", { name: "Are you playing?" });

async function openMatch(routes: object = {}, fixture: object = { status: "confirming" }) {
  return openAs(
    "/fixtures/30",
    { [DETAIL]: { status: 200, body: myFixture(fixture) }, [SQUAD]: { status: 200, body: squad() }, ...routes },
    "Match",
  );
}

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

  it("shows the squad against the Division minimum and who has replied (FR-38)", async () => {
    await openMatch();

    const progress = await screen.findByRole("region", { name: "Squad" });
    expect(progress).toHaveTextContent("1 of 5 confirmed · Old Boys");
    expect(within(progress).getByText("Short 4")).toBeInTheDocument();
    expect(within(progress).getByRole("img", { name: "1 of 5 confirmed" })).toBeInTheDocument();
    expect(progress).toHaveTextContent("Your team needs 4 more by Tue 13:40 or it's out of the match.");
    const replies = screen.getByRole("list", { name: "Squad replies" });
    expect(replies).toHaveTextContent("Confirmed · 1Pieter Botha (captain)");
    expect(replies).toHaveTextContent("Waiting · 2Sipho Dlamini (you), Zaid Adams");
    expect(replies).toHaveTextContent("Declined · 1Ayanda Khumalo");
  });

  it("says Ready when the team meets the minimum", async () => {
    await openMatch({ [SQUAD]: { status: 200, body: squad({ confirmed: 5, below_minimum: false, short_by: 0 }) } });

    const progress = await screen.findByRole("region", { name: "Squad" });
    expect(within(progress).getByText("Ready")).toBeInTheDocument();
    expect(progress).toHaveTextContent("Your team meets the minimum for this match.");
  });

  it("answers I'm in and shows the answer with Change until the cutoff (FR-3)", async () => {
    const after = squad({
      confirmed: 2,
      waiting: 1,
      short_by: 3,
      my_answer: "confirm",
      players: squad().players.map((p) => (p.is_me ? { ...p, answer: "confirm", answered_at: "2026-10-26T06:30:00Z" } : p)),
    });
    const { calls } = await openMatch({ [ANSWER]: { status: 200, body: after } });

    expect(await screen.findByText("Reply by Tue 13:40. You can change your answer until then.")).toBeInTheDocument();
    await userEvent.click(within(reply()).getByRole("button", { name: "I'm in" }));

    expect(await within(reply()).findByText("You're in")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ answer: "confirm" });
    expect(reply()).toHaveTextContent("Answered Mon 26 Oct");
    expect(screen.getByRole("region", { name: "Squad" })).toHaveTextContent("2 of 5 confirmed");

    await userEvent.click(within(reply()).getByRole("button", { name: "Change" }));
    expect(within(reply()).getByRole("button", { name: "Can't make it" })).toBeInTheDocument();
  });

  it("shows the backend's refusal after the cutoff", async () => {
    await openMatch({
      [ANSWER]: { status: 409, body: { detail: "Replies for this match closed at Tue 27 Oct, 13:40." } },
    });

    await userEvent.click(await within(await screen.findByRole("article", { name: "Are you playing?" })).findByRole("button", { name: "Can't make it" }));

    expect(await screen.findByText("Replies for this match closed at Tue 27 Oct, 13:40.")).toBeInTheDocument();
  });

  it("keeps the answer without Change once replies are closed", async () => {
    await openMatch({ [SQUAD]: { status: 200, body: squad({ replies_open: false, my_answer: "decline" }) } }, { status: "ready" });

    expect(await within(await screen.findByRole("article", { name: "Are you playing?" })).findByText("Can't make it")).toBeInTheDocument();
    expect(within(reply()).queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Squad" })).not.toHaveTextContent("Your team needs");
  });

  it("says when replies open, before the Confirmations go out", async () => {
    await openMatch({ [SQUAD]: { status: 200, body: squad({ replies_open: false }) } }, { status: "scheduled" });

    expect(await screen.findByText("Replies open when the Confirmations go out.")).toBeInTheDocument();
    expect(within(reply()).queryByRole("button")).not.toBeInTheDocument();
  });
});
