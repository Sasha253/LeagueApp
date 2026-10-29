import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { currentTokens, loadAdminTokens, setTokens } from "../api/auth";
import { fakeApi, ME, TOKENS, type Routes } from "../test/fakeApi";
import { renderApp } from "../test/renderApp";

const ROOT_ME = { ...ME, name: "Root", is_superuser: true };
const TESTERS = [
  { id: 7, name: "Test Admin (Club A)", email: "admin.club1@test.invalid", roles: ["Admin at Club A"] },
  {
    id: 9,
    name: "Test Goalkeeper (Club A)",
    email: "keeper.club1@test.invalid",
    roles: ["Player (goalkeeper)"],
  },
];
const ADMIN_ME = {
  ...ME,
  id: 7,
  name: "Test Admin (Club A)",
  email: "admin.club1@test.invalid",
  player: null,
  club_roles: [{ club_id: 1, club_name: "Club A", role: "admin" as const }],
  is_test_account: true,
};
const TEST_TOKENS = { access: "test-access", refresh: "test-refresh" };

async function open(routes: Routes, me: object = ROOT_ME) {
  await setTokens(TOKENS);
  const api = fakeApi({
    "GET /api/v1/auth/me/": { status: 200, body: me },
    "GET /api/v1/inbox/summary/": { status: 200, body: { unread: 0 } },
    "GET /api/v1/nights/": { status: 200, body: [] },
    ...routes,
  });
  const router = renderApp("/test-users");
  await screen.findByRole("heading", { name: "Log in as" });
  return { ...api, router };
}

describe("TestUsersPage", () => {
  it("lists the test users with their roles", async () => {
    await open({ "GET /api/v1/auth/test-users/": { status: 200, body: TESTERS } });

    expect(await screen.findByText("Test Admin (Club A)")).toBeInTheDocument();
    expect(screen.getByText("Player (goalkeeper)")).toBeInTheDocument();
  });

  it("signs in as a test user, and goes back to the superuser", async () => {
    const { calls, router } = await open({
      "GET /api/v1/auth/test-users/": { status: 200, body: TESTERS },
      "POST /api/v1/auth/test-users/7/login/": { status: 200, body: { ...TEST_TOKENS, user: ADMIN_ME } },
      "POST /api/v1/auth/logout/": { status: 200, body: {} },
    });

    await userEvent.click(await screen.findByRole("button", { name: "Log in as Test Admin (Club A)" }));

    expect(await screen.findByText("Signed in as Test Admin (Club A)")).toBeInTheDocument();
    expect(await screen.findByText("At your clubs")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/profile");
    expect(currentTokens()).toEqual(TEST_TOKENS);
    expect(await loadAdminTokens()).toEqual(TOKENS);

    await userEvent.click(screen.getByRole("button", { name: "Back to superuser" }));

    await screen.findByRole("link", { name: /Log in as/ });
    expect(screen.queryByText(/Signed in as/)).not.toBeInTheDocument();
    expect(currentTokens()).toEqual(TOKENS);
    expect(await loadAdminTokens()).toBeNull();
    const logout = calls.find((call) => call.path === "/api/v1/auth/logout/");
    expect(logout?.body).toEqual({ refresh: TEST_TOKENS.refresh });
  });

  it("logging out as a test user ends the superuser's session too", async () => {
    const { calls } = await open({
      "GET /api/v1/auth/test-users/": { status: 200, body: TESTERS },
      "POST /api/v1/auth/test-users/7/login/": { status: 200, body: { ...TEST_TOKENS, user: ADMIN_ME } },
      "POST /api/v1/auth/logout/": { status: 200, body: {} },
    });

    await userEvent.click(await screen.findByRole("button", { name: "Log in as Test Admin (Club A)" }));
    await userEvent.click(await screen.findByRole("button", { name: "Log out" }));

    await screen.findByRole("button", { name: "Log in" });
    const loggedOut = calls.filter((call) => call.path === "/api/v1/auth/logout/").map((call) => call.body);
    expect(loggedOut).toEqual([{ refresh: TEST_TOKENS.refresh }, { refresh: TOKENS.refresh }]);
    expect(currentTokens()).toBeNull();
    expect(await loadAdminTokens()).toBeNull();
  });

  it("says so when signing in as a test user fails", async () => {
    await open({
      "GET /api/v1/auth/test-users/": { status: 200, body: TESTERS },
      "POST /api/v1/auth/test-users/9/login/": { status: 404, body: { detail: "Not found." } },
    });

    await userEvent.click(await screen.findByRole("button", { name: "Log in as Test Goalkeeper (Club A)" }));

    expect(await screen.findByText("Couldn't sign in as Test Goalkeeper (Club A)")).toBeInTheDocument();
    expect(currentTokens()).toEqual(TOKENS);
  });

  it("says so when there are no test users", async () => {
    await open({ "GET /api/v1/auth/test-users/": { status: 200, body: [] } });

    expect(await screen.findByText("No test users yet. Add them with make_test_users.")).toBeInTheDocument();
  });

  it("says so when the user isn't a superuser", async () => {
    await open({ "GET /api/v1/auth/test-users/": { status: 403, body: { detail: "No." } } }, ME);

    expect(await screen.findByText("Only a superuser can sign in as a test user.")).toBeInTheDocument();
  });
});
