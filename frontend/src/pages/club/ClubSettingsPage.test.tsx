import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { json } from "../../test/fakeApi";
import { openAsAdmin, SETTINGS } from "./testing";

const URL = "/api/v1/clubs/1/settings/";

async function open(patch: Parameters<typeof openAsAdmin>[1][string] = { status: 200, body: SETTINGS }) {
  const result = await openAsAdmin(
    "/clubs/1/setup/settings",
    { [`GET ${URL}`]: { status: 200, body: SETTINGS }, [`PATCH ${URL}`]: patch },
    "Settings",
  );
  await screen.findByLabelText("League fee per Team (R)");
  return result;
}

describe("ClubSettingsPage", () => {
  it("shows the club's values and which fees are missing", async () => {
    await open();

    expect(screen.getByLabelText("Confirmations go out (hours before kick-off)")).toHaveValue("36");
    expect(screen.getByLabelText("Credit when the club cancels (%)")).toHaveValue("100");
    expect(screen.getByLabelText("League fee per Team (R)")).toHaveValue("");
    expect(screen.getByText(/Still to set: League fee per Team, Friendly fee per match/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Card and cash" })).toHaveAttribute("aria-pressed", "true");
  });

  it("saves fees as decimal strings and whole numbers as numbers", async () => {
    const { calls } = await open((request) =>
      request.json().then((body) => json(200, { ...SETTINGS, ...body, missing: ["booking_hourly_fee"] })),
    );
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("League fee per Team (R)"), "350");
    await user.type(screen.getByLabelText("Friendly fee per match (R)"), "70.50");
    const minimum = screen.getByLabelText("Minimum players for a new Division");
    await user.clear(minimum);
    await user.type(minimum, "6");
    await user.click(screen.getByRole("button", { name: "Cash only" }));
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Saved")).toBeInTheDocument();
    const body = calls.find((c) => c.method === "PATCH")!.body as Record<string, unknown>;
    expect(body).toMatchObject({
      league_fee: "350",
      friendly_fee: "70.50",
      booking_hourly_fee: null,
      division_min_players: 6,
      payment_mode: "cash_only",
    });
    expect(screen.getByText("Still to set: Field hire per hour.", { exact: false })).toBeInTheDocument();
  });

  it("shows the API's reason next to a value it refuses", async () => {
    await open({
      status: 400,
      body: { readiness_hours_before: ["Must be fewer hours before kick-off than the Confirmations."] },
    });

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText("Must be fewer hours before kick-off than the Confirmations."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Reminder and squad check (hours before kick-off)")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });
});
