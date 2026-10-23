import { Capacitor } from "@capacitor/core";
import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PushTap } from "../native/push";
import { fakeApi, ME } from "../test/fakeApi";
import { renderApp } from "../test/renderApp";
import { openAs } from "../pages/teams/testing";
import { DEVICE_KEY } from "./device";

const native = vi.hoisted(() => ({
  onToken: null as ((token: string) => void) | null,
  onTap: null as ((tap: PushTap) => void) | null,
  onReceived: null as (() => void) | null,
  stop: () => {},
}));

vi.mock("../native/push", () => ({
  registerPush: vi.fn(async (onToken: (token: string) => void) => {
    native.onToken = onToken;
    return { allowed: true, stop: native.stop };
  }),
  onPushTap: vi.fn((handler: (tap: PushTap) => void) => {
    native.onTap = handler;
    return () => {};
  }),
  onPushReceived: vi.fn((handler: () => void) => {
    native.onReceived = handler;
    return () => {};
  }),
  unregisterPush: vi.fn(async () => {}),
}));

const { registerPush, unregisterPush } = vi.mocked(await import("../native/push"));

beforeEach(() => {
  native.onToken = native.onTap = native.onReceived = null;
  vi.clearAllMocks();
});

const NOTIFICATION = {
  id: 5,
  kind: "update",
  title: "Red Lions vs Sharks moved",
  body: "",
  club_id: 1,
  fixture_id: null,
  created_at: "2026-10-26T05:40:00Z",
  read_at: "2026-10-26T05:40:00Z",
  answer: "",
  answered_at: null,
  answer_by: null,
  actions: [],
  can_answer: false,
  needs_reply: false,
};

describe("PushBridge", () => {
  it("registers this phone once someone is signed in", async () => {
    vi.spyOn(Capacitor, "getPlatform").mockReturnValue("android");
    const { calls } = await openAs(
      "/profile",
      { "POST /api/v1/devices/": { status: 201, body: { id: 12, platform: "android" } } },
      "Profile",
    );

    await waitFor(() => expect(registerPush).toHaveBeenCalledOnce());
    await act(async () => native.onToken!("fcm-token-1"));

    await waitFor(() => expect(window.localStorage.getItem(DEVICE_KEY)).toBe("12"));
    expect(calls.find((c) => c.path === "/api/v1/devices/")!.body).toEqual({
      token: "fcm-token-1",
      platform: "android",
    });
  });

  it("doesn't ask for push before anyone signs in", async () => {
    fakeApi({});
    renderApp("/login");
    await screen.findByRole("heading", { name: "Log in" });

    expect(registerPush).not.toHaveBeenCalled();
  });

  it("opens the notification when its push is tapped", async () => {
    const { router } = await openAs(
      "/profile",
      { "GET /api/v1/inbox/5/": { status: 200, body: NOTIFICATION } },
      "Profile",
    );

    await act(async () => native.onTap!({ actionId: "tap", data: { notification_id: "5", kind: "update" } }));

    expect(router.state.location.pathname).toBe("/inbox/5");
    expect(await screen.findByRole("heading", { name: "Red Lions vs Sharks moved" })).toBeInTheDocument();
  });

  it("forgets this phone on logout, while the session still works", async () => {
    window.localStorage.setItem(DEVICE_KEY, "12");
    const { calls } = await openAs(
      "/profile",
      {
        "DELETE /api/v1/devices/12/": { status: 204 },
        "POST /api/v1/auth/logout/": { status: 200, body: {} },
      },
      "Profile",
      ME,
    );

    await userEvent.click(screen.getByRole("button", { name: "Log out" }));

    await waitFor(() => expect(calls.some((c) => c.path === "/api/v1/auth/logout/")).toBe(true));
    const remove = calls.findIndex((c) => c.method === "DELETE" && c.path === "/api/v1/devices/12/");
    const logout = calls.findIndex((c) => c.path === "/api/v1/auth/logout/");
    expect(remove).toBeGreaterThanOrEqual(0);
    expect(remove).toBeLessThan(logout);
    expect(calls[remove]!.auth).toBe("Bearer access-1");
    expect(unregisterPush).toHaveBeenCalledOnce();
    expect(window.localStorage.getItem(DEVICE_KEY)).toBeNull();
  });
});
