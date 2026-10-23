import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { openAs } from "../teams/testing";
import { BOOKER, booking, bookingBarcode, FREE, outcome } from "./testing";

const ONE = "GET /api/v1/me/bookings/70/";
const BARCODE = "GET /api/v1/me/bookings/70/barcode/";
const OUTCOME = "GET /api/v1/me/bookings/70/outcome/";

describe("MyBookingsPage", () => {
  it("lists bookings coming up and before", async () => {
    await openAs(
      "/bookings",
      {
        "GET /api/v1/me/bookings/": {
          status: 200,
          body: [booking(), booking({ id: 71, status: "accepted", is_over: true })],
        },
      },
      "My bookings",
      BOOKER,
    );

    const coming = await screen.findByRole("list", { name: "Coming up" });
    expect(within(coming).getByRole("link")).toHaveAttribute("href", "/bookings/70");
    expect(coming).toHaveTextContent("Pitch 3 · Club A");
    expect(coming).toHaveTextContent("Waiting for the club");
    expect(screen.getByRole("list", { name: "Before" })).toHaveTextContent("Accepted");
    expect(screen.getByRole("link", { name: "Book a field" })).toHaveAttribute("href", "/book");
  });
});

describe("BookingPage", () => {
  it("says a waiting booking needs the club", async () => {
    await openAs("/bookings/70", { [ONE]: { status: 200, body: booking() } }, "Booking", BOOKER);

    expect(await screen.findByText("Waiting for the club", { selector: ".la-banner__title" })).toBeInTheDocument();
    expect(screen.getByText("R 600 × 2 h")).toBeInTheDocument();
    expect(screen.getByText("R 1,200")).toBeInTheDocument();
  });

  it("shows the entry Barcode once accepted, and why it doesn't count yet", async () => {
    await openAs(
      "/bookings/70",
      {
        [ONE]: { status: 200, body: booking({ status: "accepted" }) },
        [BARCODE]: {
          status: 200,
          body: { state: "unpaid", reason: "The booking still owes R 1,200.", barcode: bookingBarcode() },
        },
      },
      "Booking",
      BOOKER,
    );

    const ticket = await screen.findByRole("region", { name: "Payment Barcode" });
    expect(within(ticket).getByText("Pitch 3 · 2 h")).toBeInTheDocument();
    expect(within(ticket).getByText("Accepted · not paid yet")).toBeInTheDocument();
    expect(within(ticket).getByText("BK 2410 0815")).toBeInTheDocument();
    expect(screen.getByText("The booking still owes R 1,200.")).toBeInTheDocument();
  });

  it("shows a valid Barcode as paid", async () => {
    await openAs(
      "/bookings/70",
      {
        [ONE]: { status: 200, body: booking({ status: "accepted" }) },
        [BARCODE]: { status: 200, body: { state: "valid", reason: "", barcode: bookingBarcode() } },
      },
      "Booking",
      BOOKER,
    );

    expect(await screen.findByText("Paid · valid for this booking only")).toBeInTheDocument();
  });

  it("cancels after asking once more", async () => {
    const { calls } = await openAs(
      "/bookings/70",
      {
        [ONE]: { status: 200, body: booking() },
        [OUTCOME]: { status: 200, body: outcome() },
        "POST /api/v1/me/bookings/70/cancel/": {
          status: 200,
          body: booking({ status: "cancelled", can_cancel: false, can_reschedule: false }),
        },
      },
      "Booking",
      BOOKER,
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Cancel booking" }));
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Yes, cancel it" }));

    expect(await screen.findByText("Cancelled")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel booking" })).not.toBeInTheDocument();
  });

  it("reschedules to a free time", async () => {
    const { calls } = await openAs(
      "/bookings/70",
      {
        [ONE]: { status: 200, body: booking() },
        [OUTCOME]: { status: 200, body: outcome() },
        "GET /api/v1/bookings/availability/": { status: 200, body: FREE },
        "POST /api/v1/me/bookings/70/reschedule/": {
          status: 200,
          body: booking({ starts_at: "2026-10-27T19:00:00Z", ends_at: "2026-10-27T21:00:00Z" }),
        },
      },
      "Booking",
      BOOKER,
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Reschedule" }));
    await user.click(await screen.findByRole("button", { name: "21:00" }));
    await user.click(screen.getByRole("button", { name: "Move my booking" }));

    expect(await screen.findByText("Tue 27 Oct · 21:00 to 23:00")).toBeInTheDocument();
    const asked = calls.find((c) => c.path === "/api/v1/bookings/availability/");
    expect(asked).toBeTruthy();
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({
      field: 3,
      starts_at: "2026-10-27T19:00:00Z",
      hours: 2,
    });
  });

  it("shows the club's reason for declining", async () => {
    await openAs(
      "/bookings/70",
      {
        [ONE]: {
          status: 200,
          body: booking({ status: "declined", decline_reason: "Pitch resurfacing.", can_cancel: false, can_reschedule: false }),
        },
      },
      "Booking",
      BOOKER,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Pitch resurfacing.");
  });
});
