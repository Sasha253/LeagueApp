// Request a player (design/src/ds/Screens.md, Captain 4): the Captain picks Player or
// Goalkeeper and how many, sees who will be asked, and sends it (FR-35, FR-36). Who is
// asked, the most places and whether it can be sent now are the backend's answers.

import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router";
import { api } from "../../api/client";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { LoadState, NO_ERRORS, send, useLoad } from "../club/shared";
import { ScreenHeader } from "../teams/shared";
import { MatchCard } from "./shared";
import { NOT_A_PLAYER } from "./MyFixturesPage";
import { KIND_PLURAL, wanted, type PlayerRequestKind } from "./playerRequests";

const KINDS: { kind: PlayerRequestKind; label: string }[] = [
  { kind: "player", label: "Player" },
  { kind: "goalkeeper", label: "Goalkeeper" },
];

export function RequestPlayerPage() {
  const id = Number(useParams().fixtureId);
  const navigate = useNavigate();
  const [fixture, reload] = useLoad(
    () => api.GET("/api/v1/fixtures/{id}/", { params: { path: { id } } }),
    `fixture-${id}`,
  );
  const [kind, setKind] = useState<PlayerRequestKind>("player");
  const [places, setPlaces] = useState(1);
  const [preview] = useLoad(
    () =>
      api.GET("/api/v1/fixtures/{id}/player-requests/preview/", {
        params: { path: { id }, query: { kind } },
      }),
    `player-request-preview-${id}-${kind}`,
  );
  const [errors, setErrors] = useState(NO_ERRORS);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    const failed = await send(() =>
      api.POST("/api/v1/fixtures/{id}/player-requests/", { params: { path: { id } }, body: { kind, places } }),
    );
    setBusy(false);
    setErrors(failed ?? NO_ERRORS);
    if (!failed) navigate(`/fixtures/${id}`);
  }

  const planned = preview.state === "ok" ? preview.data : null;
  const most = planned?.max_places ?? 1;
  const counts = Array.from({ length: most }, (_, i) => i + 1);

  return (
    <main className="la-screen">
      <ScreenHeader title="Request a player" back={{ label: "Match", to: `/fixtures/${id}` }} />
      <LoadState result={fixture} retry={reload} what="match" forbidden={NOT_A_PLAYER}>
        {(match) => (
          <form className="la-form" onSubmit={(e) => void submit(e)} noValidate>
            <MatchCard fixture={match} />
            <fieldset className="la-fieldset la-stack-2">
              <legend className="la-overline">Who you need</legend>
              <div className="la-choices">
                {KINDS.map((k) => (
                  <ChoiceChip key={k.kind} pressed={kind === k.kind} onToggle={() => setKind(k.kind)}>
                    {k.label}
                  </ChoiceChip>
                ))}
              </div>
            </fieldset>
            <fieldset className="la-fieldset la-stack-2">
              <legend className="la-overline">How many</legend>
              <div className="la-choices">
                {counts.map((n) => (
                  <ChoiceChip key={n} pressed={places === n} onToggle={() => setPlaces(n)}>
                    {String(n)}
                  </ChoiceChip>
                ))}
              </div>
              {errors.fields.places && <p className="la-field__error">{errors.fields.places}</p>}
            </fieldset>
            {planned && (
              <Banner
                status={planned.recipients > 0 ? "info" : "pending"}
                title={
                  planned.recipients > 0
                    ? `${planned.recipients} ${KIND_PLURAL[kind]} will be asked`
                    : `No ${KIND_PLURAL[kind]} to ask`
                }
              >
                {`Only ${KIND_PLURAL[kind]} on ${planned.night} who are in neither team. The first to accept join your team for this match.`}
              </Banner>
            )}
            {errors.general && <Banner status="cancelled" title={errors.general} />}
            <button
              type="submit"
              className="la-btn la-btn--primary la-btn--block"
              disabled={busy || planned?.recipients === 0}
            >
              {`Ask for ${wanted(kind, places)}`}
            </button>
          </form>
        )}
      </LoadState>
    </main>
  );
}
