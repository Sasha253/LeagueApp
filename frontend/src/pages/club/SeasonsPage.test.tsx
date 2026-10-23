import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { openAsAdmin } from "./testing";

const SPRING = { id: 5, name: "Spring 2026", starts_on: "2026-08-04", ends_on: "2026-11-24" };
const LIST = "/api/v1/clubs/1/seasons/";

describe("SeasonsPage", () => {
  it("lists Seasons with their dates", async () => {
    await openAsAdmin("/clubs/1/setup/seasons", { [`GET ${LIST}`]: { status: 200, body: [SPRING] } }, "Seasons");

    expect(await screen.findByText("Spring 2026")).toBeInTheDocument();
    expect(screen.getByText("Tue 4 Aug to Tue 24 Nov")).toBeInTheDocument();
  });

  it("adds a Season", async () => {
    const { calls } = await openAsAdmin(
      "/clubs/1/setup/seasons",
      {
        [`GET ${LIST}`]: [{ status: 200, body: [] }, { status: 200, body: [SPRING] }],
        [`POST ${LIST}`]: { status: 201, body: SPRING },
      },
      "Seasons",
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Add a Season" }));
    const form = screen.getByRole("form", { name: "New Season" });
    await user.type(within(form).getByLabelText("Name"), "Spring 2026");
    await user.type(within(form).getByLabelText("Starts on"), "2026-08-04");
    await user.type(within(form).getByLabelText("Ends on"), "2026-11-24");
    await user.click(within(form).getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Spring 2026")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({
      name: "Spring 2026",
      starts_on: "2026-08-04",
      ends_on: "2026-11-24",
    });
  });

  it("shows the API's reason when a Season is refused", async () => {
    await openAsAdmin(
      "/clubs/1/setup/seasons",
      {
        [`GET ${LIST}`]: { status: 200, body: [SPRING] },
        [`PATCH ${LIST}5/`]: { status: 400, body: { ends_on: ["Must be on or after the start."] } },
      },
      "Seasons",
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Edit Spring 2026" }));
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Must be on or after the start.")).toBeInTheDocument();
  });

  it("deletes a Season only after asking", async () => {
    const { calls } = await openAsAdmin(
      "/clubs/1/setup/seasons",
      {
        [`GET ${LIST}`]: [{ status: 200, body: [SPRING] }, { status: 200, body: [] }],
        [`DELETE ${LIST}5/`]: { status: 204 },
      },
      "Seasons",
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Delete" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    await user.click(screen.getByRole("button", { name: "Delete Spring 2026" }));

    expect(await screen.findByText("No Seasons yet.")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "DELETE")).toHaveLength(1);
  });
});
