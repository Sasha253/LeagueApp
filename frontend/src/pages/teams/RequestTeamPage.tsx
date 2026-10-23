// Create team request (design/src/ds/Screens.md, Captain 2): pick a Season, then a Night
// and Division from selectable rows, name the Team, and send it to the club's Admin.
// Whether a Division takes Teams (fee set, not full) is decided by the API.

import { useState } from "react";
import { Link } from "react-router";
import { api, type Schemas } from "../../api/client";
import type { FormErrors } from "../../api/errors";
import { useAuth } from "../../auth/AuthProvider";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { TextField } from "../../components/TextField";
import { formatDate, formatRand, WEEKDAYS } from "../../format";
import { LoadState, NO_ERRORS, send, useLoad } from "../club/shared";
import { NOT_A_PLAYER } from "./MyTeamsPage";
import { ScreenHeader, type Team } from "./shared";

type Division = Schemas["DivisionOption"];
type Season = Schemas["SeasonOption"];

function divisionDetail(division: Division): string {
  const fee = division.effective_league_fee ? `${formatRand(division.effective_league_fee)} league fee` : null;
  const teams =
    division.max_teams == null ? `${division.teams} Teams` : `${division.teams} of ${division.max_teams} Teams`;
  return [fee, teams, `min ${division.min_players} players`].filter(Boolean).join(" · ");
}

function closedReason(division: Division): string | null {
  if (division.is_open) return null;
  return division.effective_league_fee ? "Full" : "Not open yet";
}

export function RequestTeamPage() {
  const [seasons, retry] = useLoad(() => api.GET("/api/v1/seasons/"), "season-options");
  const [season, setSeason] = useState<Season | null>(null);
  const [sent, setSent] = useState<Team | null>(null);
  const { setMe } = useAuth();

  // The new Team is one this Player captains, so "me" changes.
  const onSent = (team: Team) => {
    setSent(team);
    api
      .GET("/api/v1/auth/me/")
      .then(({ data }) => data && setMe(data))
      .catch(() => {});
  };

  if (sent) {
    return (
      <main className="la-screen">
        <ScreenHeader title="Request a Team" back={{ label: "Teams", to: "/teams" }} />
        <Banner status="pending" title={`${sent.name} is waiting for the Admin`}>
          {sent.club.name} will confirm or decline it. You're its Captain, and Players can ask to join once it's
          confirmed.
        </Banner>
        <Link className="la-btn la-btn--primary la-btn--block" to={`/teams/${sent.id}`}>
          Open {sent.name}
        </Link>
      </main>
    );
  }

  return (
    <main className="la-screen">
      <ScreenHeader title="Request a Team" back={{ label: "Teams", to: "/teams" }} />
      <LoadState result={seasons} retry={retry} what="Seasons" forbidden={NOT_A_PLAYER}>
        {(list) =>
          list.length === 0 ? (
            <p className="body la-muted">No Season is open for Teams right now.</p>
          ) : (
            <>
              <fieldset className="la-fieldset la-stack-2">
                <legend className="la-overline">Season</legend>
                <div className="la-choices">
                  {list.map((option) => (
                    <ChoiceChip
                      key={option.id}
                      pressed={season?.id === option.id}
                      onToggle={() => setSeason(option)}
                    >
                      {`${option.name} · ${option.club.name}`}
                    </ChoiceChip>
                  ))}
                </div>
                {season && (
                  <p className="caption la-muted">
                    {formatDate(season.starts_on)} to {formatDate(season.ends_on)}
                  </p>
                )}
              </fieldset>
              {season && <TeamRequestForm key={season.id} season={season} onSent={onSent} />}
            </>
          )
        }
      </LoadState>
    </main>
  );
}

function TeamRequestForm({ season, onSent }: { season: Season; onSent: (team: Team) => void }) {
  const [divisions, retry] = useLoad(
    () => api.GET("/api/v1/seasons/{season_id}/divisions/", { params: { path: { season_id: season.id } } }),
    `season-divisions-${season.id}`,
  );
  const [division, setDivision] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (division === null) return;
    setBusy(true);
    let team: Team | undefined;
    const failed = await send(async () => {
      const answer = await api.POST("/api/v1/teams/", { body: { season: season.id, division, name: name.trim() } });
      team = answer.data;
      return answer;
    });
    setBusy(false);
    if (failed) setErrors(failed);
    else if (team) onSent(team);
  }

  return (
    <LoadState result={divisions} retry={retry} what="Divisions" forbidden={NOT_A_PLAYER}>
      {(list) => (
        <form
          className="la-stack"
          aria-label="New Team"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <fieldset className="la-fieldset la-stack-2">
            <legend className="la-overline">Night and Division</legend>
            {list.length === 0 ? (
              <p className="body la-muted">{season.club.name} has no Divisions yet.</p>
            ) : (
              <ul className="la-group">
                {list.map((option) => {
                  const closed = closedReason(option);
                  return (
                    <li key={option.id}>
                      <button
                        type="button"
                        className="la-item la-item--choice"
                        aria-pressed={division === option.id}
                        disabled={!option.is_open}
                        onClick={() => setDivision(option.id)}
                      >
                        <span className="la-item__body">
                          <span className="body-strong">
                            {WEEKDAYS[option.weekday]} · {option.name}
                          </span>
                          <span className="caption la-muted">{divisionDetail(option)}</span>
                          {closed && <span className="caption">{closed}</span>}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
            {errors.fields.division && <span className="la-field__error">{errors.fields.division}</span>}
          </fieldset>
          <TextField
            label="Team name"
            value={name}
            placeholder="Red Lions"
            maxLength={60}
            onChange={(event) => setName(event.target.value)}
            error={errors.fields.name}
          />
          {errors.general && <Banner status="cancelled" title={errors.general} />}
          <button
            type="submit"
            className="la-btn la-btn--primary la-btn--block"
            disabled={busy || division === null || !name.trim()}
          >
            Send to Admin
          </button>
        </form>
      )}
    </LoadState>
  );
}
