// A Team as its Club's Admin sees it: who asked for it and who decided, its Players, and
// assigning its Captain (PRD roles table, Admin row).

import { useState } from "react";
import { useParams } from "react-router";
import { api } from "../../api/client";
import { Banner } from "../../components/Banner";
import { StatusChip } from "../../components/StatusChip";
import { formatDate, localDate } from "../../format";
import { ConfirmButton, LoadState, send, useClub, useLoad } from "../club/shared";
import { NOT_AN_ADMIN } from "./ClubTeamsPage";
import { playersLine, POSITION_LABELS, ScreenHeader, TeamStatus, teamLine } from "./shared";

export function ClubTeamPage() {
  const { clubId } = useClub();
  const id = Number(useParams().teamId);
  const path = { params: { path: { club_id: clubId, id } } };
  const [team, reload] = useLoad(() => api.GET("/api/v1/clubs/{club_id}/teams/{id}/", path), `club-team-${clubId}-${id}`);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  async function makeCaptain(player: number, name: string) {
    setDone(null);
    const failed = await send(() =>
      api.POST("/api/v1/clubs/{club_id}/teams/{id}/captain/", { ...path, body: { player } }),
    );
    setError(failed?.general ?? failed?.fields.player ?? null);
    if (!failed) {
      setDone(`${name} is the Captain now.`);
      reload();
    }
  }

  return (
    <main className="la-screen">
      <LoadState result={team} retry={reload} what="Team" forbidden={NOT_AN_ADMIN}>
        {(data) => (
          <>
            <ScreenHeader
              title={data.name}
              back={{ label: "Team requests", to: `/clubs/${clubId}/teams` }}
              caption={teamLine(data)}
            />
            <div>
              <TeamStatus team={data} />
            </div>
            <p className="caption la-muted">
              Asked by {data.requested_by_name ?? "a Player"} on {formatDate(localDate(data.requested_at))}
              {data.decided_at &&
                ` · ${data.status === "declined" ? "Declined" : "Confirmed"} by ${data.decided_by_name ?? "an Admin"} on ${formatDate(localDate(data.decided_at))}`}
            </p>
            {data.status === "declined" && data.decline_reason && (
              <Banner status="cancelled" title="Declined">
                {data.decline_reason}
              </Banner>
            )}
            {done && <Banner status="confirmed" title={done} />}
            {error && <Banner status="cancelled" title={error} />}
            <section className="la-stack-2" aria-labelledby="players">
              <h2 id="players" className="la-overline">
                Players · {playersLine(data.players)}
              </h2>
              {data.members.length === 0 ? (
                <p className="body la-muted">No Players in this Team.</p>
              ) : (
                <ul className="la-group">
                  {data.members.map((member) => (
                    <li key={member.player_id} className="la-item">
                      <div className="la-item__body">
                        <span className="body-strong">{member.name}</span>
                        <span className="caption la-muted">
                          {[member.position ? POSITION_LABELS[member.position] : null, `Joined ${formatDate(localDate(member.joined_at))}`]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                      </div>
                      {member.is_captain ? (
                        <StatusChip status="info">Captain</StatusChip>
                      ) : (
                        data.status !== "declined" && (
                          <ConfirmButton
                            label="Make Captain"
                            confirmLabel={`Make ${member.name} Captain`}
                            onConfirm={() => void makeCaptain(member.player_id, member.name)}
                          />
                        )
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </LoadState>
    </main>
  );
}
