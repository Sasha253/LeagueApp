// A Fixture (design/src/ds/Screens.md, Player 2 "Match detail"), for a Player in one of its
// Teams: kick-off, the teams, pitch and status; then your Team's SquadProgress, your reply
// (changeable until T-6h, FR-3) and the squad's replies (FR-38). Pay my share comes with
// the payment chunks. The Team's requests to cancel or postpone (FR-18): its Captain can
// send one, and withdraw it while it waits for the Admin.

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { api } from "../../api/client";
import { Banner } from "../../components/Banner";
import { LoadState, send, useLoad } from "../club/shared";
import { ScreenHeader } from "../teams/shared";
import { FIXTURE_STATUS, MatchCard } from "./shared";
import { NOT_A_PLAYER } from "./MyFixturesPage";
import { SquadProgress, SquadReplies, YourReply, type Squad } from "./squad";
import { RequestStatus, requestDetail, requestTitle } from "./requests";

export function FixturePage() {
  const id = Number(useParams().fixtureId);
  const [fixture, reload] = useLoad(
    () => api.GET("/api/v1/fixtures/{id}/", { params: { path: { id } } }),
    `fixture-${id}`,
  );

  return (
    <main className="la-screen">
      <ScreenHeader title="Match" back={{ label: "My fixtures", to: "/fixtures" }} />
      <LoadState result={fixture} retry={reload} what="match" forbidden={NOT_A_PLAYER}>
        {(match) => {
          const mine = [match.home_team, match.away_team].find((team) => team.id === match.my_team_id);
          const opponent = mine && (mine.id === match.home_team.id ? match.away_team : match.home_team);
          return (
            <>
              <MatchCard fixture={match} />
              <ul className="la-group">
                {mine && opponent && (
                  <li className="la-item">
                    <span className="la-item__body">
                      <span className="caption la-muted">Your team</span>
                      <span className="body-strong">
                        {mine.name}, against {opponent.name}
                      </span>
                    </span>
                  </li>
                )}
                <li className="la-item">
                  <span className="la-item__body">
                    <span className="caption la-muted">Pitch</span>
                    <span className="body-strong">{match.pitch.name}</span>
                  </span>
                </li>
                <li className="la-item">
                  <span className="la-item__body">
                    <span className="caption la-muted">League</span>
                    <span className="body-strong">
                      {match.division.name} · {match.season.name} · {match.club.name}
                    </span>
                  </span>
                </li>
                <li className="la-item">
                  <span className="la-item__body">
                    <span className="caption la-muted">Status</span>
                    <span className="body-strong">{FIXTURE_STATUS[match.status].label}</span>
                  </span>
                </li>
              </ul>
              {match.friendly_eligible && (
                <p className="caption la-muted">If this match can't go ahead, it may be played as a friendly.</p>
              )}
              <MatchSquad fixtureId={match.id} notOpenYet={match.status === "scheduled"} />
              <MatchRequests fixtureId={match.id} />
            </>
          );
        }}
      </LoadState>
    </main>
  );
}

/** Your Team's replies for the match, and your own. */
function MatchSquad({ fixtureId, notOpenYet }: { fixtureId: number; notOpenYet: boolean }) {
  const [loaded, reload] = useLoad(
    () => api.GET("/api/v1/fixtures/{id}/squad/", { params: { path: { id: fixtureId } } }),
    `squad-${fixtureId}`,
  );
  const [squad, setSquad] = useState<Squad | null>(null);
  useEffect(() => {
    if (loaded.state === "ok") setSquad(loaded.data);
  }, [loaded]);

  return (
    <LoadState result={loaded} retry={reload} what="squad" forbidden={NOT_A_PLAYER}>
      {(first) => {
        const current = squad ?? first;
        return (
          <>
            <SquadProgress squad={current} />
            <YourReply fixtureId={fixtureId} squad={current} notOpenYet={notOpenYet} onAnswered={setSquad} />
            <h2 className="la-overline">Squad replies</h2>
            <SquadReplies squad={current} />
          </>
        );
      }}
    </LoadState>
  );
}

/** The Team's requests to cancel or postpone the match; its Captain sends and withdraws. */
function MatchRequests({ fixtureId }: { fixtureId: number }) {
  const [loaded, reload] = useLoad(
    () => api.GET("/api/v1/fixtures/{id}/requests/", { params: { path: { id: fixtureId } } }),
    `match-requests-${fixtureId}`,
  );
  const [error, setError] = useState<string | null>(null);

  async function withdraw(id: number) {
    const failed = await send(() =>
      api.POST("/api/v1/captain-requests/{id}/withdraw/", { params: { path: { id } } }),
    );
    setError(failed?.general ?? null);
    if (!failed) reload();
  }

  if (loaded.state !== "ok") return null;
  const { is_captain, can_request, requests } = loaded.data;
  if (!is_captain && requests.length === 0) return null;
  return (
    <section className="la-stack-2" aria-labelledby="match-requests">
      <h2 id="match-requests" className="la-overline">
        Cancel or postpone
      </h2>
      {requests.length > 0 && (
        <ul className="la-group" aria-label="Requests">
          {requests.map((r) => (
            <li key={r.id} className="la-item">
              <span className="la-item__body">
                <span className="body-strong">{requestTitle(r)}</span>
                <span className="caption">{r.reason}</span>
                <span className="caption la-muted">{requestDetail(r)}</span>
                {is_captain && r.status === "pending" && (
                  <button type="button" className="la-btn la-btn--quiet la-btn--sm" onClick={() => void withdraw(r.id)}>
                    Withdraw
                  </button>
                )}
              </span>
              <RequestStatus request={r} />
            </li>
          ))}
        </ul>
      )}
      {can_request && (
        <Link className="la-btn la-btn--secondary" to={`/fixtures/${fixtureId}/request`}>
          Ask the Admin to cancel or postpone
        </Link>
      )}
      {error && <Banner status="cancelled" title={error} />}
    </section>
  );
}
