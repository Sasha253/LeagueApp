// A Fixture for the club's Admin (design/src/ds/Screens.md, Admin 2): kick-off, teams, pitch
// and Referee, whether it may become a friendly, and every change of its status with who or
// what made it. Whether the flag can still change is the API's decision (409 otherwise).
// When one Team was out, the search for a new opponent (FR-13 to FR-16): who the slot was
// offered to, until when, and who took it. Once the match couldn't go ahead (FR-10 to FR-12,
// FR-17, FR-43): the friendly and who joined it, or the cancellation and the credit returned.
// The backend decides both; this only shows them. A friendly's fee, who pays it and its
// Captain (FR-24) are in FriendlyFees.tsx. The Admin can reschedule the match
// (FR-7 to FR-9) and answer its Captains' requests to cancel or postpone it (FR-18).

import { useState } from "react";
import { useParams } from "react-router";
import { api, type Schemas } from "../../api/client";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { StatusChip, type Status } from "../../components/StatusChip";
import { formatMoment, formatRand } from "../../format";
import { LoadState, send, useClub, useLoad } from "../club/shared";
import { POSITION_LABELS, ScreenHeader } from "../teams/shared";
import { FIXTURE_STATUS, MatchCard } from "./shared";
import { NOT_AN_ADMIN } from "./ClubFixturesPage";
import { FriendlyFeeSection } from "./FriendlyFees";
import { CaptainRequestsSection, moveOf, RescheduleSection, type Move } from "./reschedule";

type Transition = Schemas["FixtureTransition"];
type Replacement = Schemas["ReplacementOffer"];
type Fallback = Schemas["FixtureFallback"];
type Detail = Schemas["AdminFixtureDetail"];

// A match still on its way to being played can be moved; the backend refuses anything else.
const MOVABLE: Detail["status"][] = ["scheduled", "confirming", "ready"];

function rescheduleLine(r: Detail["reschedules"][number]): string {
  const pitch = r.from_pitch.id !== r.to_pitch.id ? `, ${r.from_pitch.name} to ${r.to_pitch.name}` : "";
  return `${formatMoment(r.from_kick_off)} to ${formatMoment(r.to_kick_off)}${pitch}`;
}

function rescheduleBy(r: Detail["reschedules"][number]): string {
  const parts = [`${formatMoment(r.at)}${r.by_name ? ` · ${r.by_name}` : ""}`, `${r.notified} told`];
  if (r.confirmations_sent) parts.push("Confirmations sent at once");
  return parts.join(" · ");
}

/** Reschedule and Captain requests: the picked time is shared, so a postponement can use it. */
function MatchChanges({ clubId, fixture, onDone }: { clubId: number; fixture: Detail; onDone: () => void }) {
  const [move, setMove] = useState<Move>(() => moveOf(fixture));
  return (
    <>
      <CaptainRequestsSection clubId={clubId} requests={fixture.captain_requests} move={move} onDone={onDone} />
      {MOVABLE.includes(fixture.status) && (
        <RescheduleSection clubId={clubId} fixture={fixture} move={move} onMove={setMove} onDone={onDone} />
      )}
      {fixture.reschedules.length > 0 && (
        <ul className="la-group" aria-label="Reschedules">
          {fixture.reschedules.map((r) => (
            <li key={r.id} className="la-item">
              <span className="la-item__body">
                <span className="body-strong">Moved {rescheduleLine(r)}</span>
                <span className="caption la-muted">{rescheduleBy(r)}</span>
                {r.note && <span className="caption">{r.note}</span>}
              </span>
              <StatusChip status="info">Rescheduled</StatusChip>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

const FALLBACK_OUTCOME: Record<Fallback["outcome"], { status: Status; label: string }> = {
  friendly: { status: "info", label: "Friendly" },
  cancelled: { status: "cancelled", label: "Cancelled" },
};

function fallbackWhy(f: Fallback): string {
  if (f.cause === "both_teams_out") return "Both Teams were out.";
  return f.remaining_team ? `No new opponent for ${f.remaining_team.name}.` : "No new opponent was found.";
}

function fallbackDetail(f: Fallback): string {
  if (f.outcome === "friendly") {
    const invited = f.invited === 1 ? "1 Player" : `${f.invited} Players`;
    return `Open to join until kick-off: ${f.joined.length} of ${invited} invited joined.`;
  }
  if (f.credits === 0) return "Nothing was paid for this match, so no credit was returned.";
  const entries = f.credits === 1 ? "1 payment" : `${f.credits} payments`;
  return `${formatRand(f.credit_returned)} returned as credit to whoever paid (${entries}).`;
}

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

            <MatchChanges
              key={`${match.kick_off}-${match.pitch.id}`}
              clubId={clubId}
              fixture={match}
              onDone={reload}
            />

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

            {match.fallback && (
              <section className="la-stack-2" aria-labelledby="fallback">
                <h2 id="fallback" className="la-overline">
                  {FALLBACK_OUTCOME[match.fallback.outcome].label}
                </h2>
                <ul className="la-group" aria-label="Outcome">
                  <li className="la-item">
                    <span className="la-item__body">
                      <span className="body-strong">{fallbackWhy(match.fallback)}</span>
                      <span className="caption la-muted">{fallbackDetail(match.fallback)}</span>
                      <span className="caption la-muted">Decided {formatMoment(match.fallback.decided_at)}</span>
                    </span>
                    <StatusChip status={FALLBACK_OUTCOME[match.fallback.outcome].status}>
                      {FALLBACK_OUTCOME[match.fallback.outcome].label}
                    </StatusChip>
                  </li>
                </ul>
                {match.fallback.joined.length > 0 && (
                  <ul className="la-group" aria-label="Joined">
                    {match.fallback.joined.map((p) => (
                      <li key={p.id} className="la-item">
                        <span className="la-item__body">
                          <span className="body-strong">{p.name}</span>
                          <span className="caption la-muted">
                            {[POSITION_LABELS[p.position], `joined ${formatMoment(p.joined_at)}`]
                              .filter(Boolean)
                              .join(" · ")}
                          </span>
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            )}

            {match.fallback?.outcome === "friendly" && <FriendlyFeeSection clubId={clubId} fixtureId={match.id} />}

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
