import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { fakeApi } from "../../test/fakeApi";
import { renderApp } from "../../test/renderApp";

const PRIVACY = "GET /api/v1/legal/privacy/";

const policy = (overrides: object = {}) => ({
  title: "Privacy policy",
  updated_on: "2026-10-24",
  operator: "Floodlit Leagues (Pty) Ltd",
  contact_email: "privacy@example.com",
  sections: [
    { heading: "Who we are", paragraphs: ["Floodlit Leagues (Pty) Ltd runs League App."] },
    {
      heading: "What we never keep",
      paragraphs: ["Card details. Card payments go straight to PayFast.", "Camera images."],
    },
  ],
  ...overrides,
});

describe("PrivacyPage", () => {
  it("shows the policy from the API without signing in", async () => {
    const { calls } = fakeApi({ [PRIVACY]: { status: 200, body: policy() } });
    renderApp("/privacy");

    expect(await screen.findByRole("heading", { name: "What we never keep" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Privacy policy", level: 1 })).toBeInTheDocument();
    expect(
      screen.getByText("League App, run by Floodlit Leagues (Pty) Ltd. Last updated Sat 24 Oct 2026."),
    ).toBeInTheDocument();
    expect(screen.getByText("Card details. Card payments go straight to PayFast.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "privacy@example.com" })).toHaveAttribute(
      "href",
      "mailto:privacy@example.com",
    );
    expect(screen.getByText("Version 1.0.0 (1)")).toBeInTheDocument();
    expect(calls.find((c) => c.path === "/api/v1/legal/privacy/")?.auth).toBeNull();
  });

  it("leaves out the email line when there is no contact address", async () => {
    fakeApi({ [PRIVACY]: { status: 200, body: policy({ contact_email: "" }) } });
    renderApp("/privacy");

    await screen.findByRole("heading", { name: "Who we are" });
    expect(screen.queryByText(/Privacy questions and requests/)).not.toBeInTheDocument();
  });

  it("offers Retry when the policy can't load", async () => {
    fakeApi({ [PRIVACY]: [{ status: 500 }, { status: 200, body: policy() }] });
    const user = userEvent.setup();
    renderApp("/privacy");

    await user.click(await screen.findByRole("button", { name: "Retry" }));

    expect(await screen.findByRole("heading", { name: "Who we are" })).toBeInTheDocument();
  });

  it("opened directly, leads to the start of the app", async () => {
    fakeApi({ [PRIVACY]: { status: 200, body: policy() } });
    renderApp("/privacy");

    expect(await screen.findByRole("link", { name: "League App" })).toHaveAttribute("href", "/");
  });

  it("is linked from Sign up, and Back returns there", async () => {
    fakeApi({ [PRIVACY]: { status: 200, body: policy() }, "GET /api/v1/nights/": { status: 200, body: [] } });
    const user = userEvent.setup();
    const router = renderApp("/signup");

    await user.click(await screen.findByRole("link", { name: "privacy policy" }));
    await screen.findByRole("heading", { name: "Who we are" });
    await user.click(screen.getByRole("button", { name: "Back" }));

    expect(router.state.location.pathname).toBe("/signup");
  });
});
