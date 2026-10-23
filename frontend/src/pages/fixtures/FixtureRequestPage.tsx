// Cancel or postpone (design/src/ds/Screens.md, Captain 5): the Captain picks cancel or
// postpone, gives a reason and sends it to the Admin. Nothing changes until an Admin accepts
// it (FR-18); whether the Captain may send one now is the backend's answer.

import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router";
import { api } from "../../api/client";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { TextField } from "../../components/TextField";
import { LoadState, NO_ERRORS, send, useLoad } from "../club/shared";
import { ScreenHeader } from "../teams/shared";
import { MatchCard } from "./shared";
import { NOT_A_PLAYER } from "./MyFixturesPage";
import { REQUEST_KIND, type RequestKind } from "./requests";

const KINDS: RequestKind[] = ["cancel", "postpone"];

const WHAT_HAPPENS: Record<RequestKind, string> = {
  cancel: "If the Admin accepts, your Team is out of this match and the slot is offered to other Teams.",
  postpone: "If the Admin accepts, they pick the new date and time, and both Teams are told.",
};

export function FixtureRequestPage() {
  const id = Number(useParams().fixtureId);
  const navigate = useNavigate();
  const [fixture, reload] = useLoad(
    () => api.GET("/api/v1/fixtures/{id}/", { params: { path: { id } } }),
    `fixture-${id}`,
  );
  const [kind, setKind] = useState<RequestKind>("postpone");
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState(NO_ERRORS);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    const failed = await send(() =>
      api.POST("/api/v1/fixtures/{id}/requests/", { params: { path: { id } }, body: { kind, reason } }),
    );
    setBusy(false);
    setErrors(failed ?? NO_ERRORS);
    if (!failed) navigate(`/fixtures/${id}`);
  }

  return (
    <main className="la-screen">
      <ScreenHeader title="Cancel or postpone" back={{ label: "Match", to: `/fixtures/${id}` }} />
      <LoadState result={fixture} retry={reload} what="match" forbidden={NOT_A_PLAYER}>
        {(match) => (
          <form className="la-form" onSubmit={(e) => void submit(e)} noValidate>
            <MatchCard fixture={match} />
            <Banner status="pending" title="The Admin must accept it">
              Nothing changes until then. You'll be told when they decide.
            </Banner>
            <fieldset className="la-fieldset la-stack-2">
              <legend className="la-overline">Ask to</legend>
              <div className="la-choices">
                {KINDS.map((k) => (
                  <ChoiceChip key={k} pressed={kind === k} onToggle={() => setKind(k)}>
                    {REQUEST_KIND[k]}
                  </ChoiceChip>
                ))}
              </div>
              <p className="caption la-muted">{WHAT_HAPPENS[kind]}</p>
            </fieldset>
            <TextField
              label="Reason"
              value={reason}
              maxLength={300}
              required
              onChange={(e) => setReason(e.target.value)}
              help="The Admin reads this."
              error={errors.fields.reason}
            />
            {errors.general && <Banner status="cancelled" title={errors.general} />}
            <button type="submit" className="la-btn la-btn--primary la-btn--block" disabled={busy}>
              Send to Admin
            </button>
          </form>
        )}
      </LoadState>
    </main>
  );
}
