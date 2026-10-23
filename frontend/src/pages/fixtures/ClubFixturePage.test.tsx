import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ADMIN_ME } from "../club/testing";
import { openAs } from "../teams/testing";
import { adminFixture, replacement } from "./testing";

const DETAIL = "/api/v1/clubs/1/fixtures/30/";

describe("ClubFixturePage", () => {
  it("shows the match, its pitch and Referee, and its history", async () => {
    const fixture = adminFixture({
      status: "cancelled",
      transitions: [
        ...adminFixture().transitions,
        {
          id: 2,
          from_status: "scheduled",
          to_status: "confirming",
          at: "2026-10-26T05:40:00Z",
          cause: "checkpoint",
          actor_name: null,
          note: "",
        },
        {
          id: 3,
          from_status: "confirming",
          to_status: "cancelled",
          at: "2026-10-27T10:00:00Z",
          cause: "admin",
          actor_name: "Ada Admin",
          note: "Pitch flooded",
        },
      ],
    });
    await openAs("/clubs/1/fixtures/30", { [`GET ${DETAIL}`]: { status: 200, body: fixture } }, "Fixture", ADMIN_ME);

    expect(await screen.findByRole("article", { name: "Red Lions vs Old Boys" })).toHaveTextContent("19:40");
    expect(screen.getByText("Referee: Rita Referee")).toBeInTheDocument();
    const history = within(screen.getByRole("list", { name: "History" })).getAllByRole("listitem");
    expect(history[0]).toHaveTextContent("Added as scheduled");
    expect(history[0]).toHaveTextContent("Tue 20 Oct · 10:00 · Ada Admin (Fixture import)");
    expect(history[1]).toHaveTextContent("Scheduled to Confirming");
    expect(history[1]).toHaveTextContent("Mon 26 Oct · 07:40 · Timed checkpoint");
    expect(history[2]).toHaveTextContent("Confirming to Cancelled");
    expect(history[2]).toHaveTextContent("Pitch flooded");
  });

  it("marks the match friendly-eligible", async () => {
    const marked = adminFixture({
      friendly_eligible: true,
      friendly_eligible_changed_by_name: "Ada Admin",
      friendly_eligible_changed_at: "2026-10-23T08:00:00Z",
    });
    const { calls } = await openAs(
      "/clubs/1/fixtures/30",
      {
        [`GET ${DETAIL}`]: [
          { status: 200, body: adminFixture() },
          { status: 200, body: marked },
        ],
        [`PATCH ${DETAIL}`]: { status: 200, body: marked },
      },
      "Fixture",
      ADMIN_ME,
    );
    const chip = await screen.findByRole("button", { name: "Friendly-eligible", pressed: false });

    await userEvent.click(chip);

    expect(await screen.findByRole("button", { name: "Friendly-eligible", pressed: true })).toBeInTheDocument();
    expect(screen.getByText("Set Fri 23 Oct · 10:00 by Ada Admin")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ friendly_eligible: true });
  });

  it("shows why the flag can't change any more", async () => {
    await openAs(
      "/clubs/1/fixtures/30",
      {
        [`GET ${DETAIL}`]: { status: 200, body: adminFixture({ status: "played" }) },
        [`PATCH ${DETAIL}`]: {
          status: 409,
          body: { detail: "This Fixture is played, so whether it may become a friendly can't change now." },
        },
      },
      "Fixture",
      ADMIN_ME,
    );

    await userEvent.click(await screen.findByRole("button", { name: "Friendly-eligible" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("can't change now");
  });

  it("shows nothing about a new opponent while no Team is out", async () => {
    await openAs("/clubs/1/fixtures/30", { [`GET ${DETAIL}`]: { status: 200, body: adminFixture() } }, "Fixture", ADMIN_ME);

    await screen.findByRole("article", { name: "Red Lions vs Old Boys" });
    expect(screen.queryByRole("list", { name: "New opponent" })).not.toBeInTheDocument();
  });

  it("shows who the slot is offered to and until when", async () => {
    const fixture = adminFixture({ status: "replacement_offered", replacements: [replacement()] });
    await openAs("/clubs/1/fixtures/30", { [`GET ${DETAIL}`]: { status: 200, body: fixture } }, "Fixture", ADMIN_ME);

    const row = within(await screen.findByRole("list", { name: "New opponent" })).getByRole("listitem");
    expect(row).toHaveTextContent("Red Lions out");
    expect(row).toHaveTextContent("Offered to Blue Bulls, Green Geckos until Tue 27 Oct · 17:40.");
    expect(row).toHaveTextContent("Status: Offered");
  });

  it("shows which Team took the slot, and a search no Team answered", async () => {
    const fixture = adminFixture({
      status: "ready",
      home_team: { id: 11, name: "Blue Bulls" },
      replacements: [
        replacement({ id: 3, status: "lapsed", offered_to: [] }),
        replacement({
          status: "accepted",
          accepted_team: { id: 11, name: "Blue Bulls" },
          accepted_by_name: "Bongi",
          accepted_at: "2026-10-27T13:00:00Z",
        }),
      ],
    });
    await openAs("/clubs/1/fixtures/30", { [`GET ${DETAIL}`]: { status: 200, body: fixture } }, "Fixture", ADMIN_ME);

    const rows = within(await screen.findByRole("list", { name: "New opponent" })).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("No other Team could take the slot.");
    expect(rows[0]).toHaveTextContent("Status: No Team took it");
    expect(rows[1]).toHaveTextContent("Blue Bulls took the slot (Bongi), Tue 27 Oct · 15:00.");
    expect(rows[1]).toHaveTextContent("Status: Taken");
  });
});
