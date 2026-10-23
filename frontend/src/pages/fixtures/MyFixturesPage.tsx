// My fixtures (design/src/ds/Screens.md, Player 1 "Matches"): the upcoming and past Fixtures
// of the Teams you're in now, for Players and Captains. Replies, squads and payments come
// with later chunks.

import { Link } from "react-router";
import { api } from "../../api/client";
import { LoadState, useLoad } from "../club/shared";
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
