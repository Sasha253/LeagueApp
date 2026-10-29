// Team requests (design/src/ds/Screens.md, Admin 3, "Team creation" tab): the Club's
// Team requests to confirm or decline, then its confirmed Teams.

import { useState } from "react";
import { Link } from "react-router";
import { api, type Schemas } from "../../api/client";
import { Banner } from "../../components/Banner";
import { TextField } from "../../components/TextField";
import { formatDate, localDate } from "../../format";
import { LoadState, send, useClub, useLoad } from "../club/shared";
import { playersLine, ScreenHeader, teamLine } from "./shared";

type AdminTeam = Schemas["AdminTeam"];

export const NOT_AN_ADMIN = "Only this club's Admins can see its Teams.";

export function ClubTeamsPage() {
  const { clubId, clubName } = useClub();
  const listOf = (status: "requested" | "active") =>
    api.GET("/api/v1/clubs/{club_id}/teams/", { params: { path: { club_id: clubId }, query: { status } } });
  const [requested, reloadRequested] = useLoad(() => listOf("requested"), `club-teams-requested-${clubId}`);
  const [active, reloadActive] = useLoad(() => listOf("active"), `club-teams-active-${clubId}`);

  const answered = () => {
    reloadRequested();
    reloadActive();
  };

  return (
    <main className="la-screen">
      <ScreenHeader title="Team requests" back={{ label: "Club home", to: `/clubs/${clubId}` }} caption={clubName} />
      <LoadState result={requested} retry={reloadRequested} what="Team requests" forbidden={NOT_AN_ADMIN}>
        {(list) =>
          list.length === 0 ? (
            <p className="body la-muted">No Team requests waiting.</p>
          ) : (
            <ul className="la-group" aria-label="Waiting for you">
              {list.map((team) => (
                <li key={team.id} className="la-item">
                  <TeamRequest clubId={clubId} team={team} onAnswered={answered} />
                </li>
              ))}
            </ul>
          )
        }
      </LoadState>

      <section className="la-stack-2" aria-labelledby="club-teams">
        <h2 id="club-teams" className="la-overline">
          Teams
        </h2>
        <LoadState result={active} retry={reloadActive} what="Teams" forbidden={NOT_AN_ADMIN}>
          {(list) =>
            list.length === 0 ? (
              <p className="body la-muted">No confirmed Teams yet.</p>
            ) : (
              <ul className="la-group">
                {list.map((team) => (
                  <li key={team.id}>
                    <Link className="la-item la-item--link" to={`/clubs/${clubId}/teams/${team.id}`}>
                      <span className="la-item__body">
                        <span className="body-strong">{team.name}</span>
                        <span className="caption la-muted">{teamLine(team)}</span>
                        <span className="caption la-muted">
                          Captain: {team.captain_name ?? "none"} · {playersLine(team.players)}
                        </span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )
          }
        </LoadState>
      </section>
    </main>
  );
}

/** One request: Confirm, or Decline with an optional reason. */
function TeamRequest({ clubId, team, onAnswered }: { clubId: number; team: AdminTeam; onAnswered: () => void }) {
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const path = { params: { path: { club_id: clubId, id: team.id } } };

  async function act(call: () => Promise<{ error?: unknown; response: Response }>) {
    setBusy(true);
    const failed = await send(call);
    setBusy(false);
    setError(failed?.general ?? failed?.fields.reason ?? null);
    if (!failed) onAnswered();
  }

  return (
    <div className="la-item__body la-stack-2">
      <span className="body-strong">{team.name}</span>
      <span className="caption la-muted">{teamLine(team)}</span>
      <span className="caption la-muted">
        Asked by {team.requested_by_name ?? team.captain_name ?? "a Player"} on{" "}
        {formatDate(localDate(team.requested_at))}
      </span>
      {error && <Banner status="cancelled" title={error} />}
      {declining ? (
        <form
          className="la-stack-2"
          aria-label={`Decline ${team.name}`}
          onSubmit={(event) => {
            event.preventDefault();
            void act(() => api.POST("/api/v1/clubs/{club_id}/teams/{id}/decline/", { ...path, body: { reason } }));
          }}
        >
          <TextField
            label="Reason (optional)"
            help="Kept with the request for the club's Admins."
            value={reason}
            maxLength={300}
            onChange={(event) => setReason(event.target.value)}
          />
          <div className="la-actions">
            <button type="submit" className="la-btn la-btn--danger la-btn--sm" disabled={busy}>
              Decline {team.name}
            </button>
            <button type="button" className="la-btn la-btn--quiet la-btn--sm" onClick={() => setDeclining(false)}>
              Keep
            </button>
          </div>
        </form>
      ) : (
        <div className="la-actions">
          <button
            type="button"
            className="la-btn la-btn--secondary la-btn--sm"
            aria-label={`Confirm ${team.name}`}
            disabled={busy}
            onClick={() => void act(() => api.POST("/api/v1/clubs/{club_id}/teams/{id}/confirm/", path))}
          >
            Confirm
          </button>
          <button
            type="button"
            className="la-btn la-btn--quiet la-btn--sm"
            aria-label={`Decline ${team.name}`}
            onClick={() => setDeclining(true)}
          >
            Decline
          </button>
        </div>
      )}
    </div>
  );
}
