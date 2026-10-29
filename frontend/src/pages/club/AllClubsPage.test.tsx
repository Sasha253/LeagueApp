import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { setTokens } from "../../api/auth";
import { fakeApi, ME, TOKENS, type Routes } from "../../test/fakeApi";
import { renderApp } from "../../test/renderApp";
import { SETTINGS } from "./testing";

const ROOT_ME = { ...ME, is_superuser: true };
const CLUBS = [
  { id: 1, name: "Club A" },
  { id: 2, name: "Club B" },
];

async function open(path: string, routes: Routes, heading: string, me: object = ROOT_ME) {
  await setTokens(TOKENS);
  const api = fakeApi({ "GET /api/v1/auth/me/": { status: 200, body: me }, ...routes });
  const router = renderApp(path);
  await screen.findByRole("heading", { name: heading });
  return { ...api, router };
}

describe("AllClubsPage", () => {
  it("lists every club, each opening its Club home", async () => {
    const { router } = await open("/clubs", { "GET /api/v1/clubs/": { status: 200, body: CLUBS } }, "All clubs");

    const clubB = (await screen.findByText("Club B")).closest("li")!;
    expect(screen.getByText("Club A")).toBeInTheDocument();
    expect(within(clubB).getByRole("link", { name: "Scan at Club B" })).toHaveAttribute("href", "/clubs/2/scan");
    expect(screen.getByRole("link", { name: "Add a club" })).toHaveAttribute("href", "/clubs/new");

    await userEvent.click(within(clubB).getByRole("link", { name: "Open Club B" }));
    expect(router.state.location.pathname).toBe("/clubs/2");
  });

  it("says so when there are no clubs yet", async () => {
    await open("/clubs", { "GET /api/v1/clubs/": { status: 200, body: [] } }, "All clubs");

    expect(await screen.findByText("No clubs yet.")).toBeInTheDocument();
  });

  it("says so when the user isn't a superuser", async () => {
    await open("/clubs", { "GET /api/v1/clubs/": { status: 403, body: { detail: "No." } } }, "All clubs", ME);

    expect(await screen.findByText("Only a superuser can see every club.")).toBeInTheDocument();
  });

  it("names a club the superuser holds no role at in its screens", async () => {
    const { calls } = await open(
      "/clubs/2/setup",
      {
        "GET /api/v1/clubs/2/": { status: 200, body: { id: 2, name: "Club B" } },
        "GET /api/v1/clubs/2/settings/": { status: 200, body: SETTINGS },
      },
      "Club setup",
    );

    expect(await screen.findByText("Club B")).toBeInTheDocument();
    expect(calls.some((call) => call.method === "GET" && call.path === "/api/v1/clubs/2/")).toBe(true);
  });
});
