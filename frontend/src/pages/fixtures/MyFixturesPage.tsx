// My fixtures (design/src/ds/Screens.md, Player 1 "Matches"): the upcoming and past Fixtures
// of the Teams you're in now, for Players and Captains, and "Games you can join": the
// Player and Goalkeeper Requests you were sent (FR-36, FR-37). Replies, squads and
// payments come with later chunks.

import { useState } from "react";
import { Link } from "react-router";
import { api, type Schemas } from "../../api/client";
import { Banner } from "../../components/Banner";
import { StatusChip } from "../../components/StatusChip";
import { LoadState, send, useLoad } from "../club/shared";
import { deadline } from "../inbox/shared";
import { wanted } from "./playerRequests";
import { ScreenHeader } from "../teams/shared";
import { FixtureStatusChip, kickOffDate, MatchCard, matchName } from "./shared";
import { formatTime } from "../../format";

export const NOT_A_PLAYER = 'Fixtures are for Players. Turn on "I play" in your Profile.';

export function MyFixturesPage() {
  const [upcoming, reloadUpcoming] = useLoad(() => api.GET("/api/v1/me/fixtures/"), "my-fixtures");
  const [past, reloadPast] = useLoad(
    () => api.GET("/api/v1/me/fixtures/", { params: { query: { when: "past" } } }),
    "my-past-fixtures",
  );

  return (
    <main className="la-screen">
      <ScreenHeader title="My fixtures" back={{ label: "Profile", to: "/profile" }} />
      <LoadState result={upcoming} retry={reloadUpcoming} what="your fixtures" forbidden={NOT_A_PLAYER}>
        {(fixtures) => (
          <section className="la-stack-2" aria-labelledby="upcoming">
            <h2 id="upcoming" className="la-overline">
              Coming up
            </h2>
            {fixtures.length === 0 ? (
              <>
                <p className="body la-muted">No fixtures for your Teams yet. Your club's Admin adds them.</p>
                <Link className="la-btn la-btn--secondary" to="/teams">
                  Your Teams
                </Link>
              </>
            ) : (
              fixtures.map((fixture) => (
                <Link key={fixture.id} to={`/fixtures/${fixture.id}`} className="la-card-link">
                  <MatchCard fixture={fixture} />
                </Link>
              ))
            )}
          </section>
        )}
      </LoadState>
      <GamesToJoin />
      <LoadState result={past} retry={reloadPast} what="your past fixtures" forbidden={NOT_A_PLAYER}>
        {(fixtures) =>
          fixtures.length > 0 && (
            <section className="la-stack-2" aria-labelledby="past">
              <h2 id="past" className="la-overline">
                Before
              </h2>
              <ul className="la-group">
                {fixtures.map((fixture) => (
                  <li key={fixture.id}>
                    <Link className="la-item la-item--link" to={`/fixtures/${fixture.id}`}>
                      <span className="la-item__body">
                        <span className="body-strong">{matchName(fixture)}</span>
                        <span className="caption la-muted">
                          {kickOffDate(fixture.kick_off)} · {formatTime(fixture.kick_off)} · {fixture.pitch.name}
                        </span>
                      </span>
                      <FixtureStatusChip status={fixture.status} />
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )
        }
      </LoadState>
    </main>
  );
}

type Game = Schemas["MyPlayerRequest"];

/** Player and Goalkeeper Requests you can still answer, and the ones you joined. */
function GamesToJoin() {
  const [loaded, reload] = useLoad(() => api.GET("/api/v1/me/player-requests/"), "my-player-requests");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function answer(game: Game, reply: "accept" | "decline") {
    setBusy(true);
    const failed = await send(() =>
      api.POST("/api/v1/inbox/{notification_id}/answer/", {
        params: { path: { notification_id: game.notification_id } },
        body: { answer: reply },
      }),
    );
    setBusy(false);
    setError(failed?.general ?? null);
    reload();
  }

  const games = loaded.state === "ok" ? loaded.data : [];
  if (games.length === 0 && !error) return null;
  return (
    <section className="la-stack-2" aria-labelledby="games-to-join">
      <h2 id="games-to-join" className="la-overline">
        Games you can join
      </h2>
      {error && <Banner status="cancelled" title={error} />}
      {games.map((game) => (
        <MatchCard key={game.id} fixture={game.fixture}>
          <div className="la-stack-2">
            <span className="body-strong">
              {game.team.name} needs {wanted(game.kind, game.places)}
            </span>
            {game.joined ? (
              <StatusChip status="confirmed">{`You're playing for ${game.team.name}`}</StatusChip>
            ) : (
              <span className="caption la-muted">
                {game.places_left === 1 ? "1 place left" : `${game.places_left} places left`} · first to accept
                joins · until {deadline(game.answer_by)}
              </span>
            )}
            {game.can_answer && (
              <div className="la-actions">
                <button
                  type="button"
                  className="la-btn la-btn--primary"
                  disabled={busy}
                  onClick={() => void answer(game, "accept")}
                >
                  Join match
                </button>
                {game.my_answer === "decline" ? (
                  <StatusChip status="cancelled">Declined</StatusChip>
                ) : (
                  <button
                    type="button"
                    className="la-btn la-btn--secondary"
                    disabled={busy}
                    onClick={() => void answer(game, "decline")}
                  >
                    Not tonight
                  </button>
                )}
              </div>
            )}
          </div>
        </MatchCard>
      ))}
    </section>
  );
}
