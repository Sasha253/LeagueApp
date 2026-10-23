// A Fixture for the club's Admin (design/src/ds/Screens.md, Admin 2): kick-off, teams, pitch
// and Referee, whether it may become a friendly, and every change of its status with who or
// what made it. Whether the flag can still change is the API's decision (409 otherwise).
// When one Team was out, the search for a new opponent (FR-13 to FR-16): who the slot was
// offered to, until when, and who took it.

import { useState } from "react";
import { useParams } from "react-router";
import { api, type Schemas } from "../../api/client";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { StatusChip, type Status } from "../../components/StatusChip";
import { formatMoment } from "../../format";
import { LoadState, send, useClub, useLoad } from "../club/shared";
import { ScreenHeader } from "../teams/shared";
import { FIXTURE_STATUS, MatchCard } from "./shared";
import { NOT_AN_ADMIN } from "./ClubFixturesPage";

type Transition = Schemas["FixtureTransition"];
type Replacement = Schemas["ReplacementOffer"];

const REPLACEMENT_STATUS: Record<Replacement["status"], { status: Status; label: string }> = {
  open: { status: "pending", label: "Offered" },
  accepted: { status: "confirmed", label: "Taken" },
  lapsed: { status: "cancelled", label: "No Team took it" },
  withdrawn: { status: "info", label: "Withdrawn" },
};

function replacementDetail(r: Replacement): string {
  const offered = r.offered_to.map((t) => t.name).join(", ");
  if (r.status === "accepted" && r.accepted_team) {
    const by = r.accepted_by_name ? ` (${r.accepted_by_name})` : "";
    return `${r.accepted_team.name} took the slot${by}${r.accepted_at ? `, ${formatMoment(r.accepted_at)}` : ""}.`;
  }
  if (r.offered_to.length === 0) return "No other Team could take the slot.";
  if (r.status === "open") return `Offered to ${offered} until ${formatMoment(r.closes_at)}.`;
  return `Offered to ${offered}.`;
}

const CAUSES: Record<Transition["cause"], string> = {
  import: "Fixture import",
  admin: "Admin",
  captain: "Captain",
  checkpoint: "Timed checkpoint",
  system: "League App",
};

function transitionTitle(t: Transition): string {
  const to = FIXTURE_STATUS[t.to_status].label;
  return t.from_status ? `${FIXTURE_STATUS[t.from_status].label} to ${to}` : `Added as ${to.toLowerCase()}`;
}

function transitionBy(t: Transition): string {
  const by = t.actor_name ? `${t.actor_name} (${CAUSES[t.cause]})` : CAUSES[t.cause];
  return `${formatMoment(t.at)} · ${by}`;
}

export function ClubFixturePage() {
  const { clubId, clubName } = useClub();
  const id = Number(useParams().fixtureId);
  const [fixture, reload] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/fixtures/{id}/", { params: { path: { club_id: clubId, id } } }),
    `club-fixture-${clubId}-${id}`,
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function setFriendlyEligible(value: boolean) {
    setSaving(true);
    const failed = await send(() =>
      api.PATCH("/api/v1/clubs/{club_id}/fixtures/{id}/", {
        params: { path: { club_id: clubId, id } },
        body: { friendly_eligible: value },
      }),
    );
    setSaving(false);
    setError(failed ? (failed.general ?? Object.values(failed.fields)[0] ?? "That didn't work.") : null);
    if (!failed) reload();
  }

  return (
    <main className="la-screen">
      <ScreenHeader title="Fixture" back={{ label: "Fixtures", to: `/clubs/${clubId}/fixtures` }} caption={clubName} />
      <LoadState result={fixture} retry={reload} what="fixture" forbidden={NOT_AN_ADMIN}>
        {(match) => (
          <>
            <MatchCard fixture={match} />
            <ul className="la-group">
              <li className="la-item">
                <span className="la-item__body">
                  <span className="caption la-muted">Pitch</span>
                  <span className="body-strong">{match.pitch.name}</span>
                  <span className="caption la-muted">Referee: {match.referee_name ?? "none yet"}</span>
                </span>
              </li>
              <li className="la-item">
                <span className="la-item__body">
                  <span className="caption la-muted">League</span>
                  <span className="body-strong">
                    {match.division.name} · {match.season.name}
                  </span>
                </span>
              </li>
            </ul>

            <section className="la-stack-2" aria-labelledby="friendly">
              <h2 id="friendly" className="la-overline">
                If it can't go ahead
              </h2>
              <p className="caption la-muted">
                A friendly-eligible match becomes a friendly when no replacement opponent is found. Otherwise it is
                cancelled and paid Players get credit.
              </p>
              <div className="la-choices">
                <ChoiceChip
                  pressed={match.friendly_eligible}
                  onToggle={() => !saving && void setFriendlyEligible(!match.friendly_eligible)}
                >
                  Friendly-eligible
                </ChoiceChip>
              </div>
              {match.friendly_eligible_changed_at && (
                <p className="caption la-muted">
                  Set {formatMoment(match.friendly_eligible_changed_at)}
                  {match.friendly_eligible_changed_by_name && ` by ${match.friendly_eligible_changed_by_name}`}
                </p>
              )}
              {error && <Banner status="cancelled" title={error} />}
            </section>

            {match.replacements.length > 0 && (
              <section className="la-stack-2" aria-labelledby="replacement">
                <h2 id="replacement" className="la-overline">
                  New opponent
                </h2>
                <ul className="la-group" aria-label="New opponent">
                  {match.replacements.map((r) => (
                    <li key={r.id} className="la-item">
                      <span className="la-item__body">
                        <span className="body-strong">{r.out_team.name} out</span>
                        <span className="caption la-muted">{replacementDetail(r)}</span>
                      </span>
                      <StatusChip status={REPLACEMENT_STATUS[r.status].status}>
                        {REPLACEMENT_STATUS[r.status].label}
                      </StatusChip>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section className="la-stack-2" aria-labelledby="history">
              <h2 id="history" className="la-overline">
                History
              </h2>
              <ul className="la-group" aria-label="History">
                {match.transitions.map((t) => (
                  <li key={t.id} className="la-item">
                    <span className="la-item__body">
                      <span className="body-strong">{transitionTitle(t)}</span>
                      <span className="caption la-muted">{transitionBy(t)}</span>
                      {t.note && <span className="caption">{t.note}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
      </LoadState>
    </main>
  );
}
