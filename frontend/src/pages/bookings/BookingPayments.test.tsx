import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { openAs } from "../teams/testing";
import { BOOKER, booking, bookingBarcode, clubBooking, outcome } from "./testing";

vi.mock("../../native/browser", () => ({ openCheckout: vi.fn(async () => true) }));
const { openCheckout } = await import("../../native/browser");

beforeEach(() => vi.mocked(openCheckout).mockClear());

const ONE = "GET /api/v1/me/bookings/70/";
const OUTCOME = "GET /api/v1/me/bookings/70/outcome/";
const BARCODE = "GET /api/v1/me/bookings/70/barcode/";
const UNPAID = { status: 200, body: { state: "unpaid", reason: "The booking still owes R 1,200.", barcode: bookingBarcode() } };
const CHECKOUT = "https://sandbox.payfast.co.za/eng/process?m_payment_id=abc";

describe("Booking payments", () => {
  it("says when payment is taken before it is due", async () => {
    await openAs(
      "/bookings/70",
      { [ONE]: { status: 200, body: booking({ status: "accepted" }) }, [OUTCOME]: { status: 200, body: outcome() }, [BARCODE]: UNPAID },
      "Booking",
      BOOKER,
    );

    expect(await screen.findByText("Payment is taken Mon 26 Oct · 18:00.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Pay/ })).not.toBeInTheDocument();
    expect(screen.getByText("Still to pay")).toBeInTheDocument();
  });

  it("asks for cash at the club when it can't be paid in the app", async () => {
    await openAs(
      "/bookings/70",
      {
        [ONE]: { status: 200, body: booking({ status: "accepted", payment_requested: true, can_pay: false, outstanding: "1200.00" }) },
        [OUTCOME]: { status: 200, body: outcome() },
        [BARCODE]: UNPAID,
      },
      "Booking",
      BOOKER,
    );

    expect(await screen.findByText("Pay R 1,200 to the club before you play.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Pay/ })).not.toBeInTheDocument();
  });

  it("pays what is due on PayFast, then shows the result", async () => {
    const { calls } = await openAs(
      "/bookings/70",
      {
        [ONE]: {
          status: 200,
          body: booking({ status: "accepted", payment_requested: true, can_pay: true, paid: "200.00", outstanding: "1000.00" }),
        },
        [OUTCOME]: { status: 200, body: outcome() },
        [BARCODE]: UNPAID,
        "POST /api/v1/me/bookings/70/pay/": {
          status: 201,
          body: {
            reference: "abc",
            team: null,
            booking: { id: 70, field: { id: 3, name: "Pitch 3" }, starts_at: "2026-10-27T16:00:00Z", hours: 2 },
            amount: "1000.00",
            credit_used: "none",
            credit_amount: "0.00",
            card_amount: "1000.00",
            provider: "payfast",
            status: "pending",
            created_at: "2026-10-26T17:00:00Z",
            completed_at: null,
            checkout: { url: CHECKOUT, action: "https://sandbox.payfast.co.za/eng/process", form_fields: [] },
          },
        },
      },
      "Booking",
      BOOKER,
    );
    const user = userEvent.setup();

    expect(await screen.findByText("Payment due: R 1,000")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Pay R 1,000" }));

    expect(openCheckout).toHaveBeenCalledWith(CHECKOUT);
    expect(calls.some((c) => c.method === "POST" && c.path === "/api/v1/me/bookings/70/pay/")).toBe(true);
    expect(await screen.findByRole("heading", { name: "Payment" })).toBeInTheDocument();
  });

  it("shows what a cancellation returns before it is confirmed (FR-45)", async () => {
    await openAs(
      "/bookings/70",
      {
        [ONE]: { status: 200, body: booking({ status: "accepted", paid: "1200.00", outstanding: "0.00" }) },
        [OUTCOME]: {
          status: 200,
          body: outcome({
            cancel: {
              window: "late",
              paid: "1200.00",
              credit_percent: 50,
              credit: "600.00",
              kept: "600.00",
              summary: "You get R 600 of the R 1,200 you paid back as credit (50%). The club keeps R 600.",
            },
            reschedule: { window: "late", reschedules_left: 1, summary: "You can move it for free once more." },
          }),
        },
        [BARCODE]: { status: 200, body: { state: "valid", reason: "", barcode: bookingBarcode() } },
      },
      "Booking",
      BOOKER,
    );
    const user = userEvent.setup();

    const policy = await screen.findByRole("list", { name: "Cancellation policy" });
    expect(within(policy).getByText("24h to 6h before · now")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel booking" }));

    const ask = screen.getByRole("group", { name: "Cancel booking" });
    expect(ask).toHaveTextContent("The club keeps R 600.");
  });

  it("says why a booking can't be moved any more", async () => {
    await openAs(
      "/bookings/70",
      {
        [ONE]: { status: 200, body: booking({ status: "accepted", can_reschedule: false }) },
        [OUTCOME]: {
          status: 200,
          body: outcome({
            reschedule: { window: "very_late", allowed: false, summary: "It can't be moved less than 6 hours before it starts." },
          }),
        },
        [BARCODE]: UNPAID,
      },
      "Booking",
      BOOKER,
    );

    expect(await screen.findByText("It can't be moved less than 6 hours before it starts.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reschedule" })).not.toBeInTheDocument();
  });

  it("tells the user the club cancelled", async () => {
    await openAs(
      "/bookings/70",
      {
        [ONE]: {
          status: 200,
          body: booking({ status: "cancelled", cancelled_by_club: true, can_cancel: false, can_reschedule: false }),
        },
      },
      "Booking",
      BOOKER,
    );

    expect(await screen.findByText("The club cancelled this booking")).toBeInTheDocument();
  });
});

describe("Club bookings: cash and cancelling for the club", () => {
  const LIST = "GET /api/v1/clubs/1/bookings/";
  const ADMIN = {
    ...BOOKER,
    id: 2,
    name: "Admin",
    is_booking_user: false,
    club_roles: [{ club_id: 1, club_name: "Club A", role: "admin" as const }],
  };
  const accepted = clubBooking({
    status: "accepted",
    can_decide: false,
    can_record_cash: true,
    paid: "200.00",
    outstanding: "1000.00",
    club_cancel_summary: "You get all R 200 you paid back as credit.",
  });

  it("records cash, starting at what is still owed", async () => {
    const { calls } = await openAs(
      "/clubs/1/bookings",
      {
        [LIST]: { status: 200, body: [accepted] },
        "POST /api/v1/clubs/1/bookings/70/cash/": { status: 201, body: {} },
      },
      "Bookings",
      ADMIN,
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "All" }));
    expect(await screen.findByText("Paid R 200 · still to pay R 1,000")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Record cash" }));
    expect(screen.getByLabelText("Cash received (R)")).toHaveValue("1000.00");
    await user.click(screen.getByRole("button", { name: "Record cash" }));

    const post = calls.find((c) => c.method === "POST")!;
    expect(post.body).toEqual({ amount: "1000.00", reason: "" });
  });

  it("cancels for the club with a reason, after showing the credit it returns", async () => {
    const { calls } = await openAs(
      "/clubs/1/bookings",
      {
        [LIST]: { status: 200, body: [accepted] },
        "POST /api/v1/clubs/1/bookings/70/cancel/": { status: 200, body: {} },
      },
      "Bookings",
      ADMIN,
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "All" }));
    await user.click(await screen.findByRole("button", { name: "Cancel for the club" }));
    expect(screen.getByText("You get all R 200 you paid back as credit.")).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: "Cancel booking" });
    expect(confirm).toBeDisabled();
    await user.type(screen.getByLabelText("Why the club cancels"), "Floodlights down");
    await user.click(confirm);

    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ reason: "Floodlights down" });
  });
});
