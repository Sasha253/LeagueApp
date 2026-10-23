// Shared by the inbox screen tests: notifications as the API sends them.

const CONFIRM_ACTIONS = [
  { key: "confirm", label: "Confirm", action: "answer" },
  { key: "decline", label: "Decline", action: "answer" },
];

export function notification(overrides: object = {}) {
  return {
    id: 5,
    kind: "confirmation",
    title: "Can you make Tuesday's match?",
    body: "Red Lions vs Old Boys · Tue 27 Oct · 19:40 · Pitch 3",
    club_id: 1,
    fixture_id: 30 as number | null,
    booking_id: null as number | null,
    // Mon 26 Oct 07:40 in South Africa.
    created_at: "2026-10-26T05:40:00Z",
    read_at: null,
    answer: "",
    answered_at: null,
    // Tue 27 Oct 13:40 in South Africa (T-6h).
    answer_by: "2026-10-27T11:40:00Z",
    actions: CONFIRM_ACTIONS,
    can_answer: true,
    needs_reply: true,
    ...overrides,
  };
}

export const UPDATE = notification({
  id: 6,
  kind: "update",
  title: "Red Lions vs Sharks moved",
  body: "Now Tue 3 Nov, 20:20, Pitch 1",
  read_at: "2026-10-25T08:00:00Z",
  answer_by: null,
  actions: [],
  can_answer: false,
  needs_reply: false,
});

export const ANSWERED = notification({
  id: 7,
  title: "Can you make Tuesday 20 Oct?",
  read_at: "2026-10-19T08:00:00Z",
  answer: "confirm",
  answered_at: "2026-10-19T08:00:00Z",
  answer_by: "2026-10-20T11:00:00Z",
  can_answer: false,
  needs_reply: false,
});

export const GENERAL = notification({
  id: 8,
  kind: "general",
  title: "Old Boys are out tonight",
  body: "Find a friendly instead.",
  fixture_id: null,
  answer_by: null,
  actions: [{ key: "find_match", label: "Find a match", action: "open" }],
  can_answer: false,
  needs_reply: false,
});
