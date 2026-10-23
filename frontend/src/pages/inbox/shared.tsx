// What the inbox screens share: how each kind of notification is named and drawn, and how
// its answer reads. What can be answered, and until when, comes from the API.

import type { Schemas } from "../../api/client";
import { Icon, type IconName } from "../../components/Icon";
import type { Status } from "../../components/StatusChip";
import { formatDate, formatTime, localDate, WEEKDAYS_SHORT } from "../../format";

export type Notification = Schemas["Notification"];
export type Kind = Schemas["NotificationKindEnum"];
export type AnswerKey = Schemas["NotificationAnswerEnum"];

export const KIND_LABEL: Record<Kind, string> = {
  confirmation: "Confirmation",
  reminder: "Reminder",
  general: "General",
  update: "Update",
  player_request: "Player Request",
  goalkeeper_request: "Goalkeeper Request",
  booking: "Booking",
};

const KIND_ICON: Record<Kind, IconName> = {
  confirmation: "bell",
  reminder: "bell",
  general: "bell",
  update: "calendarClock",
  player_request: "users",
  goalkeeper_request: "hand",
  booking: "ticket",
};

/** Player phrases for the answer buttons (README, Voice); the API's label otherwise. */
const BUTTON_LABEL: Partial<Record<Kind, Partial<Record<AnswerKey, string>>>> = {
  confirmation: { confirm: "I'm in", decline: "Can't make it" },
  player_request: { accept: "Join match", decline: "Not tonight" },
  goalkeeper_request: { accept: "Join match", decline: "Not tonight" },
};

export function buttonLabel(kind: Kind, key: string, fallback: string): string {
  return BUTTON_LABEL[kind]?.[key as AnswerKey] ?? fallback;
}

/** How a given answer reads, as a status chip. */
export function answerChip(kind: Kind, answer: AnswerKey): { status: Status; label: string } {
  if (answer === "decline") {
    return { status: "cancelled", label: kind === "confirmation" ? "Can't make it" : "Declined" };
  }
  if (kind === "confirmation") return { status: "confirmed", label: "You're in" };
  if (answer === "accept") return { status: "confirmed", label: "Accepted" };
  return { status: "confirmed", label: "Confirmed" };
}

/** The tone and icon of a notification's disc: waiting, answered, an update, or neutral. */
export function discOf(n: Notification): { tone: Status | "neutral"; icon: IconName } {
  if (n.needs_reply) return { tone: "pending", icon: KIND_ICON[n.kind] };
  if (n.answer) {
    return n.answer === "decline" ? { tone: "cancelled", icon: "x" } : { tone: "confirmed", icon: "check" };
  }
  if (n.kind === "update") return { tone: "info", icon: "calendarClock" };
  return { tone: "neutral", icon: KIND_ICON[n.kind] };
}

export function Disc({ notification, xl }: { notification: Notification; xl?: boolean }) {
  const { tone, icon } = discOf(notification);
  return (
    <span className={`la-disc la-disc--${tone}${xl ? " la-disc--xl" : ""}`} aria-hidden="true">
      <Icon name={icon} />
    </span>
  );
}

/** "Tue 13:40": the reply deadline, in South Africa. */
export function deadline(isoDateTime: string): string {
  const day = new Date(`${localDate(isoDateTime)}T00:00:00Z`).getUTCDay();
  return `${WEEKDAYS_SHORT[(day + 6) % 7]} ${formatTime(isoDateTime)}`;
}

/** "Mon 19 Oct", in South Africa. */
export function day(isoDateTime: string): string {
  return formatDate(localDate(isoDateTime));
}
