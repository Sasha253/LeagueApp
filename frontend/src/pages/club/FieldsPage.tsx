// Fields (FR-42, FR-8): the Club's pitches, each with the Referee who gets its updates.

import { useState } from "react";
import { api, type Schemas } from "../../api/client";
import type { FormErrors } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { TextField } from "../../components/TextField";
import { ConfirmButton, LoadState, NO_ERRORS, send, SetupHeader, useClub, useLoad } from "./shared";

type Field = Schemas["Field"];
type Member = Schemas["ClubMember"];

export function FieldsPage() {
  const { clubId } = useClub();
  const path = { club_id: clubId };
  const [data, reload] = useLoad(async () => {
    const [fields, members] = await Promise.all([
      api.GET("/api/v1/clubs/{club_id}/fields/", { params: { path } }),
      api.GET("/api/v1/clubs/{club_id}/members/", { params: { path } }),
    ]);
    const failed = !fields.data ? fields : !members.data ? members : null;
    if (failed) return { error: failed.error, response: failed.response };
    const referees = members.data!.filter((member) => member.role === "referee");
    return { data: { fields: fields.data!, referees }, response: fields.response };
  }, `fields-${clubId}`);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function remove(field: Field) {
    const failed = await send(() =>
      api.DELETE("/api/v1/clubs/{club_id}/fields/{id}/", { params: { path: { ...path, id: field.id } } }),
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
      <SetupHeader title="Fields" />
      <LoadState result={data} retry={reload} what="Fields">
        {({ fields, referees }) => (
          <>
            {fields.length === 0 && editing !== "new" && <p className="body la-muted">No Fields yet.</p>}
            {fields.length > 0 && (
              <ul className="la-group">
                {fields.map((field) => (
                  <li key={field.id} className="la-item">
                    {editing === field.id ? (
                      <FieldForm
                        clubId={clubId}
                        field={field}
                        referees={referees}
                        onSaved={saved}
                        onCancel={() => setEditing(null)}
                      />
                    ) : (
                      <>
                        <div className="la-item__body">
                          <span className="body-strong">{field.name}</span>
                          <span className="caption la-muted">
                            {field.referee_name ? `Referee: ${field.referee_name}` : "No Referee"}
                          </span>
                        </div>
                        <button
                          type="button"
                          className="la-btn la-btn--quiet la-btn--sm"
                          aria-label={`Edit ${field.name}`}
                          onClick={() => setEditing(field.id)}
                        >
                          Edit
                        </button>
                        <ConfirmButton label="Delete" confirmLabel={`Delete ${field.name}`} onConfirm={() => remove(field)} />
                      </>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {error && <Banner status="cancelled" title={error} />}
            {editing === "new" ? (
              <FieldForm clubId={clubId} referees={referees} onSaved={saved} onCancel={() => setEditing(null)} />
            ) : (
              <button type="button" className="la-btn la-btn--secondary la-btn--block" onClick={() => setEditing("new")}>
                Add a Field
              </button>
            )}
          </>
        )}
      </LoadState>
    </main>
  );
}

function FieldForm({
  clubId,
  field,
  referees,
  onSaved,
  onCancel,
}: {
  clubId: number;
  field?: Field;
  referees: Member[];
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(field?.name ?? "");
  const [referee, setReferee] = useState<number | null>(field?.referee ?? null);
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [busy, setBusy] = useState(false);
  const path = { club_id: clubId };

  async function save() {
    setBusy(true);
    const body = { name, referee };
    const failed = await send(() =>
      field
        ? api.PATCH("/api/v1/clubs/{club_id}/fields/{id}/", { params: { path: { ...path, id: field.id } }, body })
        : api.POST("/api/v1/clubs/{club_id}/fields/", { params: { path }, body }),
    );
    setBusy(false);
    if (failed) setErrors(failed);
    else onSaved();
  }

  return (
    <form
      className="la-stack la-form"
      aria-label={field ? `Edit ${field.name}` : "New Field"}
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
    >
      <TextField
        label="Name"
        value={name}
        placeholder="Pitch 1"
        onChange={(event) => setName(event.target.value)}
        error={errors.fields.name}
      />
      <fieldset className="la-fieldset la-stack-2">
        <legend className="la-field__label">Referee</legend>
        <div className="la-choices">
          <ChoiceChip pressed={referee === null} onToggle={() => setReferee(null)}>
            None
          </ChoiceChip>
          {referees.map((member) => (
            <ChoiceChip
              key={member.user_id}
              pressed={referee === member.user_id}
              onToggle={() => setReferee(member.user_id)}
            >
              {member.name}
            </ChoiceChip>
          ))}
        </div>
        {referees.length === 0 && (
          <span className="la-field__help">Invite a Referee in People first.</span>
        )}
        {errors.fields.referee && <span className="la-field__error">{errors.fields.referee}</span>}
      </fieldset>
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
