import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { openAs } from "../teams/testing";
import { captainRequest, myFixture, squad } from "./testing";

const DETAIL = "GET /api/v1/fixtures/30/";
const SQUAD = "GET /api/v1/fixtures/30/squad/";
const REQUESTS = "/api/v1/fixtures/30/requests/";

function openMatch(requests: object) {
  return openAs(
    "/fixtures/30",
    {
      [DETAIL]: { status: 200, body: myFixture() },
      [SQUAD]: { status: 200, body: squad() },
      [`GET ${REQUESTS}`]: { status: 200, body: requests },
    },
    "Match",
  );
}

describe("FixturePage: cancel or postpone", () => {
  it("lets the Captain ask the Admin", async () => {
    await openMatch({ is_captain: true, can_request: true, requests: [] });

    expect(await screen.findByRole("link", { name: "Ask the Admin to cancel or postpone" })).toHaveAttribute(
      "href",
      "/fixtures/30/request",
    );
  });

  it("shows the Captain's waiting request, which they can withdraw", async () => {
    const { calls } = await openAs(
      "/fixtures/30",
      {
        [DETAIL]: { status: 200, body: myFixture() },
        [SQUAD]: { status: 200, body: squad() },
        [`GET ${REQUESTS}`]: [
          { status: 200, body: { is_captain: true, can_request: false, requests: [captainRequest()] } },
          { status: 200, body: { is_captain: true, can_request: true, requests: [captainRequest({ status: "withdrawn" })] } },
        ],
        "POST /api/v1/captain-requests/50/withdraw/": { status: 200, body: captainRequest({ status: "withdrawn" }) },
      },
      "Match",
    );
    const list = await screen.findByRole("list", { name: "Requests" });
    expect(list).toHaveTextContent("Waiting for the Admin");
    expect(screen.queryByRole("link", { name: /Ask the Admin/ })).not.toBeInTheDocument();

    await userEvent.click(within(list).getByRole("button", { name: "Withdraw" }));

    expect(await screen.findByText("Withdrawn")).toBeInTheDocument();
    expect(calls.some((c) => c.path === "/api/v1/captain-requests/50/withdraw/")).toBe(true);
  });

  it("shows a Player the Team's request but no buttons", async () => {
    await openMatch({ is_captain: false, can_request: false, requests: [captainRequest({ status: "declined" })] });

    const list = await screen.findByRole("list", { name: "Requests" });
    expect(list).toHaveTextContent("Red Lions asks to cancel");
    expect(list).toHaveTextContent("Declined");
    expect(within(list).queryByRole("button")).not.toBeInTheDocument();
  });

  it("shows nothing to a Player when there is no request", async () => {
    await openMatch({ is_captain: false, can_request: false, requests: [] });

    await screen.findByRole("region", { name: "Squad" });
    expect(screen.queryByRole("region", { name: "Cancel or postpone" })).not.toBeInTheDocument();
  });
});

describe("FixtureRequestPage", () => {
  it("sends the request to the Admin and goes back to the match", async () => {
    const { calls, router } = await openAs(
      "/fixtures/30/request",
      {
        [DETAIL]: { status: 200, body: myFixture() },
        [`POST ${REQUESTS}`]: { status: 201, body: { is_captain: true, can_request: false, requests: [captainRequest()] } },
      },
      "Cancel or postpone",
    );
    expect(await screen.findByText("The Admin must accept it")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByText(/your Team is out of this match/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Reason"), "Half the team is at a wedding");
    await userEvent.click(screen.getByRole("button", { name: "Send to Admin" }));

    await screen.findByRole("heading", { name: "Match" });
    expect(router.state.location.pathname).toBe("/fixtures/30");
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({
      kind: "cancel",
      reason: "Half the team is at a wedding",
    });
  });

  it("shows the backend's refusal", async () => {
    await openAs(
      "/fixtures/30/request",
      {
        [DETAIL]: { status: 200, body: myFixture() },
        [`POST ${REQUESTS}`]: { status: 409, body: { detail: "Red Lions already has a request waiting for the Admin." } },
      },
      "Cancel or postpone",
    );
    await userEvent.type(await screen.findByLabelText("Reason"), "Wedding");
    await userEvent.click(screen.getByRole("button", { name: "Send to Admin" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("already has a request waiting");
  });
});
