import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { currentTokens, setTokens } from "../api/auth";
import { fakeApi, ME, TOKENS } from "../test/fakeApi";
import { renderApp } from "../test/renderApp";

const NIGHTS = [
  { id: 11, club: { id: 1, name: "Club A" }, weekday: 1 },
  { id: 12, club: { id: 1, name: "Club A" }, weekday: 3 },
  { id: 21, club: { id: 2, name: "Club B" }, weekday: 4 },
];

async function openProfile(me: object = ME, nights: unknown = { status: 200, body: NIGHTS }) {
  await setTokens(TOKENS);
  const api = fakeApi({
    "GET /api/v1/auth/me/": { status: 200, body: me },
    "GET /api/v1/nights/": nights as never,
    "PATCH /api/v1/auth/me/": (request) =>
      request.json().then((body) => Response.json({ ...me, ...body })),
    "POST /api/v1/auth/logout/": { status: 200, body: {} },
    "GET /api/v1/inbox/summary/": { status: 200, body: { unread: 3, needs_reply: 1 } },
  });
  const router = renderApp("/profile");
  await screen.findByRole("heading", { name: "Profile" });
  return { ...api, router };
}

describe("ProfilePage", () => {
  it("opens All clubs for a superuser only", async () => {
    await openProfile({ ...ME, is_superuser: true });
    expect(screen.getByRole("link", { name: /All clubs/ })).toHaveAttribute("href", "/clubs");
  });

  it("has no All clubs for anyone else", async () => {
    await openProfile();
    expect(screen.queryByRole("link", { name: /All clubs/ })).not.toBeInTheDocument();
  });

  it("opens the Inbox, with how many are unread", async () => {
    await openProfile();

    const inbox = screen.getByRole("link", { name: /Inbox/ });
    expect(inbox).toHaveAttribute("href", "/inbox");
    expect(await within(inbox).findByText("3 unread")).toBeInTheDocument();
  });

  it("links the privacy policy and shows the app version and build", async () => {
    await openProfile();

    expect(screen.getByRole("link", { name: "Privacy policy" })).toHaveAttribute("href", "/privacy");
    expect(screen.getByText(/Version 1\.0\.0 \(1\)/)).toBeInTheDocument();
  });

  it("sends a signed-out visitor to Log in", async () => {
    fakeApi({});
    const router = renderApp("/profile");

    expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/login");
  });

  it("shows the Player's position and Nights by club", async () => {
    await openProfile({ ...ME, player: { position: "outfield", nights: [12] } });

    expect(screen.getByRole("button", { name: "Outfield" })).toHaveAttribute("aria-pressed", "true");
    expect(await screen.findByRole("button", { name: "Thu at Club A" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Tue at Club A" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "Fri at Club B" })).toBeInTheDocument();
  });

  it("saves a new position and Night opt-ins", async () => {
    const { calls } = await openProfile();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Both" }));
    await user.click(await screen.findByRole("button", { name: "Tue at Club A" }));
    await user.click(screen.getByRole("button", { name: "Fri at Club B" }));
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Saved")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "PATCH")!.body).toEqual({
      is_booking_user: false,
      player: { position: "both", nights: [11, 21] },
    });
  });

  it("lists the roles held at each club", async () => {
    await openProfile({
      ...ME,
      club_roles: [{ club_id: 1, club_name: "Club A", role: "admin" }],
    });

    const roles = screen.getByRole("region", { name: "At your clubs" });
    expect(within(roles).getByText("Admin")).toBeInTheDocument();
    expect(within(roles).getByText("Club A")).toBeInTheDocument();
  });

  it("opens Club home for an Admin, and not for a Referee", async () => {
    const { router } = await openProfile({
      ...ME,
      club_roles: [
        { club_id: 1, club_name: "Club A", role: "admin" },
        { club_id: 2, club_name: "Club B", role: "referee" },
      ],
    });

    expect(screen.queryByRole("link", { name: "Open Club B" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: "Open Club A" }));

    expect(router.state.location.pathname).toBe("/clubs/1");
  });

  it("links Admins and Referees to the club's gate scanner, and nobody else", async () => {
    await openProfile({
      ...ME,
      club_roles: [
        { club_id: 1, club_name: "Club A", role: "admin" },
        { club_id: 2, club_name: "Club B", role: "referee" },
      ],
    });

    expect(screen.getByRole("link", { name: "Scan at Club A" })).toHaveAttribute("href", "/clubs/1/scan");
    expect(screen.getByRole("link", { name: "Scan at Club B" })).toHaveAttribute("href", "/clubs/2/scan");
  });

  it("gives a Player no gate scanner", async () => {
    await openProfile();
    expect(screen.queryByRole("link", { name: /^Scan at/ })).not.toBeInTheDocument();
  });

  it("links a Player to their fixtures", async () => {
    await openProfile();
    expect(screen.getByRole("link", { name: /^My fixtures/ })).toHaveAttribute("href", "/fixtures");
  });

  it("links a Player to Teams", async () => {
    await openProfile();
    expect(screen.getByRole("link", { name: /^Teams/ })).toHaveAttribute("href", "/teams");
  });

  it("has no Teams link for someone who only hires fields", async () => {
    await openProfile({ ...ME, player: null, is_booking_user: true });
    expect(screen.queryByRole("link", { name: /^Teams/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^My fixtures/ })).not.toBeInTheDocument();
  });

  it("hides position and Nights for someone who only hires fields", async () => {
    await openProfile({ ...ME, player: null, is_booking_user: true });

    expect(screen.queryByText("Position")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "I hire a field" })).toHaveAttribute("aria-pressed", "true");
  });

  it("can't save with no way of using the app", async () => {
    await openProfile();

    await userEvent.click(screen.getByRole("button", { name: "I play" }));

    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("shows the empty state when no club has Nights yet", async () => {
    await openProfile(ME, { status: 200, body: [] });

    expect(await screen.findByText("No Nights yet. Your club adds them.")).toBeInTheDocument();
  });

  it("offers Retry when the Nights can't load", async () => {
    await openProfile(ME, { status: 500 });

    expect(await screen.findByText("Couldn't load the Nights")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("logs out and forgets the tokens", async () => {
    const { calls, router } = await openProfile();

    await userEvent.click(screen.getByRole("button", { name: "Log out" }));

    expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/login");
    expect(calls.find((c) => c.path === "/api/v1/auth/logout/")!.body).toEqual({ refresh: "refresh-1" });
    expect(currentTokens()).toBeNull();
  });
});
