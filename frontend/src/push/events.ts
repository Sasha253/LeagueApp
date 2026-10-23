// Tells open screens that the inbox changed: a push arrived, or a notification was read or
// answered, so the inbox and its unread count reload.

const EVENT = "leagueapp:inbox-changed";

export function inboxChanged(): void {
  window.dispatchEvent(new Event(EVENT));
}

export function onInboxChanged(handler: () => void): () => void {
  window.addEventListener(EVENT, handler);
  return () => window.removeEventListener(EVENT, handler);
}
