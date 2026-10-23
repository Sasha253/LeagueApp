import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setTokens } from "../../api/auth";
import { fakeApi, ME, TOKENS } from "../../test/fakeApi";
import { renderApp } from "../../test/renderApp";
import { openAs } from "../teams/testing";
import { CHECKOUT_URL, options, payment, REFERENCE } from "./testing";

vi.mock("../../native/browser", () => ({ openCheckout: vi.fn(async () => true) }));
const { openCheckout } = await import("../../native/browser");

const OPTIONS = "GET /api/v1/teams/7/payments/options/";
const PAY = "POST /api/v1/teams/7/payments/";
const RESULT = `GET /api/v1/payments/${REFERENCE}/`;

beforeEach(() => vi.mocked(openCheckout).mockClear());

describe("PayPage", () => {
  it("starts at the Player's share and opens PayFast for the card part", async () => {
    const { calls, router } = await openAs(
      "/teams/7/pay",
      {
        [OPTIONS]: { status: 200, body: options({ outstanding: "280.00" }) },
        [PAY]: { status: 201, body: payment() },
        [RESULT]: { status: 200, body: payment({ status: "complete", checkout: null }) },
      },
      "Pay my share",
    );
    const user = userEvent.setup();

    expect(screen.getByText("R 350")).toBeInTheDocument();
    expect(screen.getByText("R 280")).toBeInTheDocument();
    expect(screen.getByText("R 280 to go", { exact: false })).toBeInTheDocument();
    expect(screen.getByLabelText("Amount (R)")).toHaveValue("70");
    expect(screen.getByText("Pay any amount up to R 280. By card, at least R 5.")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Use credit first" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Pay R 70" }));

    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ amount: "70", credit: "none" });
    expect(openCheckout).toHaveBeenCalledWith(CHECKOUT_URL);
    await screen.findByRole("heading", { name: "Payment" });
    expect(router.state.location.pathname).toBe("/payments/done");
    expect(router.state.location.search).toBe(`?payment=${REFERENCE}`);
  });

  it("pays what the Player types, with their credit first, and skips PayFast when credit covers it", async () => {
    const { calls } = await openAs(
      "/teams/7/pay",
      {
        [OPTIONS]: { status: 200, body: options({ my_credit: "40.00", team_credit: "25.00" }) },
        [PAY]: {
          status: 201,
          body: payment({ amount: "35.50", credit_used: "player", credit_amount: "35.50", card_amount: "0.00", status: "complete", checkout: null }),
        },
        [RESULT]: { status: 200, body: payment({ status: "complete", checkout: null }) },
      },
      "Pay my share",
    );
    const user = userEvent.setup();

    const credit = screen.getByRole("group", { name: "Use credit first" });
    await user.click(within(credit).getByRole("button", { name: "My credit R 40" }));
    expect(within(credit).getByRole("button", { name: "Team credit R 25" })).toBeInTheDocument();
    const amount = screen.getByLabelText("Amount (R)");
    await user.clear(amount);
    await user.type(amount, "35.5");
    await user.click(screen.getByRole("button", { name: "Pay R 35.50" }));

    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ amount: "35.5", credit: "player" });
    expect(openCheckout).not.toHaveBeenCalled();
    await screen.findByRole("heading", { name: "Payment" });
  });

  it("offers all that is owed, checks the amount's format and shows the backend's refusal", async () => {
    const { calls } = await openAs(
      "/teams/7/pay",
      {
        [OPTIONS]: { status: 200, body: options({ outstanding: "200.00" }) },
        [PAY]: { status: 409, body: { detail: "That is more than the Team still owes." } },
      },
      "Pay my share",
    );
    const user = userEvent.setup();
    const amount = screen.getByLabelText("Amount (R)");

    await user.clear(amount);
    await user.type(amount, "seventy");
    await user.click(screen.getByRole("button", { name: "Pay" }));
    expect(screen.getByText("Enter an amount in rand, like 70 or 70.50.")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST")).toBe(false);

    await user.click(screen.getByRole("button", { name: "All that's owed R 200" }));
    expect(amount).toHaveValue("200");
    await user.click(screen.getByRole("button", { name: "Pay R 200" }));

    expect(await screen.findByText("That is more than the Team still owes.")).toBeInTheDocument();
    expect(openCheckout).not.toHaveBeenCalled();
  });

  it("says a cash-only club takes cash when there is no credit to use", async () => {
    await openAs(
      "/teams/7/pay",
      { [OPTIONS]: { status: 200, body: options({ card_enabled: false, minimum_card_amount: null }) } },
      "Pay my share",
    );

    expect(screen.getByText("This club takes cash")).toBeInTheDocument();
    expect(screen.getByText("Pay cash to an Admin of the club. They record it here.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Pay/ })).not.toBeInTheDocument();
  });

  it("lets a cash-only club's Player pay with credit", async () => {
    await openAs(
      "/teams/7/pay",
      { [OPTIONS]: { status: 200, body: options({ card_enabled: false, minimum_card_amount: null, my_credit: "70.00" }) } },
      "Pay my share",
    );

    expect(screen.getByText("Pay with your credit here, or pay cash to an Admin of the club.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pay R 70" })).toBeInTheDocument();
    expect(screen.getByText("Pay any amount up to R 350.")).toBeInTheDocument();
  });

  it("says when the Team has paid", async () => {
    await openAs(
      "/teams/7/pay",
      { [OPTIONS]: { status: 200, body: options({ outstanding: "0.00", is_paid: true, suggested_amount: null }) } },
      "Pay my share",
    );

    expect(screen.getByText("Red Lions has paid")).toBeInTheDocument();
    expect(screen.queryByLabelText("Amount (R)")).not.toBeInTheDocument();
  });

  it("tells someone outside the Team they can't pay", async () => {
    await setTokens(TOKENS);
    fakeApi({ "GET /api/v1/auth/me/": { status: 200, body: ME }, [OPTIONS]: { status: 404, body: { detail: "Not found." } } });
    renderApp("/teams/7/pay");

    expect(await screen.findByText("Couldn't load the payment")).toBeInTheDocument();
  });
});
