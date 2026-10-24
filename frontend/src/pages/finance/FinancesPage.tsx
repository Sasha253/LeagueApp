// Finances (PRD FR-25, FR-49; design/src/ds/Screens.md Admin 5; design/src/screens/
// f14-finances.mjs): a Season's money for the club's Admin, filtered by Season, Night and
// Division. FinanceSummary at the top, then league money by method, the income lines
// (League, Friendlies, Bookings) and credit held, the Nights and Divisions, and the Teams,
// each opening its Team ledger. The week-by-week planner (FR-47) sits under FinanceSummary
// and the Outstanding list (FR-48) after the money by method, as in the design. Every
// amount is the API's (chunks 25 and 27); nothing is added up here. Export comes later.

import { useState } from "react";
import { Link } from "react-router";
import { api, type Schemas } from "../../api/client";
import { ChoiceChip } from "../../components/ChoiceChip";
import { formatRand, WEEKDAYS } from "../../format";
import { LoadState, useClub, useLoad } from "../club/shared";
import { Outstanding } from "./Outstanding";
import { Planner } from "./Planner";
import { PaidChip } from "../payments/shared";
import { ScreenHeader } from "../teams/shared";
import { IncomeRow, NOT_AN_ADMIN, openingSeason, Stat, type SeasonSummary } from "./shared";

type ClubNight = Schemas["ClubNight"];

export function FinancesPage() {
  const { clubId, clubName } = useClub();
  const [picked, setPicked] = useState<number | null>(null);
  const [night, setNight] = useState<number | null>(null);
  const [division, setDivision] = useState<number | null>(null);
  const [seasons, reloadSeasons] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/seasons/", { params: { path: { club_id: clubId } } }),
    `seasons-${clubId}`,
  );
  const [nights] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/nights/", { params: { path: { club_id: clubId } } }),
    `nights-${clubId}`,
  );
  const nightList = nights.state === "ok" ? nights.data : [];
  const chosenNight = nightList.find((n) => n.id === night);

  function pickNight(id: number | null) {
    setNight(id);
    setDivision(null);
  }

  return (
    <main className="la-screen">
      <ScreenHeader title="Finances" back={{ label: "Profile", to: "/profile" }} caption={clubName} />
      <div className="la-actions">
        <Link className="la-btn la-btn--secondary" to={`/clubs/${clubId}/finances/compare`}>
          Compare Seasons
        </Link>
      </div>
      <LoadState result={seasons} retry={reloadSeasons} what="Seasons" forbidden={NOT_AN_ADMIN}>
        {(list) => {
          const season = picked ?? openingSeason(list);
          if (season === null) {
            return <p className="body la-muted">No Seasons yet. Add a Season in Club setup to see its finances.</p>;
          }
          return (
            <>
              <fieldset className="la-fieldset la-stack-2">
                <legend className="la-overline">Season</legend>
                <div className="la-choices">
                  {list.map((s) => (
                    <ChoiceChip key={s.id} pressed={season === s.id} onToggle={() => setPicked(s.id)}>
                      {s.name}
                    </ChoiceChip>
                  ))}
                </div>
              </fieldset>
              {nightList.length > 0 && (
                <fieldset className="la-fieldset la-stack-2">
                  <legend className="la-overline">Night</legend>
                  <div className="la-choices">
                    <ChoiceChip pressed={night === null} onToggle={() => pickNight(null)}>
                      All
                    </ChoiceChip>
                    {nightList.map((n) => (
                      <ChoiceChip key={n.id} pressed={night === n.id} onToggle={() => pickNight(n.id)}>
                        {WEEKDAYS[n.weekday]}
                      </ChoiceChip>
                    ))}
                  </div>
                </fieldset>
              )}
              {chosenNight && chosenNight.divisions.length > 0 && (
                <fieldset className="la-fieldset la-stack-2">
                  <legend className="la-overline">Division</legend>
                  <div className="la-choices">
                    <ChoiceChip pressed={division === null} onToggle={() => setDivision(null)}>
                      All
                    </ChoiceChip>
                    {chosenNight.divisions.map((d) => (
                      <ChoiceChip key={d.id} pressed={division === d.id} onToggle={() => setDivision(d.id)}>
                        {d.name}
                      </ChoiceChip>
                    ))}
                  </div>
                </fieldset>
              )}
              <SeasonFinances season={season} night={chosenNight ?? null} division={division} />
            </>
          );
        }}
      </LoadState>
    </main>
  );
}

function SeasonFinances({ season, night, division }: { season: number; night: ClubNight | null; division: number | null }) {
  const { clubId } = useClub();
  const nightId = night?.id ?? null;
  // Bumped when cash is marked paid, so the totals, planner and Team list load again.
  const [version, setVersion] = useState(0);
  const scope = { season, night: nightId, division };
  const [summary, reload] = useLoad(
    () =>
      api.GET("/api/v1/clubs/{club_id}/finance/summary/", {
        params: {
          path: { club_id: clubId },
          query: { season, ...(nightId !== null && { night: nightId }), ...(division !== null && { division }) },
        },
      }),
    `finance-summary-${clubId}-${season}-${nightId}-${division}-${version}`,
  );
  return (
    <LoadState result={summary} retry={reload} what="finances" forbidden={NOT_AN_ADMIN}>
      {(data) => (
        <>
          <FinanceSummary summary={data} />
          <Planner scope={scope} label={scopeLabel(data)} version={version} />
          <section className="la-stack-2" aria-labelledby="by-method">
            <h2 id="by-method" className="la-overline">
              League money by method
            </h2>
            <div className="la-stats">
              <Stat label="Card" amount={data.totals.league.card} />
              <Stat label="Cash" amount={data.totals.league.cash} />
              <Stat label="Credit used" amount={data.totals.league.credit_spent} />
              <Stat label="Returned as credit" amount={data.totals.league.returned_as_credit} />
            </div>
          </section>
          <Outstanding scope={scope} onPaid={() => setVersion((n) => n + 1)} />
          <IncomeLines summary={data} />
          <Breakdown summary={data} />
          <Teams season={season} night={night} division={division} version={version} />
        </>
      )}
    </LoadState>
  );
}

function scopeLabel(summary: SeasonSummary): string {
  return [
    summary.season.name,
    summary.night ? WEEKDAYS[summary.night.weekday] : "All Nights",
    ...(summary.division ? [summary.division.name] : []),
  ].join(" · ");
}

/** FinanceSummary from the design system: the scope and four totals. */
function FinanceSummary({ summary }: { summary: SeasonSummary }) {
  const scope = scopeLabel(summary);
  const { totals } = summary;
  return (
    <section className="la-card la-stack" aria-label={`Finances, ${scope}`}>
      <p className="la-overline">{scope}</p>
      <div className="la-stats">
        <Stat label="Expected" amount={totals.expected} />
        <Stat label="Received" amount={totals.league.received} />
        <Stat label="Outstanding" amount={totals.outstanding} owed />
        <Stat label="Team credit held" amount={totals.team_credit_held} />
      </div>
      <p className="caption la-muted">
        League fees for {totals.teams} {totals.teams === 1 ? "Team" : "Teams"}. Received is card and cash taken; credit
        used counts towards what a Team has paid, not towards received.
      </p>
    </section>
  );
}

function Amount({ title, sub, amount }: { title: string; sub: string; amount: string }) {
  return (
    <li className="la-item">
      <span className="la-item__body">
        <span className="body-strong">{title}</span>
        <span className="caption la-muted">{sub}</span>
      </span>
      <span className="body-strong">{formatRand(amount)}</span>
    </li>
  );
}

/** League, friendly and booking money as separate lines (FR-49), then credit held. */
function IncomeLines({ summary }: { summary: SeasonSummary }) {
  const { totals, booking, credit_held: credit } = summary;
  return (
    <section className="la-stack-2" aria-labelledby="income">
      <h2 id="income" className="la-overline">
        Income
      </h2>
      <ul className="la-group" aria-label="Income lines">
        <IncomeRow title="League" line={totals.league} />
        <IncomeRow title="Friendlies" line={totals.friendly} />
        {booking ? (
          <IncomeRow title="Bookings" line={booking} />
        ) : (
          <li className="la-item">
            <span className="la-item__body">
              <span className="body-strong">Bookings</span>
              <span className="caption la-muted">Bookings belong to no Night or Division: clear the filter to see them.</span>
            </span>
          </li>
        )}
        <Amount title="All income received" sub="Card and cash, every line above" amount={summary.received} />
      </ul>
      {(credit.player !== null || credit.booking_user !== null) && (
        <ul className="la-group" aria-label="Credit held">
          {credit.player !== null && (
            <Amount title="Player credit held" sub="Club-wide, not yet spent" amount={credit.player} />
          )}
          {credit.booking_user !== null && (
            <Amount title="Booking User credit held" sub="Club-wide, not yet spent" amount={credit.booking_user} />
          )}
        </ul>
      )}
    </section>
  );
}

/** Each Night in scope and its Divisions: Teams, received against expected, what is owed. */
function Breakdown({ summary }: { summary: SeasonSummary }) {
  if (summary.nights.length === 0) {
    return <p className="body la-muted">No Teams in this Season here yet.</p>;
  }
  return (
    <section className="la-stack-2" aria-labelledby="by-division">
      <h2 id="by-division" className="la-overline">
        By Night and Division
      </h2>
      {summary.nights.map((n) => (
        <ul key={n.night.id} className="la-group" aria-label={WEEKDAYS[n.night.weekday]}>
          <Row title={WEEKDAYS[n.night.weekday]!} figures={n} strong />
          {n.divisions.map((d) => (
            <Row key={d.division.id} title={d.division.name} figures={d} />
          ))}
        </ul>
      ))}
    </section>
  );
}

function Row({
  title,
  figures,
  strong = false,
}: {
  title: string;
  figures: Schemas["LeagueFigures"];
  strong?: boolean;
}) {
  const teams = `${figures.teams} ${figures.teams === 1 ? "Team" : "Teams"}`;
  return (
    <li className="la-item">
      <span className="la-item__body">
        <span className={strong ? "body-strong" : "body"}>{title}</span>
        <span className="caption la-muted">
          {[teams, `${formatRand(figures.league.received)} received of ${formatRand(figures.expected)}`].join(" · ")}
          {Number(figures.friendly.received) !== 0 && ` · Friendlies ${formatRand(figures.friendly.received)}`}
        </span>
      </span>
      <PaidChip balance={{ is_paid: Number(figures.outstanding) <= 0, outstanding: figures.outstanding }} />
    </li>
  );
}

/** The Season's active Teams in scope, each opening its Team ledger (FR-26). */
function Teams({
  season,
  night,
  division,
  version,
}: {
  season: number;
  night: ClubNight | null;
  division: number | null;
  version: number;
}) {
  const { clubId } = useClub();
  const [teams, reload] = useLoad(
    () =>
      api.GET("/api/v1/clubs/{club_id}/team-payments/", {
        params: { path: { club_id: clubId }, query: { season } },
      }),
    `club-team-payments-${clubId}-${season}-${version}`,
  );
  const inNight = new Set(night?.divisions.map((d) => d.id));
  return (
    <section className="la-stack-2" aria-labelledby="team-ledgers">
      <h2 id="team-ledgers" className="la-overline">
        Team ledgers
      </h2>
      <LoadState result={teams} retry={reload} what="Teams" forbidden={NOT_AN_ADMIN}>
        {(list) => {
          const rows = list.filter(
            (row) =>
              row.season.id === season &&
              (division !== null ? row.division.id === division : night === null || inNight.has(row.division.id)),
          );
          if (rows.length === 0) return <p className="body la-muted">No active Teams here.</p>;
          return (
            <ul className="la-group" aria-label="Teams">
              {rows.map((row) => (
                <li key={row.team.id}>
                  <Link className="la-item la-item--link" to={`/clubs/${clubId}/finances/teams/${row.team.id}`}>
                    <span className="la-item__body">
                      <span className="body-strong">{row.team.name}</span>
                      <span className="caption la-muted">
                        {row.division.name} · {formatRand(row.paid)} of {formatRand(row.due)}
                      </span>
                    </span>
                    <PaidChip balance={row} />
                  </Link>
                </li>
              ))}
            </ul>
          );
        }}
      </LoadState>
    </section>
  );
}
