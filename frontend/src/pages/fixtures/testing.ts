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
    ...overrides,
  };
}
