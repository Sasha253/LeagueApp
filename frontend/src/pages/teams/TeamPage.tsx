// A Team (design/src/ds/Screens.md, Captain 1 and 3): who is in it and, for its Captain,
// the Players asking to join with Accept and Decline. A Player who isn't its Captain can
// leave it. Players in the Team pay their share from here; the Captain also sees who has
// paid (pages/payments/TeamPayments.tsx).

import { useState } from "react";
import { useNavigate, useParams } from "react-router";
import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthProvider";
import { Banner } from "../../components/Banner";
import { StatusChip } from "../../components/StatusChip";
import { formatDate, localDate } from "../../format";
import { ConfirmButton, LoadState, send, useLoad } from "../club/shared";
import { TeamPayments } from "../payments/TeamPayments";
import { playersLine, POSITION_LABELS, ScreenHeader, TeamStatus, teamLine, type JoinRequest, type Team } from "./shared";

export function TeamPage() {
  const id = Number(useParams().teamId);
  const { state } = useAuth();
  const meId = state.status === "signedIn" ? state.me.id : null;
  const [team, retry] = useLoad(() => api.GET("/api/v1/teams/{id}/", { params: { path: { id } } }), `team-${id}`);
  const [members, reloadMembers] = useLoad(
    () => api.GET("/api/v1/teams/{id}/members/", { params: { path: { id } } }),
    `team-members-${id}`,
  );
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  async function leave() {
    const failed = await send(() => api.POST("/api/v1/teams/{id}/leave/", { params: { path: { id } } }));
    setError(failed?.general ?? null);
    if (!failed) navigate("/teams");
  }

  const changed = () => {
    retry();
    reloadMembers();
  };

  return (
    <main className="la-screen">
      <LoadState result={team} retry={retry} what="Team">
        {(data) => {
          const isCaptain = data.captain_id === meId;
          const isMember = members.state === "ok" && members.data.some((m) => m.player_id === meId);
          return (
            <>
              <ScreenHeader title={data.name} back={{ label: "Teams", to: "/teams" }} caption={teamLine(data)} />
              <div>
                <TeamStatus team={data} />
              </div>
              {data.status === "requested" && (
                <Banner status="pending" title="Waiting for the Admin">
                  {data.club.name} will confirm or decline this Team. Players can ask to join once it's confirmed.
                </Banner>
              )}
              {isCaptain && data.status === "active" && <JoinRequests team={data} onChange={changed} />}

              <section className="la-stack-2" aria-labelledby="squad">
                <h2 id="squad" className="la-overline">
                  Players · {playersLine(data.players)}
                </h2>
                {members.state === "ok" ? (
                  <ul className="la-group">
                    {members.data.map((member) => (
                      <li key={member.player_id} className="la-item">
                        <div className="la-item__body">
                          <span className="body-strong">
                            {member.name}
                            {member.player_id === meId ? " (you)" : ""}
                          </span>
                          <span className="caption la-muted">
                            {[member.position ? POSITION_LABELS[member.position] : null, `Joined ${formatDate(localDate(member.joined_at))}`]
                              .filter(Boolean)
                              .join(" · ")}
                          </span>
                        </div>
                        {member.is_captain && <StatusChip status="info">Captain</StatusChip>}
                      </li>
                    ))}
                  </ul>
                ) : members.state === "forbidden" ? (
                  <p className="caption la-muted">Only Players in this Team can see who is in it.</p>
                ) : members.state === "loading" ? (
                  <p className="caption la-muted" role="status">
                    Loading Players
                  </p>
                ) : (
                  <Banner status="cancelled" title="Couldn't load the Players">
                    <button type="button" className="la-btn la-btn--quiet" onClick={reloadMembers}>
                      Retry
                    </button>
                  </Banner>
                )}
              </section>

              {isMember && data.status === "active" && <TeamPayments teamId={data.id} isCaptain={isCaptain} />}

              {error && <Banner status="cancelled" title={error} />}
              {isMember && !isCaptain && (
                <div className="la-actions">
                  <ConfirmButton label="Leave team" confirmLabel={`Leave ${data.name}`} onConfirm={() => void leave()} />
                </div>
              )}
              {isCaptain && (
                <p className="caption la-muted">
                  You're the Captain. To hand over or leave, ask {data.club.name}'s Admin to assign a new Captain.
                </p>
              )}
            </>
          );
        }}
      </LoadState>
    </main>
  );
}

/** The Captain's queue of Players asking to join. */
function JoinRequests({ team, onChange }: { team: Team; onChange: () => void }) {
  const [requests, reload] = useLoad(
    () => api.GET("/api/v1/teams/{id}/join-requests/", { params: { path: { id: team.id } } }),
    `team-join-requests-${team.id}`,
  );
  const [error, setError] = useState<string | null>(null);
  // The request being answered: its buttons are off until the API answers, so a double tap
  // doesn't send it twice.
  const [busy, setBusy] = useState<number | null>(null);

  async function answer(request: JoinRequest, verb: "accept" | "decline") {
    const path = { params: { path: { id: request.id } } };
    setBusy(request.id);
    const failed = await send(() =>
      verb === "accept"
        ? api.POST("/api/v1/join-requests/{id}/accept/", path)
        : api.POST("/api/v1/join-requests/{id}/decline/", path),
    );
    setBusy(null);
    setError(failed?.general ?? null);
    reload();
    if (!failed && verb === "accept") onChange();
  }

  return (
    <section className="la-stack-2" aria-labelledby="join-requests">
      <h2 id="join-requests" className="la-overline">
        Asking to join
      </h2>
      <LoadState result={requests} retry={reload} what="requests to join" forbidden="Only the Captain sees requests to join.">
        {(list) =>
          list.length === 0 ? (
            <p className="body la-muted">No one is asking to join right now.</p>
          ) : (
            <ul className="la-group">
              {list.map((request) => (
                <li key={request.id} className="la-item">
                  <div className="la-item__body">
                    <span className="body-strong">{request.player_name}</span>
                    <span className="caption la-muted">
                      {[request.position ? POSITION_LABELS[request.position] : null, `Asked ${formatDate(localDate(request.created_at))}`]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </div>
                  <span className="la-confirm">
                    <button
                      type="button"
                      className="la-btn la-btn--secondary la-btn--sm"
                      aria-label={`Accept ${request.player_name}`}
                      disabled={busy === request.id}
                      onClick={() => void answer(request, "accept")}
                    >
                      Accept
                    </button>
                    <button
                      type="button"
                      className="la-btn la-btn--quiet la-btn--sm"
                      aria-label={`Decline ${request.player_name}`}
                      disabled={busy === request.id}
                      onClick={() => void answer(request, "decline")}
                    >
                      Decline
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          )
        }
      </LoadState>
      {error && <Banner status="cancelled" title={error} />}
    </section>
  );
}
