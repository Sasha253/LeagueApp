// Fixtures (design/src/ds/Screens.md, Admin 2): the club's Fixtures by Night, day by day, for
// its Admin. Opens a Fixture, and the import. Reschedule and cancel come in a later chunk.

import { useState } from "react";
import { Link } from "react-router";
import { api, type Schemas } from "../../api/client";
import { ChoiceChip } from "../../components/ChoiceChip";
import { formatTime, WEEKDAYS } from "../../format";
import { LoadState, useClub, useLoad } from "../club/shared";
import { ScreenHeader } from "../teams/shared";
import { FixtureStatusChip, kickOffDate, matchName } from "./shared";

type Fixture = Schemas["AdminFixture"];

export const NOT_AN_ADMIN = "Only this club's Admins can see its Fixtures.";

/** Fixtures in kick-off order, grouped by their South African date. */
function byDay(fixtures: Fixture[]): [string, Fixture[]][] {
  const days = new Map<string, Fixture[]>();
  for (const fixture of fixtures) {
    const day = kickOffDate(fixture.kick_off);
    days.set(day, [...(days.get(day) ?? []), fixture]);
  }
  return [...days];
}

export function ClubFixturesPage() {
  const { clubId, clubName } = useClub();
  const [season, setSeason] = useState<number | null>(null);
  const [night, setNight] = useState<number | null>(null);
  const [seasons] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/seasons/", { params: { path: { club_id: clubId } } }),
    `seasons-${clubId}`,
  );
  const [nights] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/nights/", { params: { path: { club_id: clubId } } }),
    `nights-${clubId}`,
  );
  const [fixtures, reload] = useLoad(
    () =>
      api.GET("/api/v1/clubs/{club_id}/fixtures/", {
        params: {
          path: { club_id: clubId },
          query: { ...(season !== null && { season }), ...(night !== null && { night }) },
        },
      }),
    `fixtures-${clubId}-${season}-${night}`,
  );

  return (
    <main className="la-screen">
      <ScreenHeader title="Fixtures" back={{ label: "Profile", to: "/profile" }} caption={clubName} />
      <div className="la-actions">
        <Link className="la-btn la-btn--secondary" to={`/clubs/${clubId}/setup/import`}>
          Import fixtures
        </Link>
        <Link className="la-btn la-btn--secondary" to={`/clubs/${clubId}/requests`}>
          Captain requests
        </Link>
      </div>

      {seasons.state === "ok" && seasons.data.length > 0 && (
        <fieldset className="la-fieldset la-stack-2">
          <legend className="la-overline">Season</legend>
          <div className="la-choices">
            <ChoiceChip pressed={season === null} onToggle={() => setSeason(null)}>
              Current
            </ChoiceChip>
            {seasons.data.map((s) => (
              <ChoiceChip key={s.id} pressed={season === s.id} onToggle={() => setSeason(s.id)}>
                {s.name}
              </ChoiceChip>
            ))}
          </div>
        </fieldset>
      )}
      {nights.state === "ok" && nights.data.length > 0 && (
        <fieldset className="la-fieldset la-stack-2">
          <legend className="la-overline">Night</legend>
          <div className="la-choices">
            <ChoiceChip pressed={night === null} onToggle={() => setNight(null)}>
              All
            </ChoiceChip>
            {nights.data.map((n) => (
              <ChoiceChip key={n.id} pressed={night === n.id} onToggle={() => setNight(n.id)}>
                {WEEKDAYS[n.weekday]}
              </ChoiceChip>
            ))}
          </div>
        </fieldset>
      )}

      <LoadState result={fixtures} retry={reload} what="fixtures" forbidden={NOT_AN_ADMIN}>
        {(list) =>
          list.length === 0 ? (
            <p className="body la-muted">No fixtures here yet. Import the Season's fixtures from a spreadsheet.</p>
          ) : (
            byDay(list).map(([day, games]) => (
              <section key={day} className="la-stack-2" aria-label={day}>
                <h2 className="la-overline">{day}</h2>
                <ul className="la-group">
                  {games.map((fixture) => (
                    <li key={fixture.id}>
                      <Link className="la-item la-item--link" to={`/clubs/${clubId}/fixtures/${fixture.id}`}>
                        <span className="la-item__body">
                          <span className="caption la-muted">
                            {formatTime(fixture.kick_off)} · {fixture.pitch.name}
                          </span>
                          <span className="body-strong">{matchName(fixture)}</span>
                          <span className="caption la-muted">
                            {WEEKDAYS[fixture.weekday]} · {fixture.division.name}
                            {fixture.friendly_eligible && " · Friendly-eligible"}
                          </span>
                        </span>
                        <FixtureStatusChip status={fixture.status} />
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            ))
          )
        }
      </LoadState>
    </main>
  );
}
