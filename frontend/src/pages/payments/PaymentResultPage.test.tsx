import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { openAs } from "../teams/testing";
import { CHECKOUT_URL, payment, REFERENCE } from "./testing";

vi.mock("../../native/browser", () => ({ openCheckout: vi.fn(async () => true) }));
const { openCheckout } = await import("../../native/browser");

const RESULT = `GET /api/v1/payments/${REFERENCE}/`;
const DONE = `/payments/done?payment=${REFERENCE}`;

beforeEach(() => vi.mocked(openCheckout).mockClear());
afterEach(() => vi.useRealTimers());

describe("PaymentResultPage", () => {
  it("shows a completed payment, with what came from credit and card", async () => {
    await openAs(
      DONE,
      {
        [RESULT]: {
          status: 200,
          body: payment({ amount: "70.00", credit_amount: "20.00", card_amount: "50.00", status: "complete", checkout: null }),
        },
      },
      "Payment",
    );

    expect(await screen.findByText("R 70 towards Red Lions")).toBeInTheDocument();
    expect(screen.getByText("R 20 from credit")).toBeInTheDocument();
    expect(screen.getByText("R 50 by card")).toBeInTheDocument();
    expect(screen.getByText("Thanks. Your payment is recorded for Red Lions.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to Red Lions" })).toHaveAttribute("href", "/teams/7");
    expect(screen.queryByRole("button", { name: "Check again" })).not.toBeInTheDocument();
  });

  it("checks again while PayFast hasn't confirmed, by itself and on request", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { calls } = await openAs(
      DONE,
      {
        [RESULT]: [
          { status: 200, body: payment() },
          { status: 200, body: payment() },
          { status: 200, body: payment({ status: "complete", checkout: null }) },
        ],
      },
      "Payment",
    );
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    expect(await screen.findByText("Waiting for PayFast")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    await vi.waitFor(() => expect(calls.filter((c) => c.path === `/api/v1/payments/${REFERENCE}/`)).toHaveLength(2));

    await user.click(screen.getByRole("button", { name: "Check again" }));
    expect(await screen.findByText("Thanks. Your payment is recorded for Red Lions.")).toBeInTheDocument();
  });

  it("offers PayFast again when the Player left before paying", async () => {
    await openAs(
      `/payments/cancelled?payment=${REFERENCE}`,
      { [RESULT]: { status: 200, body: payment({ credit_amount: "20.00", card_amount: "50.00" }) } },
      "Payment",
    );
    const user = userEvent.setup();

    expect(await screen.findByText("Not paid yet")).toBeInTheDocument();
    expect(screen.getByText("You left PayFast before paying. Your credit is already used. Pay R 50 by card to finish.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Pay R 50 by card" }));

    expect(openCheckout).toHaveBeenCalledWith(CHECKOUT_URL);
  });

  it("says a failed payment can be made again", async () => {
    await openAs(DONE, { [RESULT]: { status: 200, body: payment({ status: "failed", checkout: null }) } }, "Payment");

    expect(await screen.findByText("The card payment failed")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Pay again" })).toHaveAttribute("href", "/teams/7/pay");
  });

  it("says when there is no payment to show", async () => {
    await openAs("/payments/done", {}, "Payment");

    expect(screen.getByText("No payment to show")).toBeInTheDocument();
  });
});
