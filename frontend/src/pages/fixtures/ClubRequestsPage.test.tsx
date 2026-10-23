import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ADMIN_ME } from "../club/testing";
import { openAs } from "../teams/testing";
import { captainRequest, FIXTURE } from "./testing";

const LIST = "GET /api/v1/clubs/1/captain-requests/";

const clubRequest = (overrides: object = {}) => ({ ...captainRequest(overrides), fixture: FIXTURE });

describe("ClubRequestsPage", () => {
  it("lists the waiting requests with the match", async () => {
    const { calls } = await openAs(
      "/clubs/1/requests",
      { [LIST]: { status: 200, body: [clubRequest(), clubRequest({ id: 51, kind: "postpone", team: { id: 8, name: "Old Boys" } })] } },
      "Captain requests",
      ADMIN_ME,
    );

    const rows = within(await screen.findByRole("list", { name: "Requests" })).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Red Lions asks to cancel");
    expect(rows[0]).toHaveTextContent("Red Lions vs Old Boys · Tue 27 Oct · 19:40 · Pitch 3");
    expect(within(rows[0]!).getByRole("button", { name: "Accept: Red Lions out" })).toBeInTheDocument();
    expect(rows[1]).toHaveTextContent("Old Boys asks to postpone");
    expect(within(rows[1]!).getByRole("link", { name: "Pick the new time" })).toHaveAttribute("href", "/clubs/1/fixtures/30");
    expect(calls.find((c) => c.path === "/api/v1/clubs/1/captain-requests/")).toBeTruthy();
  });

  it("accepts a cancellation and reloads", async () => {
    const { calls } = await openAs(
      "/clubs/1/requests",
      {
        [LIST]: [
          { status: 200, body: [clubRequest()] },
          { status: 200, body: [] },
        ],
        "POST /api/v1/clubs/1/captain-requests/50/accept/": { status: 200, body: clubRequest({ status: "accepted" }) },
      },
      "Captain requests",
      ADMIN_ME,
    );

    await userEvent.click(await screen.findByRole("button", { name: "Accept: Red Lions out" }));

    expect(await screen.findByText("No Captain is waiting for an answer.")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(1);
  });

  it("declines and shows a refusal", async () => {
    await openAs(
      "/clubs/1/requests",
      {
        [LIST]: { status: 200, body: [clubRequest()] },
        "POST /api/v1/clubs/1/captain-requests/50/decline/": {
          status: 409,
          body: { detail: "This request has already been withdrawn." },
        },
      },
      "Captain requests",
      ADMIN_ME,
    );

    await userEvent.click(await screen.findByRole("button", { name: "Decline" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("already been withdrawn");
  });

  it("shows every request under All", async () => {
    await openAs(
      "/clubs/1/requests",
      { [LIST]: { status: 200, body: [clubRequest({ status: "accepted", decided_at: "2026-10-26T09:00:00Z", decided_by_name: "Ada Admin" })] } },
      "Captain requests",
      ADMIN_ME,
    );

    await userEvent.click(screen.getByRole("button", { name: "All" }));

    const list = await screen.findByRole("list", { name: "Requests" });
    expect(list).toHaveTextContent("Accepted Mon 26 Oct · 11:00 by Ada Admin");
    expect(within(list).queryByRole("button")).not.toBeInTheDocument();
  });
});
