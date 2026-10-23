import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ADMIN_ME } from "../club/testing";
import { openAs } from "../teams/testing";
import { clubBooking } from "./testing";

const LIST = "GET /api/v1/clubs/1/bookings/";

describe("ClubBookingsPage", () => {
  it("lists the waiting bookings with who booked", async () => {
    await openAs("/clubs/1/bookings", { [LIST]: { status: 200, body: [clubBooking()] } }, "Bookings", ADMIN_ME);

    const row = within(await screen.findByRole("list", { name: "Bookings" })).getByRole("listitem");
    expect(row).toHaveTextContent("Hannah Hirer · Pitch 3");
    expect(row).toHaveTextContent("Tue 27 Oct · 18:00 to 20:00 · 2 hours");
    expect(row).toHaveTextContent("R 600 × 2 h = R 1,200 · 082 555 0101 · hirer@example.com");
  });

  it("accepts and reloads", async () => {
    const { calls } = await openAs(
      "/clubs/1/bookings",
      {
        [LIST]: [
          { status: 200, body: [clubBooking()] },
          { status: 200, body: [] },
        ],
        "POST /api/v1/clubs/1/bookings/70/accept/": { status: 200, body: clubBooking({ status: "accepted" }) },
      },
      "Bookings",
      ADMIN_ME,
    );

    await userEvent.click(await screen.findByRole("button", { name: "Accept" }));

    expect(await screen.findByText("No booking is waiting for an answer.")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(1);
  });

  it("declines with a reason", async () => {
    const { calls } = await openAs(
      "/clubs/1/bookings",
      {
        [LIST]: { status: 200, body: [clubBooking()] },
        "POST /api/v1/clubs/1/bookings/70/decline/": { status: 200, body: clubBooking({ status: "declined" }) },
      },
      "Bookings",
      ADMIN_ME,
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Decline" }));
    await user.type(screen.getByLabelText("Reason (optional)"), "Pitch resurfacing.");
    await user.click(screen.getByRole("button", { name: "Decline booking" }));

    await screen.findByRole("list", { name: "Bookings" });
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ reason: "Pitch resurfacing." });
  });

  it("shows a refusal", async () => {
    await openAs(
      "/clubs/1/bookings",
      {
        [LIST]: { status: 200, body: [clubBooking()] },
        "POST /api/v1/clubs/1/bookings/70/accept/": {
          status: 409,
          body: { detail: "A league match is on this field for some of that time." },
        },
      },
      "Bookings",
      ADMIN_ME,
    );

    await userEvent.click(await screen.findByRole("button", { name: "Accept" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("league match");
  });

  it("asks for every booking under All", async () => {
    const { calls } = await openAs(
      "/clubs/1/bookings",
      { [LIST]: { status: 200, body: [clubBooking({ status: "declined", can_decide: false })] } },
      "Bookings",
      ADMIN_ME,
    );

    await userEvent.click(await screen.findByRole("button", { name: "All" }));

    expect(await screen.findByText("Declined")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Accept" })).not.toBeInTheDocument();
    expect(calls.filter((c) => c.path === "/api/v1/clubs/1/bookings/").length).toBe(2);
  });
});
