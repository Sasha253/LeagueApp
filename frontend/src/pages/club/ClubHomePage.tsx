// Club home (design/src/ds/Screens.md, Admin tab "More"; docs/DECISIONS.md): one place for a
// Club's Admin. The current Season's money at the top (FinanceSummary and the income lines,
// as on Finances), then everything the Admin can add, then every Admin screen. Every amount
// is the API's; nothing is added up here.

import { Link } from "react-router";
import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthProvider";
import { FinanceSummary, IncomeLines } from "../finance/FinancesPage";
import { NOT_AN_ADMIN, openingSeason } from "../finance/shared";
import { ScreenHeader } from "../teams/shared";
import { LoadState, useClub, useLoad } from "./shared";

type Entry = { path: string; title: string; detail: string };

const ADD: Entry[] = [
  { path: "teams/new", title: "Team", detail: "Confirmed at once, with its Captain" },
  { path: "players/invite", title: "Player", detail: "Invite by email to a Team" },
  { path: "fixtures/new", title: "Fixture", detail: "One match: Teams, pitch and kick-off" },
  { path: "setup/seasons", title: "Season", detail: "When it runs" },
  { path: "setup/nights", title: "Night or Division", detail: "Minimum players and Division fees" },
  { path: "setup/fields", title: "Field", detail: "Pitches and their Referees" },
  { path: "setup/people", title: "Admin or Referee", detail: "Invite by email" },
  { path: "setup/import", title: "Import from Excel", detail: "Seasons, Nights and Divisions, and Fixtures" },
];

const RUN: Entry[] = [
  { path: "tonight", title: "Tonight", detail: "Tonight's matches, at risk first" },
  { path: "fixtures", title: "Fixtures", detail: "Reschedule, cancel, friendly-eligible" },
  { path: "teams", title: "Team requests", detail: "Confirm or decline Teams, assign Captains" },
  { path: "requests", title: "Captain requests", detail: "Cancellations and postponements" },
  { path: "bookings", title: "Bookings", detail: "Field bookings to confirm" },
  { path: "payments", title: "Payments", detail: "What each Team has paid" },
  { path: "scan", title: "Scan", detail: "Payment Barcodes at the gate" },
  { path: "finances", title: "Finances", detail: "Planner, who owes, ledgers, export" },
  { path: "setup", title: "Club setup", detail: "Fees, cutoffs, booking policy, payments" },
];

export function ClubHomePage() {
  const { clubId, clubName } = useClub();
  const { state } = useAuth();
  const superuser = state.status === "signedIn" && state.me.is_superuser;
  const [seasons, reload] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/seasons/", { params: { path: { club_id: clubId } } }),
    `seasons-${clubId}`,
  );

  return (
    <main className="la-screen">
      <ScreenHeader
        title="Club home"
        back={superuser ? { label: "All clubs", to: "/clubs" } : { label: "Profile", to: "/profile" }}
        caption={clubName}
      />
      <LoadState result={seasons} retry={reload} what="club" forbidden="Only this club's Admins can open its home.">
        {(list) => {
          const season = openingSeason(list);
          return (
            <>
              {season === null ? (
                <p className="body la-muted">No Seasons yet. Add a Season to see its finances here.</p>
              ) : (
                <Money season={season} />
              )}
              <Entries id="add" title="Add" entries={ADD} />
              {superuser && (
                <ul className="la-group" aria-label="Add a club">
                  <li>
                    <Link className="la-item la-item--link" to="/clubs/new">
                      <span className="la-item__body">
                        <span className="body-strong">Club</span>
                        <span className="caption la-muted">A new club and its first Admin</span>
                      </span>
                    </Link>
                  </li>
                </ul>
              )}
              <Entries id="run" title="Run the club" entries={RUN} />
            </>
          );
        }}
      </LoadState>
    </main>
  );
}

/** The Season's FinanceSummary and income lines, all Nights and Divisions. */
function Money({ season }: { season: number }) {
  const { clubId } = useClub();
  const [summary, reload] = useLoad(
    () =>
      api.GET("/api/v1/clubs/{club_id}/finance/summary/", {
        params: { path: { club_id: clubId }, query: { season } },
      }),
    `finance-summary-${clubId}-${season}`,
  );
  return (
    <LoadState result={summary} retry={reload} what="finances" forbidden={NOT_AN_ADMIN}>
      {(data) => (
        <>
          <FinanceSummary summary={data} />
          <IncomeLines summary={data} />
          <div className="la-actions">
            <Link className="la-btn la-btn--secondary" to={`/clubs/${clubId}/finances`}>
              All finances
            </Link>
            <Link className="la-btn la-btn--quiet" to={`/clubs/${clubId}/finances/export`}>
              Export
            </Link>
          </div>
        </>
      )}
    </LoadState>
  );
}

function Entries({ id, title, entries }: { id: string; title: string; entries: Entry[] }) {
  const { clubId } = useClub();
  return (
    <section className="la-stack-2" aria-labelledby={id}>
      <h2 id={id} className="la-overline">
        {title}
      </h2>
      <ul className="la-group">
        {entries.map((entry) => (
          <li key={entry.path}>
            <Link className="la-item la-item--link" to={`/clubs/${clubId}/${entry.path}`}>
              <span className="la-item__body">
                <span className="body-strong">{entry.title}</span>
                <span className="caption la-muted">{entry.detail}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
