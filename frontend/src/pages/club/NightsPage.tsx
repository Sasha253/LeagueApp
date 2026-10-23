// Nights and Divisions (FR-42, FR-5): the weekdays the Club plays on, and each Night's
// Divisions with their minimum players and, when it differs, their own league fee.
// Nights and Divisions carry over from Season to Season (docs/DECISIONS.md).

import { useState } from "react";
import { Link } from "react-router";
import { api, type Schemas } from "../../api/client";
import type { FormErrors } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { TextField } from "../../components/TextField";
import { formatRand, WEEKDAYS, WEEKDAYS_SHORT } from "../../format";
import { ConfirmButton, LoadState, NO_ERRORS, send, SetupHeader, useClub, useLoad } from "./shared";

type Night = Schemas["ClubNight"];
type Division = Schemas["Division"];
type Editing = { nightId: number; divisionId: number | "new" } | null;

function feeLine(division: Division): string {
  if (division.effective_league_fee === null) return "League fee not set";
  const fee = `${formatRand(division.effective_league_fee)} per Team`;
  return division.league_fee === null || division.league_fee === undefined ? `${fee} (club fee)` : fee;
}

export function NightsPage() {
  const { clubId } = useClub();
  const path = { club_id: clubId };
  const [nights, reload] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/nights/", { params: { path } }),
    `nights-${clubId}`,
  );
  const [editing, setEditing] = useState<Editing>(null);
  const [error, setError] = useState<string | null>(null);

  async function act(call: () => Promise<{ error?: unknown; response: Response }>) {
    const failed = await send(call);
    setError(failed ? (failed.general ?? Object.values(failed.fields)[0] ?? null) : null);
    if (!failed) reload();
  }

  const addNight = (weekday: Schemas["WeekdayEnum"]) =>
    act(() => api.POST("/api/v1/clubs/{club_id}/nights/", { params: { path }, body: { weekday } }));
  const removeNight = (night: Night) =>
    act(() => api.DELETE("/api/v1/clubs/{club_id}/nights/{id}/", { params: { path: { ...path, id: night.id } } }));
  const removeDivision = (division: Division) =>
    act(() =>
      api.DELETE("/api/v1/clubs/{club_id}/divisions/{id}/", { params: { path: { ...path, id: division.id } } }),
    );
  const saved = () => {
    setEditing(null);
    reload();
  };

  return (
    <main className="la-screen">
      <SetupHeader title="Nights and Divisions" />
      <Link className="la-btn la-btn--secondary" to={`/clubs/${clubId}/setup/nights/import`}>
        Import from a spreadsheet
      </Link>
      <LoadState result={nights} retry={reload} what="Nights">
        {(list) => {
          const used = new Set(list.map((night) => night.weekday));
          const free = ([0, 1, 2, 3, 4, 5, 6] as const).filter((day) => !used.has(day));
          return (
            <>
              {list.length === 0 && <p className="body la-muted">No Nights yet. Add the weekdays you play on.</p>}
              {error && <Banner status="cancelled" title={error} />}
              {list.map((night) => (
                <section key={night.id} className="la-stack-2" aria-labelledby={`night-${night.id}`}>
                  <div className="la-section-head">
                    <h2 id={`night-${night.id}`} className="la-overline">
                      {WEEKDAYS[night.weekday]}
                    </h2>
                    {night.divisions.length === 0 && (
                      <ConfirmButton
                        label="Delete"
                        confirmLabel={`Delete ${WEEKDAYS[night.weekday]}`}
                        onConfirm={() => removeNight(night)}
                      />
                    )}
                  </div>
                  {night.divisions.length > 0 && (
                    <ul className="la-group">
                      {night.divisions.map((division) => (
                        <li key={division.id} className="la-item">
                          {editing?.divisionId === division.id ? (
                            <DivisionForm
                              clubId={clubId}
                              nightId={night.id}
                              division={division}
                              onSaved={saved}
                              onCancel={() => setEditing(null)}
                            />
                          ) : (
                            <>
                              <div className="la-item__body">
                                <span className="body-strong">{division.name}</span>
                                <span className="caption la-muted">
                                  Minimum {division.min_players} players · {feeLine(division)}
                                </span>
                              </div>
                              <button
                                type="button"
                                className="la-btn la-btn--quiet la-btn--sm"
                                aria-label={`Edit ${division.name}`}
                                onClick={() => setEditing({ nightId: night.id, divisionId: division.id })}
                              >
                                Edit
                              </button>
                              <ConfirmButton
                                label="Delete"
                                confirmLabel={`Delete ${division.name}`}
                                onConfirm={() => removeDivision(division)}
                              />
                            </>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                  {editing?.nightId === night.id && editing.divisionId === "new" ? (
                    <DivisionForm clubId={clubId} nightId={night.id} onSaved={saved} onCancel={() => setEditing(null)} />
                  ) : (
                    <button
                      type="button"
                      className="la-btn la-btn--secondary"
                      onClick={() => setEditing({ nightId: night.id, divisionId: "new" })}
                    >
                      Add a Division to {WEEKDAYS[night.weekday]}
                    </button>
                  )}
                </section>
              ))}
              {free.length > 0 && (
                <fieldset className="la-fieldset la-stack-2">
                  <legend className="la-overline">Add a Night</legend>
                  <div className="la-choices">
                    {free.map((day) => (
                      <ChoiceChip key={day} pressed={false} onToggle={() => addNight(day)} label={`Add ${WEEKDAYS[day]}`}>
                        {WEEKDAYS_SHORT[day]}
                      </ChoiceChip>
                    ))}
                  </div>
                </fieldset>
              )}
            </>
          );
        }}
      </LoadState>
    </main>
  );
}

function DivisionForm({
  clubId,
  nightId,
  division,
  onSaved,
  onCancel,
}: {
  clubId: number;
  nightId: number;
  division?: Division;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(division?.name ?? "");
  // Empty for a new Division: the API starts it from the club's minimum.
  const [minPlayers, setMinPlayers] = useState(division ? String(division.min_players) : "");
  const [fee, setFee] = useState(division?.league_fee ?? "");
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [busy, setBusy] = useState(false);
  const path = { club_id: clubId };

  async function save() {
    setBusy(true);
    const body = {
      night: nightId,
      name,
      league_fee: fee.trim() || null,
      ...(minPlayers.trim() ? { min_players: Number(minPlayers) } : {}),
    };
    const failed = await send(() =>
      division
        ? api.PATCH("/api/v1/clubs/{club_id}/divisions/{id}/", { params: { path: { ...path, id: division.id } }, body })
        : api.POST("/api/v1/clubs/{club_id}/divisions/", { params: { path }, body }),
    );
    setBusy(false);
    if (failed) setErrors(failed);
    else onSaved();
  }

  return (
    <form
      className="la-stack la-form"
      aria-label={division ? `Edit ${division.name}` : "New Division"}
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
    >
      <TextField
        label="Name"
        value={name}
        placeholder="Division 1"
        onChange={(event) => setName(event.target.value)}
        error={errors.fields.name}
      />
      <TextField
        label="Minimum players"
        inputMode="numeric"
        value={minPlayers}
        onChange={(event) => setMinPlayers(event.target.value)}
        help={division ? "Fewer confirmed at the squad check and the Team is out." : "Leave empty for the club's minimum."}
        error={errors.fields.min_players}
      />
      <TextField
        label="League fee per Team (R)"
        inputMode="decimal"
        value={fee}
        onChange={(event) => setFee(event.target.value)}
        help="Leave empty to use the club's fee."
        error={errors.fields.league_fee}
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
