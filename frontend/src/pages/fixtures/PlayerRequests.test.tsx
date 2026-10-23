import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { json } from "../../test/fakeApi";
import { openAs } from "../teams/testing";
import { gameToJoin, myFixture, playerRequest, squad } from "./testing";

const DETAIL = "GET /api/v1/fixtures/30/";
const SQUAD = "GET /api/v1/fixtures/30/squad/";
const REQUESTS = "/api/v1/fixtures/30/player-requests/";
const PREVIEW = "GET /api/v1/fixtures/30/player-requests/preview/";
const GAMES = "GET /api/v1/me/player-requests/";

function body(overrides: object = {}) {
  return { is_captain: true, can_request: true, max_places: 5, requests: [], ...overrides };
}

function openMatch(requests: object, squadBody: object = squad()) {
  return openAs(
    "/fixtures/30",
    {
      [DETAIL]: { status: 200, body: myFixture() },
      [SQUAD]: { status: 200, body: squadBody },
      [`GET ${REQUESTS}`]: { status: 200, body: requests },
    },
    "Match",
  );
}

/** The preview answers by the `kind` asked for. */
function previewByKind(request: Request) {
  const kind = new URL(request.url).searchParams.get("kind");
  const recipients = kind === "goalkeeper" ? 2 : 6;
  return json(200, { kind, recipients, night: "Tuesday", max_places: 5 });
}

describe("FixturePage: Player and Goalkeeper Requests", () => {
  it("lets the Captain request a player", async () => {
    await openMatch(body());

    expect(await screen.findByRole("link", { name: "Request a player" })).toHaveAttribute(
      "href",
      "/fixtures/30/players",
    );
  });

  it("shows who joined, and the Captain can withdraw an open request", async () => {
    const open = playerRequest({ filled: 1, joined: [{ id: 9, name: "Lerato Nkosi", joined_at: "2026-10-26T09:00:00Z" }] });
    const { calls } = await openAs(
      "/fixtures/30",
      {
        [DETAIL]: { status: 200, body: myFixture() },
        [SQUAD]: { status: 200, body: squad() },
        [`GET ${REQUESTS}`]: [
          { status: 200, body: body({ requests: [open] }) },
          { status: 200, body: body({ requests: [{ ...open, status: "withdrawn" }] }) },
        ],
        "POST /api/v1/player-requests/60/withdraw/": { status: 200, body: { ...open, status: "withdrawn" } },
      },
      "Match",
    );
    const list = await screen.findByRole("list", { name: "Player requests" });
    expect(list).toHaveTextContent("Old Boys needs 2 players");
    expect(list).toHaveTextContent("1 of 2 joined: Lerato Nkosi");
    expect(list).toHaveTextContent("Sent to 3 Players");
    expect(list).toHaveTextContent("Status: Open");

    await userEvent.click(within(list).getByRole("button", { name: "Withdraw" }));

    expect(await screen.findByText("Withdrawn")).toBeInTheDocument();
    expect(calls.some((c) => c.path === "/api/v1/player-requests/60/withdraw/")).toBe(true);
  });

  it("shows a Player the Team's request but no buttons", async () => {
    await openMatch(
      body({ is_captain: false, can_request: false, requests: [playerRequest({ kind: "goalkeeper", places: 1, status: "filled" })] }),
    );

    const list = await screen.findByRole("list", { name: "Player requests" });
    expect(list).toHaveTextContent("Old Boys needs a goalkeeper");
    expect(list).toHaveTextContent("Filled");
    expect(within(list).queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Request a player" })).not.toBeInTheDocument();
  });

  it("shows nothing to a Player when there is no request", async () => {
    await openMatch(body({ is_captain: false, can_request: false }));

    await screen.findByRole("region", { name: "Squad" });
    expect(screen.queryByRole("region", { name: "Players from other teams" })).not.toBeInTheDocument();
  });

  it("counts borrowed Players among the confirmed", async () => {
    const borrowed = [{ id: 9, name: "Lerato Nkosi", position: "outfield", kind: "player", joined_at: "2026-10-26T09:00:00Z" }];
    await openMatch(body({ is_captain: false, can_request: false }), squad({ confirmed: 2, borrowed }));

    const replies = await screen.findByRole("list", { name: "Squad replies" });
    expect(replies).toHaveTextContent("Confirmed · 2");
    expect(replies).toHaveTextContent("Lerato Nkosi (borrowed)");
  });
});

describe("RequestPlayerPage", () => {
  it("shows who will be asked and sends the request", async () => {
    const { calls, router } = await openAs(
      "/fixtures/30/players",
      {
        [DETAIL]: { status: 200, body: myFixture() },
        [PREVIEW]: previewByKind,
        [`POST ${REQUESTS}`]: { status: 201, body: body({ requests: [playerRequest()] }) },
        [SQUAD]: { status: 200, body: squad() },
        [`GET ${REQUESTS}`]: { status: 200, body: body({ requests: [playerRequest()] }) },
      },
      "Request a player",
    );
    expect(await screen.findByText("6 outfield Players will be asked")).toBeInTheDocument();
    expect(screen.getByText(/Only outfield Players on Tuesday who are in neither team/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Goalkeeper" }));
    expect(await screen.findByText("2 Goalkeepers will be asked")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "2" }));
    await userEvent.click(screen.getByRole("button", { name: "Ask for 2 goalkeepers" }));

    await screen.findByRole("heading", { name: "Match" });
    expect(router.state.location.pathname).toBe("/fixtures/30");
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ kind: "goalkeeper", places: 2 });
  });

  it("can't send when no one can be asked", async () => {
    await openAs(
      "/fixtures/30/players",
      {
        [DETAIL]: { status: 200, body: myFixture() },
        [PREVIEW]: { status: 200, body: { kind: "player", recipients: 0, night: "Tuesday", max_places: 5 } },
      },
      "Request a player",
    );

    expect(await screen.findByText("No outfield Players to ask")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask for a player" })).toBeDisabled();
  });

  it("shows the backend's refusal", async () => {
    await openAs(
      "/fixtures/30/players",
      {
        [DETAIL]: { status: 200, body: myFixture() },
        [PREVIEW]: previewByKind,
        [`POST ${REQUESTS}`]: {
          status: 409,
          body: { detail: "Old Boys already has an open request for players. Withdraw it to send a new one." },
        },
      },
      "Request a player",
    );
    await screen.findByText("6 outfield Players will be asked");
    await userEvent.click(screen.getByRole("button", { name: "Ask for a player" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("already has an open request");
  });
});

describe("MyFixturesPage: Games you can join", () => {
  const LIST = "GET /api/v1/me/fixtures/";

  it("lets a Player join a match from another team", async () => {
    const { calls } = await openAs(
      "/fixtures",
      {
        [LIST]: { status: 200, body: [] },
        [GAMES]: [
          { status: 200, body: [gameToJoin()] },
          { status: 200, body: [gameToJoin({ joined: true, can_answer: false, my_answer: "accept", places_left: 0, status: "filled" })] },
        ],
        "POST /api/v1/inbox/70/answer/": { status: 200, body: {} },
      },
      "My fixtures",
    );
    const games = await screen.findByRole("region", { name: "Games you can join" });
    expect(games).toHaveTextContent("Red Lions needs a goalkeeper");
    expect(games).toHaveTextContent("1 place left");
    expect(games).toHaveTextContent("Tue 27 Oct · Pitch 3");

    await userEvent.click(within(games).getByRole("button", { name: "Join match" }));

    expect(await screen.findByText("You're playing for Red Lions")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ answer: "accept" });
  });

  it("shows the refusal when someone else filled it first", async () => {
    await openAs(
      "/fixtures",
      {
        [LIST]: { status: 200, body: [] },
        [GAMES]: [{ status: 200, body: [gameToJoin()] }, { status: 200, body: [] }],
        "POST /api/v1/inbox/70/answer/": { status: 409, body: { detail: "Too late: this request has been filled." } },
      },
      "My fixtures",
    );
    const games = await screen.findByRole("region", { name: "Games you can join" });
    await userEvent.click(within(games).getByRole("button", { name: "Join match" }));

    await screen.findByRole("alert");
    expect(screen.getByRole("alert")).toHaveTextContent("Too late");
  });

  it("is hidden when there are no games", async () => {
    await openAs("/fixtures", { [LIST]: { status: 200, body: [] }, [GAMES]: { status: 200, body: [] } }, "My fixtures");

    await screen.findByText(/No fixtures for your Teams yet/);
    expect(screen.queryByRole("region", { name: "Games you can join" })).not.toBeInTheDocument();
  });
});
