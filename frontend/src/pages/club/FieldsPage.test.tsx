import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { openAsAdmin } from "./testing";

const REFEREE = { id: 7, user_id: 40, name: "Thabo Ref", email: "ref@example.com", role: "referee" };
const ADMIN = { id: 6, user_id: 1, name: "Sipho Dlamini", email: "sipho@example.com", role: "admin" };
const PITCH = { id: 3, name: "Pitch 3", referee: 40, referee_name: "Thabo Ref" };
const FIELDS = "/api/v1/clubs/1/fields/";
const MEMBERS = { status: 200, body: [ADMIN, REFEREE] };

describe("FieldsPage", () => {
  it("lists the Fields with their Referees", async () => {
    await openAsAdmin(
      "/clubs/1/setup/fields",
      {
        [`GET ${FIELDS}`]: { status: 200, body: [PITCH, { id: 4, name: "Pitch 4", referee: null, referee_name: null }] },
        "GET /api/v1/clubs/1/members/": MEMBERS,
      },
      "Fields",
    );

    expect(await screen.findByText("Referee: Thabo Ref")).toBeInTheDocument();
    expect(screen.getByText("No Referee")).toBeInTheDocument();
  });

  it("adds a Field and picks only from the club's Referees", async () => {
    const { calls } = await openAsAdmin(
      "/clubs/1/setup/fields",
      {
        [`GET ${FIELDS}`]: [{ status: 200, body: [] }, { status: 200, body: [PITCH] }],
        [`POST ${FIELDS}`]: { status: 201, body: PITCH },
        "GET /api/v1/clubs/1/members/": MEMBERS,
      },
      "Fields",
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Add a Field" }));
    const form = screen.getByRole("form", { name: "New Field" });
    expect(within(form).queryByRole("button", { name: "Sipho Dlamini" })).not.toBeInTheDocument();
    await user.type(within(form).getByLabelText("Name"), "Pitch 3");
    await user.click(within(form).getByRole("button", { name: "Thabo Ref" }));
    await user.click(within(form).getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Referee: Thabo Ref")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ name: "Pitch 3", referee: 40 });
  });

  it("points to People when the club has no Referees", async () => {
    await openAsAdmin(
      "/clubs/1/setup/fields",
      {
        [`GET ${FIELDS}`]: { status: 200, body: [] },
        "GET /api/v1/clubs/1/members/": { status: 200, body: [ADMIN] },
      },
      "Fields",
    );

    await userEvent.click(await screen.findByRole("button", { name: "Add a Field" }));

    expect(screen.getByText("Invite a Referee in People first.")).toBeInTheDocument();
  });
});
