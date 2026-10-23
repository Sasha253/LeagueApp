import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { currentTokens } from "../api/auth";
import { fakeApi, ME, TOKENS } from "../test/fakeApi";
import { renderApp } from "../test/renderApp";

const registered = { status: 201, body: { ...TOKENS, user: ME } };

async function answer(user: ReturnType<typeof userEvent.setup>, label: string, value: string) {
  if (value) await user.type(await screen.findByLabelText(label), value);
  await user.click(screen.getByRole("button", { name: "Next" }));
}

async function fillDetails(user: ReturnType<typeof userEvent.setup>) {
  await answer(user, "Email", "sipho@example.com");
  await answer(user, "Your name", "Sipho Dlamini");
  await answer(user, "Phone", "");
  await answer(user, "Password", "floodlit-pitch-19");
}

describe("SignUpPage", () => {
  it("asks one thing per step, then creates a Player and opens the profile", async () => {
    const { calls } = fakeApi({
      "POST /api/v1/auth/register/": registered,
      "GET /api/v1/nights/": { status: 200, body: [] },
    });
    const user = userEvent.setup();
    const router = renderApp("/signup");

    expect(await screen.findByText("Step 1 of 6")).toBeInTheDocument();
    await fillDetails(user);
    expect(screen.getByRole("button", { name: "I play" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("button", { name: "Create account" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Goalkeeper" }));
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("heading", { name: "Profile" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/profile");
    expect(calls[0]!.body).toEqual({
      email: "sipho@example.com",
      name: "Sipho Dlamini",
      phone: "",
      password: "floodlit-pitch-19",
      is_booking_user: false,
      player: { position: "goalkeeper" },
    });
    expect(currentTokens()).toEqual(TOKENS);
  });

  it("signs up a Booking User without a position step", async () => {
    const { calls } = fakeApi({
      "POST /api/v1/auth/register/": { status: 201, body: { ...TOKENS, user: { ...ME, player: null, is_booking_user: true } } },
      "GET /api/v1/nights/": { status: 200, body: [] },
    });
    const user = userEvent.setup();
    renderApp("/signup");

    await fillDetails(user);
    await user.click(screen.getByRole("button", { name: "I play" }));
    await user.click(screen.getByRole("button", { name: "I hire a field" }));
    expect(screen.getByText("Step 5 of 5")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("heading", { name: "Profile" })).toBeInTheDocument();
    expect(calls[0]!.body).toMatchObject({ is_booking_user: true, player: null });
  });

  it("needs at least one way of using the app", async () => {
    fakeApi({});
    const user = userEvent.setup();
    renderApp("/signup");

    await fillDetails(user);
    await user.click(screen.getByRole("button", { name: "I play" }));

    expect(screen.getByRole("button", { name: "Create account" })).toBeDisabled();
  });

  it("goes back to the step the server rejected and shows why", async () => {
    fakeApi({
      "POST /api/v1/auth/register/": {
        status: 400,
        body: { email: ["An account with this email already exists."] },
      },
    });
    const user = userEvent.setup();
    renderApp("/signup");

    await fillDetails(user);
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Both" }));
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("An account with this email already exists.")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Step 1 of 6")).toBeInTheDocument();
    expect(currentTokens()).toBeNull();
  });

  it("goes back a step and keeps the answer", async () => {
    fakeApi({});
    const user = userEvent.setup();
    renderApp("/signup");

    await answer(user, "Email", "sipho@example.com");
    await user.click(screen.getByRole("button", { name: "Back" }));

    expect(screen.getByLabelText("Email")).toHaveValue("sipho@example.com");
  });
});
