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
