import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ME } from "../../test/fakeApi";
import { openAs } from "../teams/testing";

const ROOT = { ...ME, is_superuser: true };

async function fillIn() {
  await userEvent.type(screen.getByLabelText("Club name"), "Floodlight Park");
  await userEvent.type(screen.getByLabelText("First Admin's email"), "boss@example.com");
  await userEvent.click(screen.getByRole("button", { name: "Add club" }));
}

describe("AddClubPage", () => {
  it("adds the club with its first Admin and opens its home", async () => {
    const { calls, router } = await openAs(
      "/clubs/new",
      {
        "POST /api/v1/clubs/": { status: 201, body: { id: 3, name: "Floodlight Park" } },
        "GET /api/v1/clubs/3/": { status: 200, body: { id: 3, name: "Floodlight Park" } },
        "GET /api/v1/clubs/3/seasons/": { status: 200, body: [] },
      },
      "Add a club",
      ROOT,
    );

    await fillIn();

    expect(calls.find((call) => call.method === "POST")?.body).toEqual({
      name: "Floodlight Park",
      admin_email: "boss@example.com",
    });
    expect(router.state.location.pathname).toBe("/clubs/3");
  });

  it("says when the name is taken", async () => {
    await openAs(
      "/clubs/new",
      { "POST /api/v1/clubs/": { status: 400, body: { name: ["A club with this name already exists."] } } },
      "Add a club",
      ROOT,
    );

    await fillIn();

    expect(await screen.findByText("A club with this name already exists.")).toBeInTheDocument();
  });

  it("refuses anyone but a superuser", async () => {
    await openAs("/clubs/new", { "POST /api/v1/clubs/": { status: 403, body: { detail: "No." } } }, "Add a club");

    await fillIn();

    expect(await screen.findByText("Only a superuser can add a club.")).toBeInTheDocument();
  });
});
