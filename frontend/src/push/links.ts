// Where a tapped push, or one of its buttons, opens in the app. The backend puts the
// notification's id, kind and Fixture on every push (notifications/services.py, push_data).

import type { PushTap } from "../native/push";

/** The General notification's "Find a match" button (backend notifications.models.FIND_MATCH). */
export const FIND_MATCH = "find_match";

/**
 * Where "Find a match" goes. The "Games you can join" list arrives with the Player Request
 * and friendly chunks; until then it opens the Player's matches (docs/OPEN_QUESTIONS.md,
 * chunk 10).
 */
export const FIND_MATCH_PATH = "/fixtures";

const ID = /^\d+$/;

/**
 * The screen for a tap. A button that answers (Confirm, Accept, Decline) opens the
 * notification's screen and never answers by itself: the Player sees what they answer.
 */
export function pushLink({ actionId, data }: PushTap): string {
  if (actionId === FIND_MATCH) return FIND_MATCH_PATH;
  const notification = data.notification_id;
  if (notification && ID.test(notification)) return `/inbox/${notification}`;
  const fixture = data.fixture_id;
  if (fixture && ID.test(fixture)) return `/fixtures/${fixture}`;
  return "/inbox";
}
