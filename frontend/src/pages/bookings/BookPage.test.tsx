import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ME } from "../../test/fakeApi";
import { openAs } from "../teams/testing";
import { BOOKER, booking, CLUB, FREE } from "./testing";

const CLUBS = "GET /api/v1/bookings/clubs/";
const AVAILABILITY = "GET /api/v1/bookings/availability/";

describe("BookPage", () => {
  it("shows each field's free times and the price from the API", async () => {
    const { calls } = await openAs(
      "/book",
      { [CLUBS]: { status: 200, body: [CLUB] }, [AVAILABILITY]: { status: 200, body: FREE } },
      "Book a field",
      BOOKER,
    );
    const user = userEvent.setup();

    const fields = await screen.findByRole("list", { name: "Fields" });
    expect(within(fields).getByRole("button", { name: /Pitch 3/ })).toHaveTextContent("2 start times free");
    expect(within(fields).getByRole("button", { name: /Pitch 4/ })).toHaveTextContent("Nothing free");
    expect(screen.getByText("R 600 × 2 h")).toBeInTheDocument();
    expect(screen.getByText("R 1,200")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request booking" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "More hours" }));
    const asked = calls.filter((c) => c.path === "/api/v1/bookings/availability/");
    expect(asked.length).toBeGreaterThanOrEqual(2);

    await user.click(within(fields).getByRole("button", { name: /Pitch 4/ }));
    expect(screen.getByText(/Pitch 4 isn't free for/)).toBeInTheDocument();
  });

  it("requests the picked slot and shows it as requested", async () => {
    const { calls } = await openAs(
      "/book",
      {
        [CLUBS]: { status: 200, body: [CLUB] },
        [AVAILABILITY]: { status: 200, body: FREE },
        "POST /api/v1/me/bookings/": { status: 201, body: booking() },
      },
      "Book a field",
      BOOKER,
    );
    const user = userEvent.setup();

    await user.click(within(await screen.findByRole("list", { name: "Fields" })).getByRole("button", { name: /Pitch 3/ }));
    await user.click(screen.getByRole("button", { name: "18:00" }));
    await user.click(screen.getByRole("button", { name: "Request booking" }));

    expect(await screen.findByText("Booking requested")).toBeInTheDocument();
    expect(screen.getByText("Tue 27 Oct · 18:00 to 20:00")).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST")!;
    expect(post.body).toEqual({ club: 1, field: 3, starts_at: "2026-10-27T16:00:00Z", hours: 1 });
  });

  it("shows why the API refused the request", async () => {
    await openAs(
      "/book",
      {
        [CLUBS]: { status: 200, body: [CLUB] },
        [AVAILABILITY]: { status: 200, body: FREE },
        "POST /api/v1/me/bookings/": { status: 409, body: { detail: "This field is already taken." } },
      },
      "Book a field",
      BOOKER,
    );
    const user = userEvent.setup();

    await user.click(within(await screen.findByRole("list", { name: "Fields" })).getByRole("button", { name: /Pitch 3/ }));
    await user.click(screen.getByRole("button", { name: "21:00" }));
    await user.click(screen.getByRole("button", { name: "Request booking" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("already taken");
  });

  it("asks a user who doesn't hire fields to turn it on", async () => {
    await openAs("/book", { [CLUBS]: { status: 403, body: { detail: "No." } } }, "Book a field", ME);

    expect(await screen.findByText(/Turn on “I hire a field”/)).toBeInTheDocument();
  });

  it("lets the user pick a club when several take bookings", async () => {
    await openAs(
      "/book",
      {
        [CLUBS]: { status: 200, body: [CLUB, { ...CLUB, id: 2, name: "Club B" }] },
        [AVAILABILITY]: { status: 200, body: FREE },
      },
      "Book a field",
      BOOKER,
    );

    await userEvent.click(await screen.findByRole("button", { name: "Club B" }));

    expect(await screen.findByText("Club B · R 600 an hour")).toBeInTheDocument();
  });
});
