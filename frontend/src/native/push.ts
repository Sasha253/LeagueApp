// Push notifications, the one place the app touches @capacitor/push-notifications.
// Inside the installed app it asks for permission, registers with Firebase Cloud Messaging
// and reports taps. In the browser (npm run dev) every call is a no-op: the inbox still
// shows every notification.

import { PushNotifications } from "@capacitor/push-notifications";
import { isNative } from "./platform";

/** The data the backend puts on every push (notifications/services.py, push_data). */
export type PushData = Record<string, string | undefined>;

/** A tapped push: "tap" for the push itself, otherwise the id of the button tapped. */
export type PushTap = { actionId: string; data: PushData };

type Unsubscribe = () => void;
const NOTHING: Unsubscribe = () => {};

/** Runs `add` (a plugin addListener call) and answers a function that removes it. */
function listen(add: () => Promise<{ remove: () => Promise<void> }>): Unsubscribe {
  // A plugin that isn't there (the browser) rejects; there is then nothing to remove.
  const handle = Promise.resolve()
    .then(add)
    .catch(() => null);
  return () => {
    void handle.then((h) => h?.remove()).catch(() => {});
  };
}

/**
 * Asks for permission (only if the phone hasn't been asked yet) and registers for push.
 * Calls `onToken` with this phone's token each time the system hands one out. Answers
 * whether push is allowed. Always false in the browser.
 */
export async function registerPush(onToken: (token: string) => void): Promise<{ allowed: boolean; stop: Unsubscribe }> {
  if (!isNative()) return { allowed: false, stop: NOTHING };

  let permission = await PushNotifications.checkPermissions();
  if (permission.receive === "prompt" || permission.receive === "prompt-with-rationale") {
    permission = await PushNotifications.requestPermissions();
  }
  if (permission.receive !== "granted") return { allowed: false, stop: NOTHING };

  // Listen before registering, so the first token isn't missed.
  const stopToken = listen(() => PushNotifications.addListener("registration", (token) => onToken(token.value)));
  const stopError = listen(() =>
    PushNotifications.addListener("registrationError", (error) => {
      console.warn("Push registration failed", error.error);
    }),
  );
  await PushNotifications.register();
  return {
    allowed: true,
    stop: () => {
      stopToken();
      stopError();
    },
  };
}

/** Calls `handler` when a push, or one of its buttons, is tapped. */
export function onPushTap(handler: (tap: PushTap) => void): Unsubscribe {
  if (!isNative()) return NOTHING;
  return listen(() =>
    PushNotifications.addListener("pushNotificationActionPerformed", (action) =>
      handler({ actionId: action.actionId, data: (action.notification.data ?? {}) as PushData }),
    ),
  );
}

/** Calls `handler` when a push arrives while the app is open. */
export function onPushReceived(handler: (data: PushData) => void): Unsubscribe {
  if (!isNative()) return NOTHING;
  return listen(() =>
    PushNotifications.addListener("pushNotificationReceived", (notification) =>
      handler((notification.data ?? {}) as PushData),
    ),
  );
}

/** Stops push for this phone (on logout): no token, no more pushes until registered again. */
export async function unregisterPush(): Promise<void> {
  if (!isNative()) return;
  await PushNotifications.unregister().catch(() => {});
}
