// Compare Seasons (PRD FR-27): income per Season, oldest first, with League, Friendlies and
// Bookings as their own lines, then each Night's league and friendly income. Pick which
// Seasons to compare; with none picked, every Season of the club. Every amount is the API's.

import { useState } from "react";
import { api } from "../../api/client";
import { ChoiceChip } from "../../components/ChoiceChip";
import { formatRand, WEEKDAYS } from "../../format";
import { LoadState, useClub, useLoad } from "../club/shared";
import { ScreenHeader } from "../teams/shared";
import { IncomeRow, NOT_AN_ADMIN, type SeasonIncome } from "./shared";

export function ComparisonPage() {
  const { clubId, clubName } = useClub();
  const [picked, setPicked] = useState<number[]>([]);
  const [seasons] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/seasons/", { params: { path: { club_id: clubId } } }),
    `seasons-${clubId}`,
  );
  const wanted = [...picked].sort((a, b) => a - b).join(",");
  const [comparison, reload] = useLoad(
    () =>
      api.GET("/api/v1/clubs/{club_id}/finance/comparison/", {
        params: { path: { club_id: clubId }, query: wanted ? { seasons: wanted } : {} },
      }),
    `finance-comparison-${clubId}-${wanted}`,
  );

  function toggle(id: number) {
    setPicked((now) => (now.includes(id) ? now.filter((n) => n !== id) : [...now, id]));
  }

  return (
    <main className="la-screen">
      <ScreenHeader title="Compare Seasons" back={{ label: "Finances", to: `/clubs/${clubId}/finances` }} caption={clubName} />
      {seasons.state === "ok" && seasons.data.length > 1 && (
        <fieldset className="la-fieldset la-stack-2">
          <legend className="la-overline">Seasons</legend>
          <div className="la-choices">
            <ChoiceChip pressed={picked.length === 0} onToggle={() => setPicked([])}>
              All
            </ChoiceChip>
            {seasons.data.map((s) => (
              <ChoiceChip key={s.id} pressed={picked.includes(s.id)} onToggle={() => toggle(s.id)}>
                {s.name}
              </ChoiceChip>
            ))}
          </div>
        </fieldset>
      )}
      <LoadState result={comparison} retry={reload} what="comparison" forbidden={NOT_AN_ADMIN}>
        {(list) =>
          list.length === 0 ? (
            <p className="body la-muted">No Seasons yet. Add a Season in Club setup to compare its income.</p>
          ) : (
            list.map((season) => <SeasonCard key={season.season.id} season={season} />)
          )
        }
      </LoadState>
    </main>
  );
}

function SeasonCard({ season }: { season: SeasonIncome }) {
  const name = season.season.name;
  return (
    <section className="la-card la-stack" aria-label={name}>
      <div className="la-row">
        <h2 className="la-overline">{name}</h2>
        <span className="title-2">{formatRand(season.received)}</span>
      </div>
      <ul className="la-group" aria-label={`${name} income lines`}>
        <IncomeRow title="League" line={season.league} />
        <IncomeRow title="Friendlies" line={season.friendly} />
        <IncomeRow title="Bookings" line={season.booking} />
      </ul>
      {season.nights.length > 0 && (
        <ul className="la-group" aria-label={`${name} by Night`}>
          {season.nights.map((n) => (
            <li key={n.night.id} className="la-item">
              <span className="la-item__body">
                <span className="body-strong">{WEEKDAYS[n.night.weekday]}</span>
                <span className="caption la-muted">
                  League {formatRand(n.league.received)} · Friendlies {formatRand(n.friendly.received)}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
