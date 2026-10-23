// Player and Goalkeeper Requests (FR-35 to FR-37): how they are labelled, and the Team's
// requests on the Match screen. Who is asked, who joins and when a request closes are all
// decided by the backend; this file only draws them.

import { useState } from "react";
import { Link } from "react-router";
import { api, type Schemas } from "../../api/client";
import { Banner } from "../../components/Banner";
import { StatusChip, type Status } from "../../components/StatusChip";
import { formatMoment } from "../../format";
import { send, useLoad } from "../club/shared";

export type PlayerRequest = Schemas["PlayerRequest"];
export type PlayerRequestKind = Schemas["PlayerRequestKindEnum"];

/** "a player" / "2 goalkeepers" */
export function wanted(kind: PlayerRequestKind, places: number): string {
  const word = kind === "player" ? "player" : "goalkeeper";
  return places === 1 ? `a ${word}` : `${places} ${word}s`;
}

export const KIND_PLURAL: Record<PlayerRequestKind, string> = {
  player: "outfield Players",
  goalkeeper: "Goalkeepers",
};

const STATUS: Record<PlayerRequest["status"], { status: Status; label: string }> = {
  open: { status: "pending", label: "Open" },
  filled: { status: "confirmed", label: "Filled" },
  withdrawn: { status: "info", label: "Withdrawn" },
  closed: { status: "info", label: "No longer applies" },
};

export function PlayerRequestStatus({ status }: { status: PlayerRequest["status"] }) {
  return <StatusChip status={STATUS[status].status}>{STATUS[status].label}</StatusChip>;
}

/** "1 of 2 joined: Lerato · Sent to 3 Players · Mon 26 Oct · 10:00 by Thandi" */
function detail(r: PlayerRequest): string {
  const names = r.joined.map((p) => p.name).join(", ");
  const parts = [`${r.filled} of ${r.places} joined${names ? `: ${names}` : ""}`];
  parts.push(`Sent to ${r.notified} ${r.notified === 1 ? "Player" : "Players"}`);
  parts.push(`${formatMoment(r.raised_at)} by ${r.raised_by_name}`);
  return parts.join(" · ");
}

/** The Team's requests for borrowed Players; its Captain raises and withdraws them. */
export function MatchPlayerRequests({ fixtureId }: { fixtureId: number }) {
  const [loaded, reload] = useLoad(
    () => api.GET("/api/v1/fixtures/{id}/player-requests/", { params: { path: { id: fixtureId } } }),
    `player-requests-${fixtureId}`,
  );
  const [error, setError] = useState<string | null>(null);

  async function withdraw(id: number) {
    const failed = await send(() =>
      api.POST("/api/v1/player-requests/{id}/withdraw/", { params: { path: { id } } }),
    );
    setError(failed?.general ?? null);
    if (!failed) reload();
  }

  if (loaded.state !== "ok") return null;
  const { is_captain, can_request, requests } = loaded.data;
  if (!is_captain && requests.length === 0) return null;
  return (
    <section className="la-stack-2" aria-labelledby="player-requests">
      <h2 id="player-requests" className="la-overline">
        Players from other teams
      </h2>
      {requests.length > 0 && (
        <ul className="la-group" aria-label="Player requests">
          {requests.map((r) => (
            <li key={r.id} className="la-item">
              <span className="la-item__body">
                <span className="body-strong">
                  {r.team.name} needs {wanted(r.kind, r.places)}
                </span>
                <span className="caption la-muted">{detail(r)}</span>
                {is_captain && r.status === "open" && (
                  <button type="button" className="la-btn la-btn--quiet la-btn--sm" onClick={() => void withdraw(r.id)}>
                    Withdraw
                  </button>
                )}
              </span>
              <PlayerRequestStatus status={r.status} />
            </li>
          ))}
        </ul>
      )}
      {can_request && (
        <Link className="la-btn la-btn--secondary" to={`/fixtures/${fixtureId}/players`}>
          Request a player
        </Link>
      )}
      {error && <Banner status="cancelled" title={error} />}
    </section>
  );
}
