// Tonight for the club's Admin (design/src/screens/f11-tonight.mjs; Screens.md Admin 1 and 4):
// matches at risk on top, each Team's confirmed Players against the Division minimum and its
// paid state, and for a Team waiting at T-6h the Admin's ruling: let them play (for example
// cash at the gate) or rule them out (FR-5, FR-6). Which matches are at risk, who waits and
// what a ruling does are all the API's decisions; this screen only draws them.

import { useState } from "react";
import { api, type Schemas } from "../../api/client";
import { Banner } from "../../components/Banner";
import { StatusChip } from "../../components/StatusChip";
import { formatDate, formatRand, formatTime, localDate } from "../../format";
import { ConfirmButton, LoadState, send, useClub, useLoad } from "../club/shared";
import { ScreenHeader } from "../teams/shared";
import { FixtureStatusChip, matchName } from "./shared";
import { NOT_AN_ADMIN } from "./ClubFixturesPage";

type Tonight = Schemas["TonightFixture"];
type TonightTeam = Schemas["TonightTeam"];
type Decision = Schemas["ReadinessDecisionEnum"];

function today(): string {
  return formatDate(localDate(new Date().toISOString()));
}

/** "R 210 of R 350" while a Team owes money, else "Paid". */
function PaidChip({ team }: { team: TonightTeam }) {
  if (!team.unpaid) return <StatusChip status="confirmed">Paid</StatusChip>;
  return <StatusChip status="pending">Unpaid</StatusChip>;
}

/** What the T-6h check decided for the Team, when it has run. */
function ReadinessChip({ team }: { team: TonightTeam }) {
  const r = team.readiness;
  if (!r) return team.below_minimum ? <StatusChip status="pending">{`Short ${team.min_players - team.confirmed}`}</StatusChip> : null;
  if (r.outcome === "out") return <StatusChip status="cancelled">Out</StatusChip>;
  if (r.outcome === "pending") return <StatusChip status="pending">Your call</StatusChip>;
  return null;
}

function TeamLine({ team }: { team: TonightTeam }) {
  const money = team.unpaid ? ` · ${formatRand(team.paid)} of ${formatRand(team.due)}` : "";
  return (
    <div className="la-team-line">
      <span className="la-team-line__name">{team.team.name}</span>
      <span className="la-team-line__count">
        {team.confirmed} of {team.min_players}
        {money}
      </span>
      <ReadinessChip team={team} />
      <PaidChip team={team} />
    </div>
  );
}

/** Why the match is at risk, in the Admin's words. */
function riskCopy(match: Tonight): string {
  const lines: string[] = [];
  for (const t of match.teams) {
    const r = t.readiness;
    const name = t.team.name;
    if (r?.outcome === "pending" && r.reason === "unpaid") {
      lines.push(`${name} still owes ${formatRand(r.outstanding)} at the T-6h check. You decide if they play.`);
    } else if (r?.outcome === "pending" && r.reason === "no_replies") {
      lines.push(`No Confirmations went out for this match, so no one could reply. You decide if ${name} plays.`);
    } else if (r?.outcome === "out" && r.reason === "short") {
      lines.push(`${name} had ${r.confirmed} of ${r.min_players} confirmed at T-6h, so they're out.`);
    } else if (r?.outcome === "out") {
      lines.push(`${name} was ruled out.`);
    } else if (!r && t.below_minimum) {
      lines.push(`${name} needs ${t.min_players - t.confirmed} more by T-6h or they're out.`);
    } else if (!r && t.unpaid) {
      lines.push(`${name} still owes ${formatRand(t.outstanding)}. Unpaid at T-6h, you decide if they play.`);
    }
  }
  return lines.join(" ");
}

function AtRiskCard({ match, onDecide }: { match: Tonight; onDecide: (id: number, d: Decision) => void }) {
  const { fixture } = match;
  const waiting = match.teams.filter((t) => t.readiness?.outcome === "pending");
  return (
    <article className="la-card la-stack-2" aria-label={matchName(fixture)}>
      <div className="la-row">
        <p className="la-overline">
          {fixture.division.name} · {fixture.pitch.name}
        </p>
        <StatusChip status="pending">At risk</StatusChip>
      </div>
      <div className="la-row">
        <p className="la-fixture">
          {fixture.home_team.name} <span className="la-vs">vs</span> {fixture.away_team.name}
        </p>
        <span className="la-time">{formatTime(fixture.kick_off)}</span>
      </div>
      <hr className="la-divider" />
      {match.teams.map((t) => (
        <TeamLine key={t.team.id} team={t} />
      ))}
      <p className="body">{riskCopy(match)}</p>
      {waiting.map((t) => (
        <div key={t.team.id} className="la-actions" aria-label={`Ruling for ${t.team.name}`} role="group">
          <button
            type="button"
            className="la-btn la-btn--secondary la-btn--sm"
            onClick={() => onDecide(t.readiness!.id, "play")}
          >
            {`Let ${t.team.name} play`}
          </button>
          <ConfirmButton
            label={`Rule ${t.team.name} out`}
            confirmLabel="Rule out"
            onConfirm={() => onDecide(t.readiness!.id, "out")}
          />
        </div>
      ))}
    </article>
  );
}

function paidSummary(match: Tonight): string {
  const unpaid = match.teams.filter((t) => t.unpaid).length;
  if (unpaid === 0) return "both paid";
  return unpaid === 2 ? "both unpaid" : "one unpaid";
}

export function TonightPage() {
  const { clubId, clubName } = useClub();
  const [tonight, reload] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/tonight/", { params: { path: { club_id: clubId } } }),
    `tonight-${clubId}`,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function decide(id: number, decision: Decision) {
    if (busy) return;
    setBusy(true);
    const failed = await send(() =>
      api.POST("/api/v1/clubs/{club_id}/readiness/{id}/decide/", {
        params: { path: { club_id: clubId, id } },
        body: { decision },
      }),
    );
    setBusy(false);
    setError(failed ? (failed.general ?? Object.values(failed.fields)[0] ?? "That didn't work.") : null);
    reload();
  }

  return (
    <main className="la-screen">
      <ScreenHeader title="Tonight" back={{ label: "Club home", to: `/clubs/${clubId}` }} caption={`${today()} · ${clubName}`} />
      {error && <Banner status="cancelled" title={error} />}
      <LoadState result={tonight} retry={reload} what="tonight's matches" forbidden={NOT_AN_ADMIN}>
        {(matches) => {
          if (matches.length === 0) return <p className="body la-muted">No matches tonight.</p>;
          const atRisk = matches.filter((m) => m.at_risk);
          const others = matches.filter((m) => !m.at_risk);
          return (
            <>
              {atRisk.length > 0 && (
                <section className="la-stack-2" aria-labelledby="at-risk">
                  <h2 id="at-risk" className="la-overline">
                    At risk · {atRisk.length}
                  </h2>
                  {atRisk.map((m) => (
                    <AtRiskCard key={m.fixture.id} match={m} onDecide={(id, d) => void decide(id, d)} />
                  ))}
                </section>
              )}
              {others.length > 0 && (
                <section className="la-stack-2" aria-labelledby="by-pitch">
                  <h2 id="by-pitch" className="la-overline">
                    By pitch and time
                  </h2>
                  <ul className="la-group" aria-label="By pitch and time">
                    {others.map((m) => (
                      <li key={m.fixture.id} className="la-item">
                        <span className="la-item__time">{formatTime(m.fixture.kick_off)}</span>
                        <span className="la-item__body">
                          <span className="body-strong">{matchName(m.fixture)}</span>
                          <span className="caption la-muted">
                            {m.fixture.pitch.name} · {m.fixture.division.name} · {paidSummary(m)}
                          </span>
                        </span>
                        <FixtureStatusChip status={m.fixture.status} />
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          );
        }}
      </LoadState>
    </main>
  );
}
