import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { currentTokens } from "../api/auth";
import { fakeApi, ME, TOKENS } from "../test/fakeApi";
import { renderApp } from "../test/renderApp";

async function logIn(email = "sipho@example.com", password = "floodlit-pitch-19") {
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Email"), email);
  await user.type(screen.getByLabelText("Password"), password);
  await user.click(screen.getByRole("button", { name: "Log in" }));
}

describe("LoginPage", () => {
  it("signs in and opens the profile", async () => {
    const { calls } = fakeApi({
      "POST /api/v1/auth/login/": { status: 200, body: TOKENS },
      "GET /api/v1/auth/me/": { status: 200, body: ME },
      "GET /api/v1/nights/": { status: 200, body: [] },
    });
    const router = renderApp("/login");

    await logIn();

    expect(await screen.findByRole("heading", { name: "Profile" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/profile");
    expect(calls[0]!.body).toEqual({ email: "sipho@example.com", password: "floodlit-pitch-19" });
    expect(currentTokens()).toEqual(TOKENS);
  });

  it("says so when the email and password don't match", async () => {
    fakeApi({ "POST /api/v1/auth/login/": { status: 401, body: { detail: "No active account" } } });
    renderApp("/login");

    await logIn();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "That email and password don't match an account.",
    );
    expect(currentTokens()).toBeNull();
  });

  it("says so when the API can't be reached", async () => {
    fakeApi({ "POST /api/v1/auth/login/": () => Promise.reject(new TypeError("Failed to fetch")) });
    renderApp("/login");

    await logIn();

    expect(await screen.findByRole("alert")).toHaveTextContent("Can't reach League App");
  });

  it("keeps Log in disabled until both fields are filled", async () => {
    fakeApi({});
    renderApp("/login");

    await userEvent.type(await screen.findByLabelText("Email"), "sipho@example.com");

    expect(screen.getByRole("button", { name: "Log in" })).toBeDisabled();
  });
});
