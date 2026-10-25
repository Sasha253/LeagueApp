// Find a team (design/src/ds/Screens.md, Player 4 and 5): search by Team name, Night and
// Division, ask to join, then wait for the Captain.

import { useEffect, useState } from "react";
import { api, type Night } from "../../api/client";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { StatusChip } from "../../components/StatusChip";
import { TextField } from "../../components/TextField";
import { WEEKDAYS_SHORT } from "../../format";
import { LoadState, send, useLoad } from "../club/shared";
import { NOT_A_PLAYER } from "./MyTeamsPage";
import { JoinStatus, playersLine, ScreenHeader, teamLine, type Team } from "./shared";

type Filters = { q: string; night: number | null; division: number | null };
type Named = Team["division"];

function nightLabel(night: Night, manyClubs: boolean) {
  const day = WEEKDAYS_SHORT[night.weekday];
  return manyClubs ? `${day} · ${night.club.name}` : day;
}

export function FindTeamPage() {
  const [text, setText] = useState("");
  const [filters, setFilters] = useState<Filters>({ q: "", night: null, division: null });
  const [nights] = useLoad(() => api.GET("/api/v1/nights/"), "nights");
  const [results, retry] = useLoad(
    () =>
      api.GET("/api/v1/teams/", {
        params: {
          query: {
            ...(filters.q ? { q: filters.q } : {}),
            ...(filters.night !== null ? { night: filters.night } : {}),
            ...(filters.division !== null ? { division: filters.division } : {}),
          },
        },
      }),
    `teams-${JSON.stringify(filters)}`,
  );
  const [mine, reloadMine] = useLoad(() => api.GET("/api/v1/me/teams/"), "my-teams");
  const [requests, reloadRequests] = useLoad(() => api.GET("/api/v1/me/join-requests/"), "my-join-requests");
  const [divisions, setDivisions] = useState<Named[]>([]);
  // The Team asked, and whether it took the Player at once as its Captain (a Team the Admin
  // added has no Captain until its first Player joins).
  const [sent, setSent] = useState<{ team: Team; captain: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  // The Team being asked: its button is off until the API answers, so a double tap doesn't
  // send the request twice.
  const [asking, setAsking] = useState<number | null>(null);

  // The Division chips are the Divisions of the chosen Night's Teams, so they come from a
  // search filtered by Night only.
  useEffect(() => {
    if (filters.night === null) setDivisions([]);
    else if (filters.division === null && results.state === "ok") {
      const seen = new Map(results.data.map((team) => [team.division.id, team.division]));
      setDivisions([...seen.values()].sort((a, b) => a.name.localeCompare(b.name)));
    }
  }, [filters.night, filters.division, results]);

  const inTeam = new Set(mine.state === "ok" ? mine.data.filter((m) => !m.left_at).map((m) => m.team.id) : []);
  const pending = new Map(
    requests.state === "ok" ? requests.data.filter((r) => r.status === "pending").map((r) => [r.team.id, r]) : [],
  );

  async function join(team: Team) {
    setSent(null);
    setAsking(team.id);
    let captain = false;
    const failed = await send(async () => {
      const answer = await api.POST("/api/v1/teams/{id}/join/", { params: { path: { id: team.id } } });
      captain = answer.data?.status === "accepted";
      return answer;
    });
    setAsking(null);
    setError(failed?.general ?? null);
    if (!failed) {
      setSent({ team, captain });
      reloadRequests();
      reloadMine();
    }
  }

  const nightList = nights.state === "ok" ? nights.data : [];
  const manyClubs = new Set(nightList.map((n) => n.club.id)).size > 1;

  return (
    <main className="la-screen">
      <ScreenHeader title="Find a team" back={{ label: "Teams", to: "/teams" }} />
      <form
        className="la-stack"
        role="search"
        aria-label="Find a team"
        onSubmit={(event) => {
          event.preventDefault();
          setFilters({ ...filters, q: text.trim() });
        }}
      >
        <TextField
          label="Team name"
          type="search"
          value={text}
          placeholder="Red Lions"
          onChange={(event) => setText(event.target.value)}
        />
        {nightList.length > 0 && (
          <fieldset className="la-fieldset la-stack-2">
            <legend className="la-overline">Night</legend>
            <div className="la-choices">
              {nightList.map((night) => (
                <ChoiceChip
                  key={night.id}
                  pressed={filters.night === night.id}
                  onToggle={() =>
                    setFilters({ ...filters, night: filters.night === night.id ? null : night.id, division: null })
                  }
                >
                  {nightLabel(night, manyClubs)}
                </ChoiceChip>
              ))}
            </div>
          </fieldset>
        )}
        {divisions.length > 1 && (
          <fieldset className="la-fieldset la-stack-2">
            <legend className="la-overline">Division</legend>
            <div className="la-choices">
              {divisions.map((division) => (
                <ChoiceChip
                  key={division.id}
                  pressed={filters.division === division.id}
                  onToggle={() =>
                    setFilters({ ...filters, division: filters.division === division.id ? null : division.id })
                  }
                >
                  {division.name}
                </ChoiceChip>
              ))}
            </div>
          </fieldset>
        )}
        <button type="submit" className="la-btn la-btn--secondary la-btn--block">
          Search
        </button>
      </form>

      {sent?.captain && (
        <Banner status="confirmed" title={`You're the Captain of ${sent.team.name}`}>
          You're its first Player. Players who ask to join next wait for you to accept them in Teams.
        </Banner>
      )}
      {sent && !sent.captain && (
        <Banner status="pending" title={`Request sent to ${sent.team.name}`}>
          You'll join when {sent.team.captain_name ?? "the Captain"} accepts. We'll show it in Teams.
        </Banner>
      )}
      {error && <Banner status="cancelled" title={error} />}

      <LoadState result={results} retry={retry} what="Teams" forbidden={NOT_A_PLAYER}>
        {(teams) =>
          teams.length === 0 ? (
            <p className="body la-muted">No Teams match. Try another name or Night.</p>
          ) : (
            <ul className="la-group" aria-label="Teams found">
              {teams.map((team) => {
                const request = pending.get(team.id);
                return (
                  <li key={team.id} className="la-item">
                    <div className="la-item__body">
                      <span className="body-strong">{team.name}</span>
                      <span className="caption la-muted">{teamLine(team)}</span>
                      <span className="caption la-muted">
                        Captain: {team.captain_name ?? "none yet"} · {playersLine(team.players)}
                      </span>
                    </div>
                    {inTeam.has(team.id) ? (
                      <StatusChip status="confirmed">You're in</StatusChip>
                    ) : request ? (
                      <JoinStatus request={request} />
                    ) : (
                      <button
                        type="button"
                        className="la-btn la-btn--secondary la-btn--sm"
                        aria-label={`Ask to join ${team.name}`}
                        disabled={asking === team.id}
                        onClick={() => void join(team)}
                      >
                        Ask to join
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )
        }
      </LoadState>
    </main>
  );
}
