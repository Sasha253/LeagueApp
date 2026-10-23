// The Admin's reschedule (design/src/ds/Screens.md, Admin 2): a new date, time and pitch,
// then a preview from the backend of who is told (FR-7, FR-8) and whether Confirmations go
// out now (FR-9) before the Admin confirms. And the match's Captain requests (FR-18) with
// Accept and Decline; accepting a postponement moves the match to the time picked here.
// Every rule (cutoffs, the Night, the Season, a free pitch) is the backend's; this only
// sends what the Admin picked and shows the answer.

import { useState } from "react";
import { api, type Schemas } from "../../api/client";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { TextField } from "../../components/TextField";
import { formatMoment, formatTime, localDate, southAfricanMoment } from "../../format";
import { NO_ERRORS, send, useLoad } from "../club/shared";
import type { FormErrors } from "../../api/errors";
import { FIXTURE_STATUS } from "./shared";
import { REQUEST_KIND, RequestStatus, requestDetail, requestTitle, type CaptainRequest } from "./requests";

type Fixture = Schemas["AdminFixtureDetail"];
type Preview = Schemas["ReschedulePreview"];

/** What the Admin picked: a South African date and time, and a pitch. */
export type Move = { date: string; time: string; pitchId: number };

export function moveOf(fixture: Fixture): Move {
  return { date: localDate(fixture.kick_off), time: formatTime(fixture.kick_off), pitchId: fixture.pitch.id };
}

export function moveBody(move: Move) {
  return { kick_off: southAfricanMoment(move.date, move.time), pitch: move.pitchId };
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function previewText(p: Preview): string {
  const told = `Tells ${plural(p.players, "Player")} of both Teams and ${plural(p.officials, "official")} (the Night's Admins and the pitch's Referee).`;
  if (!p.kick_off_changed) return `${told} Replies stand.`;
  const replies = p.answer_by ? ` Replies close ${formatMoment(p.answer_by)}.` : "";
  return p.confirmations_now
    ? `${told} Confirmations go out now.${replies}`
    : `${told} The match goes back to ${FIXTURE_STATUS[p.status_after].label.toLowerCase()}; Confirmations go out as usual.${replies}`;
}

function firstError(errors: FormErrors): string {
  return errors.general ?? Object.values(errors.fields)[0] ?? "That didn't work.";
}

export function RescheduleSection({
  clubId,
  fixture,
  move,
  onMove,
  onDone,
}: {
  clubId: number;
  fixture: Fixture;
  move: Move;
  onMove: (move: Move) => void;
  onDone: () => void;
}) {
  const [pitches] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/fields/", { params: { path: { club_id: clubId } } }),
    `fields-${clubId}`,
  );
  const [preview, setPreview] = useState<Preview | null>(null);
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const path = { club_id: clubId, id: fixture.id };

  function change(next: Partial<Move>) {
    onMove({ ...move, ...next });
    setPreview(null);
  }

  async function check() {
    setBusy(true);
    let shown: Preview | null = null;
    const failed = await send(async () => {
      const answer = await api.POST("/api/v1/clubs/{club_id}/fixtures/{id}/reschedule/preview/", {
        params: { path },
        body: moveBody(move),
      });
      shown = answer.data ?? null;
      return answer;
    });
    setBusy(false);
    setErrors(failed ?? NO_ERRORS);
    setPreview(failed ? null : shown);
  }

  async function confirm() {
    setBusy(true);
    const failed = await send(() =>
      api.POST("/api/v1/clubs/{club_id}/fixtures/{id}/reschedule/", {
        params: { path },
        body: { ...moveBody(move), note },
      }),
    );
    setBusy(false);
    setErrors(failed ?? NO_ERRORS);
    if (!failed) {
      setPreview(null);
      setNote("");
      onDone();
    }
  }

  return (
    <section className="la-stack-2" aria-labelledby="reschedule">
      <h2 id="reschedule" className="la-overline">
        Reschedule
      </h2>
      <div className="la-form">
        <TextField
          label="Date"
          type="date"
          value={move.date}
          onChange={(e) => change({ date: e.target.value })}
          error={errors.fields.kick_off}
        />
        <TextField label="Kick-off" type="time" value={move.time} onChange={(e) => change({ time: e.target.value })} />
        {pitches.state === "ok" && (
          <fieldset className="la-fieldset la-stack-2">
            <legend className="la-overline">Pitch</legend>
            <div className="la-choices">
              {pitches.data.map((p) => (
                <ChoiceChip key={p.id} pressed={move.pitchId === p.id} onToggle={() => change({ pitchId: p.id })}>
                  {p.name}
                </ChoiceChip>
              ))}
            </div>
            {errors.fields.pitch && <span className="la-field__error">{errors.fields.pitch}</span>}
          </fieldset>
        )}
        <TextField label="Note (optional)" value={note} maxLength={300} onChange={(e) => setNote(e.target.value)} />
      </div>
      {errors.general && <Banner status="cancelled" title={errors.general} />}
      {preview ? (
        <>
          <Banner status="info" title={`Move to ${formatMoment(preview.kick_off)}, ${preview.pitch.name}`}>
            {previewText(preview)}
          </Banner>
          <div className="la-actions">
            <button type="button" className="la-btn la-btn--primary" disabled={busy} onClick={() => void confirm()}>
              Reschedule
            </button>
            <button type="button" className="la-btn la-btn--quiet" onClick={() => setPreview(null)}>
              Not now
            </button>
          </div>
        </>
      ) : (
        <button type="button" className="la-btn la-btn--secondary" disabled={busy} onClick={() => void check()}>
          Check who is told
        </button>
      )}
    </section>
  );
}

export function CaptainRequestsSection({
  clubId,
  requests,
  move,
  onDone,
}: {
  clubId: number;
  requests: CaptainRequest[];
  move: Move;
  onDone: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function decide(request: CaptainRequest, decision: "accept" | "decline") {
    setBusy(true);
    const path = { club_id: clubId, id: request.id };
    const failed = await send(() =>
      decision === "decline"
        ? api.POST("/api/v1/clubs/{club_id}/captain-requests/{id}/decline/", { params: { path }, body: {} })
        : api.POST("/api/v1/clubs/{club_id}/captain-requests/{id}/accept/", {
            params: { path },
            body: request.kind === "postpone" ? moveBody(move) : {},
          }),
    );
    setBusy(false);
    setError(failed ? firstError(failed) : null);
    if (!failed) onDone();
  }

  if (requests.length === 0) return null;
  return (
    <section className="la-stack-2" aria-labelledby="captain-requests">
      <h2 id="captain-requests" className="la-overline">
        Captain requests
      </h2>
      <ul className="la-group" aria-label="Captain requests">
        {requests.map((r) => (
          <li key={r.id} className="la-item">
            <span className="la-item__body">
              <span className="body-strong">{requestTitle(r)}</span>
              <span className="caption">{r.reason}</span>
              <span className="caption la-muted">{requestDetail(r)}</span>
              {r.status === "pending" && (
                <span className="la-actions">
                  <button
                    type="button"
                    className="la-btn la-btn--primary la-btn--sm"
                    disabled={busy}
                    onClick={() => void decide(r, "accept")}
                  >
                    {r.kind === "postpone" ? "Accept: move to the time above" : `Accept: ${r.team.name} out`}
                  </button>
                  <button
                    type="button"
                    className="la-btn la-btn--quiet la-btn--sm"
                    disabled={busy}
                    onClick={() => void decide(r, "decline")}
                  >
                    Decline
                  </button>
                </span>
              )}
            </span>
            <RequestStatus request={r} />
          </li>
        ))}
      </ul>
      <p className="caption la-muted">
        {REQUEST_KIND.cancel}: the Team is out and the slot is offered to other Teams. {REQUEST_KIND.postpone}: pick the
        new date, time and pitch under Reschedule, then accept.
      </p>
      {error && <Banner status="cancelled" title={error} />}
    </section>
  );
}
