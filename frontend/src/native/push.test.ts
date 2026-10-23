import { beforeEach, describe, expect, it, vi } from "vitest";

type Listener = (event: unknown) => void;
const listeners: Record<string, Listener> = {};
const remove = vi.fn(async () => {});

vi.mock("@capacitor/push-notifications", () => ({
  PushNotifications: {
    checkPermissions: vi.fn(),
    requestPermissions: vi.fn(),
    register: vi.fn(async () => {}),
    unregister: vi.fn(async () => {}),
    addListener: vi.fn(async (name: string, listener: Listener) => {
      listeners[name] = listener;
      return { remove };
    }),
  },
}));

// Fresh copies that see the mock, as in storage.test.ts.
async function load(native: boolean) {
  vi.resetModules();
  const { Capacitor } = await import("@capacitor/core");
  vi.spyOn(Capacitor, "isNativePlatform").mockReturnValue(native);
  const { PushNotifications } = await import("@capacitor/push-notifications");
  const push = await import("./push");
  return { PushNotifications: vi.mocked(PushNotifications), push };
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

beforeEach(() => {
  for (const key of Object.keys(listeners)) delete listeners[key];
  vi.clearAllMocks();
});

describe("push in the browser", () => {
  it("does nothing and never touches the plugin", async () => {
    const { PushNotifications, push } = await load(false);
    const onToken = vi.fn();

    expect((await push.registerPush(onToken)).allowed).toBe(false);
    push.onPushTap(vi.fn())();
    push.onPushReceived(vi.fn())();
    await push.unregisterPush();

    expect(PushNotifications.checkPermissions).not.toHaveBeenCalled();
    expect(PushNotifications.addListener).not.toHaveBeenCalled();
    expect(PushNotifications.unregister).not.toHaveBeenCalled();
  });
});

describe("push in the installed app", () => {
  it("asks for permission once, registers and hands back the token", async () => {
    const { PushNotifications, push } = await load(true);
    PushNotifications.checkPermissions.mockResolvedValue({ receive: "prompt" });
    PushNotifications.requestPermissions.mockResolvedValue({ receive: "granted" });
    const onToken = vi.fn();

    const { allowed, stop } = await push.registerPush(onToken);
    await flush();
    listeners.registration!({ value: "fcm-token-1" });

    expect(allowed).toBe(true);
    expect(PushNotifications.requestPermissions).toHaveBeenCalledOnce();
    expect(PushNotifications.register).toHaveBeenCalledOnce();
    expect(onToken).toHaveBeenCalledWith("fcm-token-1");
    stop();
    await flush();
    expect(remove).toHaveBeenCalledTimes(2);
  });

  it("doesn't ask again when the phone already said yes", async () => {
    const { PushNotifications, push } = await load(true);
    PushNotifications.checkPermissions.mockResolvedValue({ receive: "granted" });

    await push.registerPush(vi.fn());

    expect(PushNotifications.requestPermissions).not.toHaveBeenCalled();
    expect(PushNotifications.register).toHaveBeenCalledOnce();
  });

  it.each(["denied", "prompt"])("doesn't register when permission ends %s", async (answer) => {
    const { PushNotifications, push } = await load(true);
    PushNotifications.checkPermissions.mockResolvedValue({ receive: answer as "denied" });
    PushNotifications.requestPermissions.mockResolvedValue({ receive: "denied" });

    expect((await push.registerPush(vi.fn())).allowed).toBe(false);
    expect(PushNotifications.register).not.toHaveBeenCalled();
  });

  it("reports a tap with its button and data, and a push that arrives", async () => {
    const { push } = await load(true);
    const onTap = vi.fn();
    const onReceived = vi.fn();

    push.onPushTap(onTap);
    push.onPushReceived(onReceived);
    await flush();
    listeners.pushNotificationActionPerformed!({
      actionId: "tap",
      notification: { data: { notification_id: "5", kind: "confirmation" } },
    });
    listeners.pushNotificationReceived!({ data: { notification_id: "6" } });

    expect(onTap).toHaveBeenCalledWith({ actionId: "tap", data: { notification_id: "5", kind: "confirmation" } });
    expect(onReceived).toHaveBeenCalledWith({ notification_id: "6" });
  });

  it("unregisters on logout", async () => {
    const { PushNotifications, push } = await load(true);
    await push.unregisterPush();
    expect(PushNotifications.unregister).toHaveBeenCalledOnce();
  });
});
