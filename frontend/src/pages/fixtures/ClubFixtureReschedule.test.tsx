import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ADMIN_ME } from "../club/testing";
import { openAs } from "../teams/testing";
import { adminFixture, captainRequest, reschedulePreview } from "./testing";

const DETAIL = "/api/v1/clubs/1/fixtures/30/";
const FIELDS = "GET /api/v1/clubs/1/fields/";
const PREVIEW = "POST /api/v1/clubs/1/fixtures/30/reschedule/preview/";
const RESCHEDULE = "POST /api/v1/clubs/1/fixtures/30/reschedule/";
const ACCEPT = "POST /api/v1/clubs/1/captain-requests/50/accept/";
const DECLINE = "POST /api/v1/clubs/1/captain-requests/50/decline/";

const PITCHES = [
  { id: 9, name: "Pitch 3", referee: null, referee_name: null },
  { id: 10, name: "Pitch 5", referee: null, referee_name: null },
];

function open(fixture: object, routes: object = {}) {
  const body = adminFixture(fixture);
  return openAs(
    "/clubs/1/fixtures/30",
    { [`GET ${DETAIL}`]: { status: 200, body }, [FIELDS]: { status: 200, body: PITCHES }, ...routes },
    "Fixture",
    ADMIN_ME,
  );
}

const section = () => screen.getByRole("region", { name: "Reschedule" });

describe("ClubFixturePage: reschedule", () => {
  it("starts from the current kick-off and pitch, previews, then reschedules", async () => {
    const moved = adminFixture({
      kick_off: "2026-11-03T17:40:00Z",
      reschedules: [
        {
          id: 1,
          from_kick_off: "2026-10-27T17:40:00Z",
          to_kick_off: "2026-11-03T17:40:00Z",
          from_pitch: { id: 9, name: "Pitch 3" },
          to_pitch: { id: 10, name: "Pitch 5" },
          at: "2026-10-23T08:00:00Z",
          by_name: "Ada Admin",
          note: "Floodlights",
          request_id: null,
          confirmations_sent: false,
          notified: 10,
        },
      ],
    });
    const { calls } = await open(
      {},
      {
        [`GET ${DETAIL}`]: [
          { status: 200, body: adminFixture() },
          { status: 200, body: moved },
        ],
        [PREVIEW]: { status: 200, body: reschedulePreview({ pitch: { id: 10, name: "Pitch 5" }, pitch_changed: true }) },
        [RESCHEDULE]: { status: 200, body: moved },
      },
    );
    await screen.findByRole("region", { name: "Reschedule" });
    const date = within(section()).getByLabelText("Date");
    expect(date).toHaveValue("2026-10-27");
    expect(within(section()).getByLabelText("Kick-off")).toHaveValue("19:40");

    fireEvent.change(date, { target: { value: "2026-11-03" } });
    await userEvent.click(await within(section()).findByRole("button", { name: "Pitch 5" }));
    await userEvent.click(within(section()).getByRole("button", { name: "Check who is told" }));

    const preview = await within(section()).findByRole("status");
    expect(preview).toHaveTextContent("Move to Tue 3 Nov · 19:40, Pitch 5");
    expect(preview).toHaveTextContent("Tells 8 Players of both Teams and 2 officials");
    expect(preview).toHaveTextContent("Confirmations go out as usual");
    expect(calls.find((c) => c.path.endsWith("/preview/"))!.body).toEqual({
      kick_off: "2026-11-03T19:40:00+02:00",
      pitch: 10,
    });

    await userEvent.type(within(section()).getByLabelText("Note (optional)"), "Floodlights");
    await userEvent.click(within(section()).getByRole("button", { name: "Reschedule" }));

    const history = await screen.findByRole("list", { name: "Reschedules" });
    expect(history).toHaveTextContent("Moved Tue 27 Oct · 19:40 to Tue 3 Nov · 19:40, Pitch 3 to Pitch 5");
    expect(history).toHaveTextContent("Ada Admin · 10 told");
    expect(calls.find((c) => c.path.endsWith("/reschedule/"))!.body).toEqual({
      kick_off: "2026-11-03T19:40:00+02:00",
      pitch: 10,
      note: "Floodlights",
    });
  });

  it("says when Confirmations go out at once", async () => {
    await open({}, { [PREVIEW]: { status: 200, body: reschedulePreview({ confirmations_now: true, status_after: "confirming" }) } });
    await userEvent.click(await screen.findByRole("button", { name: "Check who is told" }));

    expect(await within(section()).findByRole("status")).toHaveTextContent(
      "Confirmations go out now. Replies close Tue 3 Nov · 13:40.",
    );
  });

  it("shows the backend's refusal next to the date", async () => {
    await open(
      {},
      { [PREVIEW]: { status: 400, body: { kick_off: ["Wed 28 Oct isn't a Tuesday, this Division's Night."] } } },
    );
    await userEvent.click(await screen.findByRole("button", { name: "Check who is told" }));

    expect(await screen.findByText("Wed 28 Oct isn't a Tuesday, this Division's Night.")).toBeInTheDocument();
    expect(within(section()).queryByRole("button", { name: "Reschedule" })).not.toBeInTheDocument();
  });

  it("offers no reschedule once the match is cancelled", async () => {
    await open({ status: "cancelled" });

    await screen.findByRole("article", { name: "Red Lions vs Old Boys" });
    expect(screen.queryByRole("region", { name: "Reschedule" })).not.toBeInTheDocument();
  });
});

describe("ClubFixturePage: Captain requests", () => {
  it("accepts a cancellation", async () => {
    const { calls } = await open(
      { captain_requests: [captainRequest()] },
      { [ACCEPT]: { status: 200, body: { ...captainRequest({ status: "accepted" }), fixture: {} } } },
    );
    const list = await screen.findByRole("list", { name: "Captain requests" });
    expect(list).toHaveTextContent("Red Lions asks to cancel");
    expect(list).toHaveTextContent("Half the team is at a wedding");
    expect(list).toHaveTextContent("Sent Mon 26 Oct · 10:00 by Thandi Mokoena");

    await userEvent.click(within(list).getByRole("button", { name: "Accept: Red Lions out" }));

    expect(calls.find((c) => c.method === "POST")).toMatchObject({ path: "/api/v1/clubs/1/captain-requests/50/accept/", body: {} });
  });

  it("accepts a postponement with the time picked under Reschedule", async () => {
    const { calls } = await open(
      { captain_requests: [captainRequest({ kind: "postpone" })] },
      { [ACCEPT]: { status: 200, body: {} } },
    );
    await screen.findByRole("region", { name: "Reschedule" });
    fireEvent.change(within(section()).getByLabelText("Date"), { target: { value: "2026-11-03" } });

    const list = screen.getByRole("list", { name: "Captain requests" });
    await userEvent.click(within(list).getByRole("button", { name: "Accept: move to the time above" }));

    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ kick_off: "2026-11-03T19:40:00+02:00", pitch: 9 });
  });

  it("declines, and shows the backend's refusal", async () => {
    await open(
      { captain_requests: [captainRequest()] },
      { [DECLINE]: { status: 409, body: { detail: "This request has already been withdrawn." } } },
    );

    await userEvent.click(await screen.findByRole("button", { name: "Decline" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("This request has already been withdrawn.");
  });

  it("shows decided requests without buttons", async () => {
    await open({
      captain_requests: [
        captainRequest({ status: "declined", decided_by_name: "Ada Admin", decided_at: "2026-10-26T09:00:00Z", note: "Find a sub" }),
      ],
    });

    const list = await screen.findByRole("list", { name: "Captain requests" });
    expect(list).toHaveTextContent("Declined Mon 26 Oct · 11:00 by Ada Admin · Find a sub");
    expect(within(list).queryByRole("button")).not.toBeInTheDocument();
  });
});
