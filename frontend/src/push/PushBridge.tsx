// Connects push to the app: registers this phone once someone is signed in, opens the
// right screen when a push or one of its buttons is tapped, and refreshes the inbox when a
// push arrives while the app is open. Renders nothing; does nothing in the browser.

import { useEffect } from "react";
import { useNavigate } from "react-router";
import { useAuth } from "../auth/AuthProvider";
import { onPushReceived, onPushTap, registerPush } from "../native/push";
import { registerDevice } from "./device";
import { inboxChanged } from "./events";
import { pushLink } from "./links";

export function PushBridge() {
  const navigate = useNavigate();
  const { state } = useAuth();
  const userId = state.status === "signedIn" ? state.me.id : null;

  // From the first render: a tap that started the app is delivered once a listener exists.
  useEffect(() => onPushTap((tap) => void navigate(pushLink(tap))), [navigate]);
  useEffect(() => onPushReceived(() => inboxChanged()), []);

  useEffect(() => {
    if (userId === null) return;
    let cancelled = false;
    let stop = () => {};
    registerPush((token) => {
      registerDevice(token).catch(() => {});
    })
      .then((result) => {
        if (cancelled) result.stop();
        else stop = result.stop;
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      stop();
    };
  }, [userId]);

  return null;
}
