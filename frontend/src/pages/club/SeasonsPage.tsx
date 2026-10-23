// Seasons (FR-42): when each of the Club's Seasons runs.

import { useState } from "react";
import { api, type Schemas } from "../../api/client";
import type { FormErrors } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { TextField } from "../../components/TextField";
import { formatDate } from "../../format";
import { ConfirmButton, LoadState, NO_ERRORS, send, SetupHeader, useClub, useLoad } from "./shared";

type Season = Schemas["Season"];
type Draft = { name: string; starts_on: string; ends_on: string };
const EMPTY: Draft = { name: "", starts_on: "", ends_on: "" };

export function SeasonsPage() {
  const { clubId } = useClub();
  const path = { club_id: clubId };
  const [seasons, reload] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/seasons/", { params: { path } }),
    `seasons-${clubId}`,
  );
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function remove(season: Season) {
    const failed = await send(() =>
      api.DELETE("/api/v1/clubs/{club_id}/seasons/{id}/", { params: { path: { ...path, id: season.id } } }),
    );
    setError(failed?.general ?? null);
    if (!failed) reload();
  }

  const saved = () => {
    setEditing(null);
    reload();
  };

  return (
    <main className="la-screen">
      <SetupHeader title="Seasons" />
      <LoadState result={seasons} retry={reload} what="Seasons">
        {(list) => (
          <>
            {list.length === 0 && editing !== "new" && <p className="body la-muted">No Seasons yet.</p>}
            {list.length > 0 && (
              <ul className="la-group">
                {list.map((season) =>
                  editing === season.id ? (
                    <li key={season.id} className="la-item">
                      <SeasonForm clubId={clubId} season={season} onSaved={saved} onCancel={() => setEditing(null)} />
                    </li>
                  ) : (
                    <li key={season.id} className="la-item">
                      <div className="la-item__body">
                        <span className="body-strong">{season.name}</span>
                        <span className="caption la-muted">
                          {formatDate(season.starts_on)} to {formatDate(season.ends_on)}
                        </span>
                      </div>
                      <button
                        type="button"
                        className="la-btn la-btn--quiet la-btn--sm"
                        aria-label={`Edit ${season.name}`}
                        onClick={() => setEditing(season.id)}
                      >
                        Edit
                      </button>
                      <ConfirmButton
                        label="Delete"
                        confirmLabel={`Delete ${season.name}`}
                        onConfirm={() => remove(season)}
                      />
                    </li>
                  ),
                )}
              </ul>
            )}
            {error && <Banner status="cancelled" title={error} />}
            {editing === "new" ? (
              <SeasonForm clubId={clubId} onSaved={saved} onCancel={() => setEditing(null)} />
            ) : (
              <button type="button" className="la-btn la-btn--secondary la-btn--block" onClick={() => setEditing("new")}>
                Add a Season
              </button>
            )}
          </>
        )}
      </LoadState>
    </main>
  );
}

function SeasonForm({
  clubId,
  season,
  onSaved,
  onCancel,
}: {
  clubId: number;
  season?: Season;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<Draft>(season ?? EMPTY);
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [busy, setBusy] = useState(false);
  const path = { club_id: clubId };

  async function save() {
    setBusy(true);
    const body = { name: draft.name, starts_on: draft.starts_on, ends_on: draft.ends_on };
    const failed = await send(() =>
      season
        ? api.PATCH("/api/v1/clubs/{club_id}/seasons/{id}/", { params: { path: { ...path, id: season.id } }, body })
        : api.POST("/api/v1/clubs/{club_id}/seasons/", { params: { path }, body }),
    );
    setBusy(false);
    if (failed) setErrors(failed);
    else onSaved();
  }

  return (
    <form
      className="la-stack la-form"
      aria-label={season ? `Edit ${season.name}` : "New Season"}
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
    >
      <TextField
        label="Name"
        value={draft.name}
        placeholder="Spring 2026"
        onChange={(event) => setDraft({ ...draft, name: event.target.value })}
        error={errors.fields.name}
      />
      <TextField
        label="Starts on"
        type="date"
        value={draft.starts_on}
        onChange={(event) => setDraft({ ...draft, starts_on: event.target.value })}
        error={errors.fields.starts_on}
      />
      <TextField
        label="Ends on"
        type="date"
        value={draft.ends_on}
        onChange={(event) => setDraft({ ...draft, ends_on: event.target.value })}
        error={errors.fields.ends_on}
      />
      {errors.general && <Banner status="cancelled" title={errors.general} />}
      <div className="la-actions">
        <button type="submit" className="la-btn la-btn--primary" disabled={busy}>
          Save
        </button>
        <button type="button" className="la-btn la-btn--secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
