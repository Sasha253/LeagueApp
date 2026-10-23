// Teams (design/src/ds/Screens.md, Player tab "Teams"): the Teams you're in and were in,
// your requests to join, and the ways to find or start a Team.

import { useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import { Banner } from "../../components/Banner";
import { StatusChip } from "../../components/StatusChip";
import { LoadState, send, useLoad } from "../club/shared";
import { JoinStatus, playersLine, ScreenHeader, TeamStatus, teamLine, type JoinRequest } from "./shared";

export const NOT_A_PLAYER = 'Teams are for Players. Turn on "I play" in your Profile.';

export function MyTeamsPage() {
  const [teams, reloadTeams] = useLoad(() => api.GET("/api/v1/me/teams/"), "my-teams");
  const [requests, reloadRequests] = useLoad(() => api.GET("/api/v1/me/join-requests/"), "my-join-requests");
  const [error, setError] = useState<string | null>(null);
  const [withdrawing, setWithdrawing] = useState<number | null>(null);

  async function withdraw(request: JoinRequest) {
    setWithdrawing(request.id);
    const failed = await send(() =>
      api.POST("/api/v1/join-requests/{id}/withdraw/", { params: { path: { id: request.id } } }),
    );
    setWithdrawing(null);
    setError(failed?.general ?? null);
    if (!failed) reloadRequests();
  }

  return (
    <main className="la-screen">
      <ScreenHeader title="Teams" back={{ label: "Profile", to: "/profile" }} />
      <LoadState result={teams} retry={reloadTeams} what="your Teams" forbidden={NOT_A_PLAYER}>
        {(memberships) => {
          const current = memberships.filter((m) => !m.left_at);
          const past = memberships.filter((m) => m.left_at);
          return (
            <>
              <section className="la-stack-2" aria-labelledby="my-teams">
                <h2 id="my-teams" className="la-overline">
                  Your Teams
                </h2>
                {current.length === 0 ? (
                  <p className="body la-muted">You're not in a Team yet. Find one to join, or start your own.</p>
                ) : (
                  <ul className="la-group">
                    {current.map(({ id, team, is_captain }) => (
                      <li key={id}>
                        <Link className="la-item la-item--link" to={`/teams/${team.id}`}>
                          <span className="la-item__body">
                            <span className="body-strong">{team.name}</span>
                            <span className="caption la-muted">{teamLine(team)}</span>
                            <span className="caption la-muted">
                              {is_captain ? "You're the Captain" : `Captain: ${team.captain_name ?? "none yet"}`}
                              {" · "}
                              {playersLine(team.players)}
                            </span>
                          </span>
                          {team.status !== "active" && <TeamStatus team={team} />}
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="la-actions">
                  <Link className="la-btn la-btn--primary" to="/teams/find">
                    Find a team
                  </Link>
                  <Link className="la-btn la-btn--secondary" to="/teams/new">
                    Request a Team
                  </Link>
                </div>
              </section>

              <LoadState result={requests} retry={reloadRequests} what="your requests to join" forbidden={NOT_A_PLAYER}>
                {(list) => {
                  // Accepted ones are in "Your Teams"; withdrawn ones are gone.
                  const open = list.filter((r) => r.status === "pending" || r.status === "declined");
                  if (open.length === 0) return null;
                  return (
                    <section className="la-stack-2" aria-labelledby="my-requests">
                      <h2 id="my-requests" className="la-overline">
                        Requests to join
                      </h2>
                      <ul className="la-group">
                        {open.map((request) => (
                          <li key={request.id} className="la-item">
                            <div className="la-item__body">
                              <span className="body-strong">{request.team.name}</span>
                              <span className="caption la-muted">{teamLine(request.team)}</span>
                              <span>
                                <JoinStatus request={request} />
                              </span>
                            </div>
                            {request.status === "pending" && (
                              <button
                                type="button"
                                className="la-btn la-btn--quiet la-btn--sm"
                                aria-label={`Withdraw request to join ${request.team.name}`}
                                disabled={withdrawing === request.id}
                                onClick={() => void withdraw(request)}
                              >
                                Withdraw
                              </button>
                            )}
                          </li>
                        ))}
                      </ul>
                    </section>
                  );
                }}
              </LoadState>
              {error && <Banner status="cancelled" title={error} />}

              {past.length > 0 && (
                <section className="la-stack-2" aria-labelledby="past-teams">
                  <h2 id="past-teams" className="la-overline">
                    Before
                  </h2>
                  <ul className="la-group">
                    {past.map(({ id, team }) => (
                      <li key={id} className="la-item">
                        <div className="la-item__body">
                          <span className="body-strong">{team.name}</span>
                          <span className="caption la-muted">{teamLine(team)}</span>
                        </div>
                        <StatusChip status="info">Left</StatusChip>
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
