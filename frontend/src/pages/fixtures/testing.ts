// Shared by the Fixture screen tests: Fixtures as the API sends them.

const CLUB = { id: 1, name: "Club A" };

export const FIXTURE = {
  id: 30,
  club: CLUB,
  season: { id: 5, name: "Spring 2026" },
  division: { id: 3, name: "Division 2" },
  weekday: 1 as const,
  pitch: { id: 9, name: "Pitch 3" },
  // 19:40 in South Africa.
  kick_off: "2026-10-27T17:40:00Z",
  home_team: { id: 7, name: "Red Lions" },
  away_team: { id: 8, name: "Old Boys" },
  friendly_eligible: false,
  status: "scheduled" as const,
};

export function myFixture(overrides: object = {}) {
  return { ...FIXTURE, my_team_id: 8, ...overrides };
}

export function adminFixture(overrides: object = {}) {
  return {
    ...FIXTURE,
    referee_name: "Rita Referee",
    friendly_eligible_changed_by_name: null,
    friendly_eligible_changed_at: null,
    created_at: "2026-10-20T08:00:00Z",
    transitions: [
      {
        id: 1,
        from_status: "",
        to_status: "scheduled",
        at: "2026-10-20T08:00:00Z",
        cause: "import",
        actor_name: "Ada Admin",
        note: "",
      },
    ],
    replacements: [],
    fallback: null,
    reschedules: [],
    captain_requests: [],
    ...overrides,
  };
}

/** A search for a new opponent, as the Admin's fixture detail sends it. */
export function replacement(overrides: object = {}) {
  return {
    id: 4,
    // 19:40 and its close time, 17:40, in South Africa.
    kick_off: "2026-10-27T17:40:00Z",
    status: "open" as const,
    slot: "home" as const,
    out_team: { id: 7, name: "Red Lions" },
    remaining_team: { id: 8, name: "Old Boys" },
    opened_at: "2026-10-27T11:40:00Z",
    closes_at: "2026-10-27T15:40:00Z",
    offered_to: [
      { id: 11, name: "Blue Bulls" },
      { id: 12, name: "Green Geckos" },
    ],
    accepted_team: null,
    accepted_by_name: null,
    accepted_at: null,
    ended_at: null,
    ...overrides,
  };
}

/** A friendly or a cancellation, as the Admin's fixture detail sends it. */
export function fallback(overrides: object = {}) {
  return {
    id: 6,
    kick_off: "2026-10-27T17:40:00Z",
    cause: "both_teams_out" as const,
    outcome: "friendly" as const,
    remaining_team: null,
    // 13:40 in South Africa.
    decided_at: "2026-10-27T11:40:00Z",
    invited: 3,
    joined: [],
    credit_returned: "0.00",
    credits: 0,
    ...overrides,
  };
}

/** My Team's replies for Fixture 30, as the squad endpoint sends them. */
export function squad(overrides: object = {}) {
  return {
    fixture_id: 30,
    team: { id: 8, name: "Old Boys" },
    min_players: 5,
    confirmed: 1,
    declined: 1,
    waiting: 2,
    below_minimum: true,
    short_by: 4,
    // Tue 27 Oct 13:40 in South Africa: T-6h.
    answer_by: "2026-10-27T11:40:00Z",
    replies_open: true,
    my_answer: "" as const,
    players: [
      { id: 3, name: "Pieter Botha", position: "goalkeeper", is_captain: true, is_me: false, answer: "confirm", answered_at: "2026-10-26T06:00:00Z" },
      { id: 4, name: "Ayanda Khumalo", position: "both", is_captain: false, is_me: false, answer: "decline", answered_at: "2026-10-26T07:00:00Z" },
      { id: 1, name: "Sipho Dlamini", position: "outfield", is_captain: false, is_me: true, answer: "", answered_at: null },
      { id: 5, name: "Zaid Adams", position: "outfield", is_captain: false, is_me: false, answer: "", answered_at: null },
    ],
    borrowed: [] as { id: number; name: string; position: string; kind: "player" | "goalkeeper"; joined_at: string }[],
    ...overrides,
  };
}

/** A Captain's request to cancel or postpone Fixture 30 (FR-18). */
export function captainRequest(overrides: object = {}) {
  return {
    id: 50,
    fixture_id: 30,
    team: { id: 7, name: "Red Lions" },
    kind: "cancel" as const,
    reason: "Half the team is at a wedding",
    kick_off: "2026-10-27T17:40:00Z",
    requested_by_name: "Thandi Mokoena",
    // Mon 26 Oct 10:00 in South Africa.
    requested_at: "2026-10-26T08:00:00Z",
    status: "pending" as const,
    decided_by_name: null,
    decided_at: null,
    note: "",
    ...overrides,
  };
}

/** What a reschedule will do, as the preview endpoint sends it. */
export function reschedulePreview(overrides: object = {}) {
  return {
    // Tue 3 Nov 19:40 in South Africa.
    kick_off: "2026-11-03T17:40:00Z",
    pitch: { id: 9, name: "Pitch 3" },
    kick_off_changed: true,
    pitch_changed: false,
    status_after: "scheduled" as const,
    confirmations_now: false,
    answer_by: "2026-11-03T11:40:00Z",
    players: 8,
    officials: 2,
    ...overrides,
  };
}

/** A Captain's Player or Goalkeeper Request for Fixture 30 (FR-35). */
export function playerRequest(overrides: object = {}) {
  return {
    id: 60,
    fixture_id: 30,
    team: { id: 8, name: "Old Boys" },
    kind: "player" as const,
    places: 2,
    filled: 0,
    kick_off: "2026-10-27T17:40:00Z",
    raised_by_name: "Pieter Botha",
    // Mon 26 Oct 10:00 in South Africa.
    raised_at: "2026-10-26T08:00:00Z",
    status: "open" as const,
    ended_at: null,
    note: "",
    notified: 3,
    joined: [] as { id: number; name: string; joined_at: string }[],
    ...overrides,
  };
}

/** A request I was sent, as /api/v1/me/player-requests/ sends it. */
export function gameToJoin(overrides: object = {}) {
  return {
    id: 60,
    notification_id: 70,
    kind: "goalkeeper" as const,
    team: { id: 7, name: "Red Lions" },
    fixture: FIXTURE,
    places: 1,
    places_left: 1,
    status: "open" as const,
    my_answer: "" as const,
    joined: false,
    can_answer: true,
    answer_by: "2026-10-27T17:40:00Z",
    ...overrides,
  };
}
