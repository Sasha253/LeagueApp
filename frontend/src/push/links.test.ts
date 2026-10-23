import { describe, expect, it } from "vitest";
import { FIND_MATCH_PATH, pushLink } from "./links";

describe("pushLink", () => {
  it("opens the notification for a tap", () => {
    expect(pushLink({ actionId: "tap", data: { notification_id: "5", kind: "confirmation", fixture_id: "30" } })).toBe(
      "/inbox/5",
    );
  });

  it.each(["confirm", "decline", "accept"])("opens the notification for its %s button, never answering", (actionId) => {
    expect(pushLink({ actionId, data: { notification_id: "5" } })).toBe("/inbox/5");
  });

  it("opens Find a match for the General button", () => {
    expect(pushLink({ actionId: "find_match", data: { notification_id: "5" } })).toBe(FIND_MATCH_PATH);
  });

  it("falls back to the match, then the inbox", () => {
    expect(pushLink({ actionId: "tap", data: { fixture_id: "30" } })).toBe("/fixtures/30");
    expect(pushLink({ actionId: "tap", data: {} })).toBe("/inbox");
  });

  it("ignores ids that aren't numbers", () => {
    expect(pushLink({ actionId: "tap", data: { notification_id: "../admin", fixture_id: "x" } })).toBe("/inbox");
  });
});
