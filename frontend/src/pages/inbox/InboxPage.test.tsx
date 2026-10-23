import { act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { inboxChanged } from "../../push/events";
import { json } from "../../test/fakeApi";
import { openAs } from "../teams/testing";
import { ANSWERED, notification, UPDATE } from "./testing";

const LIST = "GET /api/v1/inbox/";
const SUMMARY = "GET /api/v1/inbox/summary/";

/** Answers the list by its `filter` query. */
function byFilter(lists: Record<string, object[]>) {
  return (request: Request) => json(200, lists[new URL(request.url).searchParams.get("filter") ?? "all"] ?? []);
}

describe("InboxPage", () => {
  it("pins what needs a reply on top, with its deadline in South African time", async () => {
    await openAs(
      "/inbox",
      {
        [LIST]: byFilter({ all: [notification(), UPDATE, ANSWERED] }),
        [SUMMARY]: { status: 200, body: { unread: 1, needs_reply: 1 } },
      },
      "Inbox",
    );

    const pinned = await screen.findByRole("region", { name: "Needs reply" });
    const row = within(pinned).getByRole("link", { name: /Can you make Tuesday's match/ });
    expect(row).toHaveAttribute("href", "/inbox/5");
    expect(row).toHaveTextContent("Red Lions vs Old Boys · Tue 27 Oct · 19:40 · Pitch 3");
    expect(row).toHaveTextContent("Status: Reply by Tue 13:40");

    const earlier = screen.getByRole("region", { name: "Earlier" });
    const links = within(earlier).getAllByRole("link");
    expect(links[0]).toHaveTextContent("Update · Now Tue 3 Nov, 20:20, Pitch 1");
    expect(links[1]).toHaveTextContent("Confirmation · answered Mon 19 Oct");
    expect(screen.getByText("1 unread")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Needs reply\W+1$/ })).toBeInTheDocument();
  });

  it("marks unread rows", async () => {
    await openAs("/inbox", { [LIST]: byFilter({ all: [notification(), UPDATE] }) }, "Inbox");

    const unread = await screen.findByRole("link", { name: /Can you make Tuesday's match/ });
    expect(unread).toHaveTextContent("Unread: Can you make");
    expect(unread.querySelector(".la-unread")).not.toBeNull();
    const read = screen.getByRole("link", { name: /Red Lions vs Sharks moved/ });
    expect(read).not.toHaveTextContent("Unread");
    expect(read.querySelector(".la-unread")).toBeNull();
  });

  it("filters by Needs reply and Updates", async () => {
    const { calls } = await openAs(
      "/inbox",
      { [LIST]: byFilter({ all: [notification(), UPDATE], needs_reply: [notification()], updates: [UPDATE] }) },
      "Inbox",
    );
    await screen.findByRole("region", { name: "Needs reply" });

    await userEvent.click(screen.getByRole("button", { name: "Updates" }));
    expect(await screen.findByRole("link", { name: /Red Lions vs Sharks moved/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Can you make/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Updates" })).toHaveAttribute("aria-pressed", "true");

    await userEvent.click(screen.getByRole("button", { name: /Needs reply/ }));
    expect(await screen.findByRole("link", { name: /Can you make/ })).toBeInTheDocument();
    const asked = calls.filter((c) => c.path === "/api/v1/inbox/").length;
    expect(asked).toBe(3);
  });

  it("never shows the last filter's rows while the next one loads", async () => {
    await openAs(
      "/inbox",
      {
        [LIST]: (request: Request) =>
          new URL(request.url).searchParams.get("filter") === "updates"
            ? new Promise<Response>(() => {}) // still loading
            : json(200, [notification(), UPDATE]),
      },
      "Inbox",
    );
    await screen.findByRole("region", { name: "Needs reply" });

    await userEvent.click(screen.getByRole("button", { name: "Updates" }));

    expect(screen.queryByRole("link", { name: /Can you make/ })).not.toBeInTheDocument();
  });

  it("says when there is nothing, per filter", async () => {
    await openAs("/inbox", { [LIST]: byFilter({}) }, "Inbox");

    expect(await screen.findByText(/Nothing here yet/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Needs reply/ }));
    expect(await screen.findByText(/You're all caught up/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "See all" }));
    expect(await screen.findByText(/Nothing here yet/)).toBeInTheDocument();
  });

  it("offers Retry when the inbox can't load", async () => {
    await openAs("/inbox", { [LIST]: [{ status: 500 }, { status: 200, body: [UPDATE] }] }, "Inbox");

    await userEvent.click(await screen.findByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("link", { name: /Red Lions vs Sharks moved/ })).toBeInTheDocument();
  });

  it("reloads when a push arrives", async () => {
    await openAs("/inbox", { [LIST]: [{ status: 200, body: [] }, { status: 200, body: [UPDATE] }] }, "Inbox");
    await screen.findByText(/Nothing here yet/);

    act(() => inboxChanged());

    expect(await screen.findByRole("link", { name: /Red Lions vs Sharks moved/ })).toBeInTheDocument();
  });
});
