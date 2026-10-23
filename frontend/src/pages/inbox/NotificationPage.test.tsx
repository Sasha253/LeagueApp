import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { json, ME } from "../../test/fakeApi";
import { openAs } from "../teams/testing";
import { ANSWERED, GENERAL, notification, UPDATE } from "./testing";

const path = (id: number) => `/api/v1/inbox/${id}/`;

/** Opens notification `n` with the API's read and answer endpoints. */
async function open(n: ReturnType<typeof notification>, extra = {}, me: object = ME) {
  return openAs(
    `/inbox/${n.id}`,
    {
      [`GET ${path(n.id)}`]: { status: 200, body: n },
      [`POST ${path(n.id)}read/`]: { status: 200, body: { ...n, read_at: "2026-10-26T05:41:00Z" } },
      ...extra,
    },
    ({ confirmation: "Confirmation", update: "Update", general: "General", player_request: "Player Request" } as Record<string, string>)[
      n.kind as string
    ]!,
    me,
  );
}

const card = () => screen.getByRole("article", { name: /./ });

describe("NotificationPage", () => {
  it("shows a Confirmation with its reply buttons and deadline, and marks it read", async () => {
    const { calls } = await open(notification());

    expect(within(card()).getByRole("heading", { name: "Can you make Tuesday's match?" })).toBeInTheDocument();
    expect(card()).toHaveTextContent("Red Lions vs Old Boys · Tue 27 Oct · 19:40 · Pitch 3");
    expect(card()).toHaveTextContent("Reply by Tue 13:40. You can change your answer until then.");
    expect(screen.getByText("Mon 26 Oct · 07:40")).toBeInTheDocument();
    expect(within(card()).getByRole("button", { name: "I'm in" })).toBeInTheDocument();
    expect(within(card()).getByRole("button", { name: "Can't make it" })).toBeInTheDocument();
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === `${path(5)}read/`)).toBe(true));
    expect(screen.getByRole("link", { name: "Open the match" })).toHaveAttribute("href", "/fixtures/30");
  });

  it("doesn't mark a read notification read again", async () => {
    const { calls } = await open(UPDATE);
    expect(calls.some((c) => c.path.endsWith("/read/"))).toBe(false);
  });

  it("answers I'm in, then shows You're in! and lets the answer change", async () => {
    const answered = notification({
      read_at: "2026-10-26T05:41:00Z",
      answer: "confirm",
      answered_at: "2026-10-26T05:42:00Z",
      needs_reply: false,
    });
    const { calls } = await open(notification(), { [`POST ${path(5)}answer/`]: { status: 200, body: answered } });

    await userEvent.click(screen.getByRole("button", { name: "I'm in" }));

    expect(await screen.findByText("You're in!")).toBeInTheDocument();
    expect(calls.find((c) => c.path === `${path(5)}answer/`)!.body).toEqual({ answer: "confirm" });
    expect(card()).toHaveTextContent("Status: You're in");
    expect(screen.queryByRole("button", { name: "I'm in" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Change" }));
    expect(screen.getByRole("button", { name: "Can't make it" })).toBeInTheDocument();
  });

  it("shows why an answer was refused", async () => {
    await open(notification(), {
      [`POST ${path(5)}answer/`]: { status: 409, body: { detail: "Replies for this match are closed." } },
    });

    await userEvent.click(screen.getByRole("button", { name: "Can't make it" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Replies for this match are closed.");
    expect(screen.getByRole("button", { name: "I'm in" })).toBeEnabled();
  });

  it("shows an answer that can no longer change, without Change", async () => {
    await open(ANSWERED);

    expect(card()).toHaveTextContent("Status: You're in");
    expect(card()).toHaveTextContent("Answered Mon 19 Oct");
    expect(screen.queryByRole("button", { name: "Change" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "I'm in" })).not.toBeInTheDocument();
  });

  it("says when replies closed before an answer", async () => {
    await open(notification({ can_answer: false, needs_reply: false }));

    expect(screen.getByText("Replies are closed")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "I'm in" })).not.toBeInTheDocument();
  });

  it("uses player phrases for a Player Request", async () => {
    await open(
      notification({
        kind: "player_request",
        title: "Red Lions need a player",
        actions: [
          { key: "accept", label: "Accept", action: "answer" },
          { key: "decline", label: "Decline", action: "answer" },
        ],
      }),
    );
    expect(within(card()).getByRole("button", { name: "Join match" })).toBeInTheDocument();
    expect(within(card()).getByRole("button", { name: "Not tonight" })).toBeInTheDocument();
  });

  it("shows an Update as a plain message", async () => {
    await open(UPDATE);

    expect(card()).toHaveTextContent("Now Tue 3 Nov, 20:20, Pitch 1");
    expect(within(card()).queryByRole("button")).not.toBeInTheDocument();
  });

  it("offers Find a match on a General notification", async () => {
    await open(GENERAL);

    expect(within(card()).getByRole("link", { name: "Find a match" })).toHaveAttribute("href", "/fixtures");
    expect(screen.queryByRole("link", { name: "Open the match" })).not.toBeInTheDocument();
  });

  it("opens the club's match screen for an Admin of that club", async () => {
    await open(UPDATE, {}, { ...ME, club_roles: [{ club_id: 1, club_name: "Club A", role: "admin" }] });

    expect(screen.getByRole("link", { name: "Open the match" })).toHaveAttribute("href", "/clubs/1/fixtures/30");
  });

  it("says when the notification can't be found", async () => {
    await openAs("/inbox/99", { [`GET ${path(99)}`]: () => json(404, { detail: "Not found." }) }, "Notification");

    expect(await screen.findByText("Couldn't load the notification")).toBeInTheDocument();
  });
});
