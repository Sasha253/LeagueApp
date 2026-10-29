// Add a Fixture (docs/DECISIONS.md): one match between two active Teams of a Division, on a
// pitch, at a South African kick-off. The API checks it as a row of the league import (on
// the Division's Night, inside the Season, still to come, pitch and Teams free).

import { useState } from "react";
import { useNavigate } from "react-router";
import { api } from "../../api/client";
import { formErrors, unreachable, type FormErrors } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { TextField } from "../../components/TextField";
import { southAfricanMoment, WEEKDAYS_SHORT } from "../../format";
import { LoadState, NO_ERRORS, useClub, useLoad } from "../club/shared";
import { openingSeason } from "../finance/shared";
import { ScreenHeader } from "../teams/shared";

type Draft = {
  season: number | null;
  division: number | null;
  pitch: number | null;
  home: number | null;
  away: number | null;
  date: string;
  time: string;
  friendly: boolean;
};

const EMPTY: Draft = { season: null, division: null, pitch: null, home: null, away: null, date: "", time: "", friendly: false };

export function AddFixturePage() {
  const { clubId, clubName } = useClub();
  const path = { club_id: clubId };
  const [seasons, reloadSeasons] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/seasons/", { params: { path } }),
    `seasons-${clubId}`,
  );
  const [nights, reloadNights] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/nights/", { params: { path } }),
    `nights-${clubId}`,
  );
  const [fields, reloadFields] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/fields/", { params: { path } }),
    `fields-${clubId}`,
  );

  return (
    <main className="la-screen">
      <ScreenHeader title="Add a Fixture" back={{ label: "Club home", to: `/clubs/${clubId}` }} caption={clubName} />
      <LoadState result={seasons} retry={reloadSeasons} what="Seasons">
        {(seasonList) => (
          <LoadState result={nights} retry={reloadNights} what="Nights and Divisions">
            {(nightList) => (
              <LoadState result={fields} retry={reloadFields} what="Fields">
                {(fieldList) => {
                  const season = openingSeason(seasonList);
                  const divisions = nightList.flatMap((n) => n.divisions.map((d) => ({ ...d, weekday: n.weekday })));
                  if (season === null || divisions.length === 0 || fieldList.length === 0) {
                    return (
                      <Banner status="pending" title="Nothing to add a Fixture to yet">
                        A Fixture needs a Season, a Division and a Field. Add them in Club setup first.
                      </Banner>
                    );
                  }
                  return (
                    <FixtureForm
                      seasons={seasonList}
                      opening={season}
                      divisions={divisions}
                      fields={fieldList}
                    />
                  );
                }}
              </LoadState>
            )}
          </LoadState>
        )}
      </LoadState>
    </main>
  );
}

function FixtureForm({
  seasons,
  opening,
  divisions,
  fields,
}: {
  seasons: { id: number; name: string }[];
  opening: number;
  divisions: { id: number; name: string; weekday: number }[];
  fields: { id: number; name: string }[];
}) {
  const { clubId } = useClub();
  const navigate = useNavigate();
  const [draft, setDraft] = useState<Draft>({ ...EMPTY, season: opening });
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [busy, setBusy] = useState(false);
  const change = (next: Partial<Draft>) => setDraft({ ...draft, ...next });
  const pickScope = (next: Partial<Draft>) => change({ ...next, home: null, away: null });

  const { season, division } = draft;
  const [teams, reloadTeams] = useLoad(
    () =>
      api.GET("/api/v1/clubs/{club_id}/teams/", {
        params: {
          path: { club_id: clubId },
          query: { status: "active", season: season ?? undefined, division: division ?? undefined },
        },
      }),
    `club-teams-active-${clubId}-${season}-${division}`,
  );

  const ready =
    draft.division !== null && draft.pitch !== null && draft.home !== null && draft.away !== null && !!draft.date && !!draft.time;

  async function save() {
    const { season, division, pitch, home, away } = draft;
    if (season === null || division === null || pitch === null || home === null || away === null) return;
    setBusy(true);
    setErrors(NO_ERRORS);
    try {
      const { data, error } = await api.POST("/api/v1/clubs/{club_id}/fixtures/", {
        params: { path: { club_id: clubId } },
        body: {
          season,
          division,
          pitch,
          home_team: home,
          away_team: away,
          kick_off: southAfricanMoment(draft.date, draft.time),
          friendly_eligible: draft.friendly,
        },
      });
      if (data) navigate(`/clubs/${clubId}/fixtures/${data.id}`);
      else setErrors(formErrors(error));
    } catch {
      setErrors(unreachable);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="la-stack la-form"
      aria-label="New Fixture"
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
    >
      <Chips
        legend="Season"
        options={seasons}
        value={draft.season}
        onPick={(id) => pickScope({ season: id })}
        error={errors.fields.season}
      />
      <Chips
        legend="Division"
        options={divisions.map((d) => ({ id: d.id, name: `${WEEKDAYS_SHORT[d.weekday]} · ${d.name}` }))}
        value={draft.division}
        onPick={(id) => pickScope({ division: id })}
        error={errors.fields.division}
      />
      {draft.division !== null && (
        <LoadState result={teams} retry={reloadTeams} what="Teams">
          {(list) =>
            list.length < 2 ? (
              <p className="body la-muted">This Division needs two active Teams this Season.</p>
            ) : (
              <>
                <Chips
                  legend="Home"
                  options={list}
                  value={draft.home}
                  onPick={(id) => change({ home: id })}
                  error={errors.fields.home_team}
                />
                <Chips
                  legend="Away"
                  options={list.filter((t) => t.id !== draft.home)}
                  value={draft.away}
                  onPick={(id) => change({ away: id })}
                  error={errors.fields.away_team}
                />
              </>
            )
          }
        </LoadState>
      )}
      <Chips
        legend="Pitch"
        options={fields}
        value={draft.pitch}
        onPick={(id) => change({ pitch: id })}
        error={errors.fields.pitch}
      />
      <TextField
        label="Date"
        type="date"
        value={draft.date}
        onChange={(event) => change({ date: event.target.value })}
        error={errors.fields.kick_off}
      />
      <TextField
        label="Kick-off"
        type="time"
        value={draft.time}
        help="South African time, 24-hour"
        onChange={(event) => change({ time: event.target.value })}
      />
      <div className="la-choices">
        <ChoiceChip pressed={draft.friendly} onToggle={() => change({ friendly: !draft.friendly })}>
          Friendly-eligible
        </ChoiceChip>
      </div>
      {errors.general && <Banner status="cancelled" title={errors.general} />}
      <button type="submit" className="la-btn la-btn--primary la-btn--block" disabled={busy || !ready}>
        Add Fixture
      </button>
    </form>
  );
}

function Chips({
  legend,
  options,
  value,
  onPick,
  error,
}: {
  legend: string;
  options: { id: number; name: string }[];
  value: number | null;
  onPick: (id: number) => void;
  error?: string;
}) {
  return (
    <fieldset className="la-fieldset la-stack-2">
      <legend className="la-overline">{legend}</legend>
      <div className="la-choices">
        {options.map((option) => (
          <ChoiceChip
            key={option.id}
            pressed={value === option.id}
            onToggle={() => onPick(option.id)}
            label={`${legend}: ${option.name}`}
          >
            {option.name}
          </ChoiceChip>
        ))}
      </div>
      {error && <span className="la-field__error">{error}</span>}
    </fieldset>
  );
}
