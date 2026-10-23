import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { openAsAdmin } from "./testing";

const ME_ADMIN = { id: 6, user_id: 1, name: "Sipho Dlamini", email: "sipho@example.com", role: "admin" };
const REFEREE = { id: 7, user_id: 40, name: "Thabo Ref", email: "ref@example.com", role: "referee" };
const INVITE = { id: 9, email: "new@example.com", role: "admin", created_at: "2026-10-23T10:00:00Z", accepted: false };
const MEMBERS = "/api/v1/clubs/1/members/";
const INVITES = "/api/v1/clubs/1/invites/";

describe("PeoplePage", () => {
  it("lists the Admins, Referees and open invites", async () => {
    await openAsAdmin(
      "/clubs/1/setup/people",
      {
        [`GET ${MEMBERS}`]: { status: 200, body: [ME_ADMIN, REFEREE] },
        [`GET ${INVITES}`]: { status: 200, body: [INVITE] },
      },
      "People",
    );

    const members = await screen.findByRole("region", { name: "Admins and Referees" });
    expect(within(members).getByText("Sipho Dlamini (you)")).toBeInTheDocument();
    expect(within(members).getByText("Referee · ref@example.com")).toBeInTheDocument();
    const invites = screen.getByRole("region", { name: "Invited, not signed up yet" });
    expect(within(invites).getByText("new@example.com")).toBeInTheDocument();
  });

  it("invites an email that has no account yet", async () => {
    const { calls } = await openAsAdmin(
      "/clubs/1/setup/people",
      {
        [`GET ${MEMBERS}`]: { status: 200, body: [ME_ADMIN] },
        [`GET ${INVITES}`]: [{ status: 200, body: [] }, { status: 200, body: [INVITE] }],
        [`POST ${INVITES}`]: { status: 201, body: INVITE },
      },
      "People",
    );
    const user = userEvent.setup();

    const form = await screen.findByRole("form", { name: "Invite" });
    await user.type(within(form).getByLabelText("Email"), "new@example.com");
    await user.click(within(form).getByRole("button", { name: "Admin" }));
    await user.click(within(form).getByRole("button", { name: "Send invite" }));

    expect(
      await screen.findByText("Invited new@example.com. They get the Admin role when they sign up with this email."),
    ).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ email: "new@example.com", role: "admin" });
  });

  it("says when an existing account got the role at once", async () => {
    await openAsAdmin(
      "/clubs/1/setup/people",
      {
        [`GET ${MEMBERS}`]: { status: 200, body: [ME_ADMIN] },
        [`GET ${INVITES}`]: { status: 200, body: [] },
        [`POST ${INVITES}`]: { status: 201, body: { ...INVITE, email: "ref@example.com", role: "referee", accepted: true } },
      },
      "People",
    );
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Email"), "ref@example.com");
    await user.click(screen.getByRole("button", { name: "Send invite" }));

    expect(await screen.findByText("ref@example.com now has the Referee role.")).toBeInTheDocument();
  });

  it("shows why the last Admin can't be removed", async () => {
    await openAsAdmin(
      "/clubs/1/setup/people",
      {
        [`GET ${MEMBERS}`]: { status: 200, body: [ME_ADMIN] },
        [`GET ${INVITES}`]: { status: 200, body: [] },
        [`DELETE ${MEMBERS}6/`]: { status: 409, body: { detail: "A club needs at least one Admin." } },
      },
      "People",
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Remove" }));
    await user.click(screen.getByRole("button", { name: "Remove Sipho Dlamini as Admin" }));

    expect(await screen.findByText("A club needs at least one Admin.")).toBeInTheDocument();
  });
});
