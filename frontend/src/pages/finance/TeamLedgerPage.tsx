// Team ledger (PRD FR-26, FR-50; design/src/ds/Screens.md Admin 6): PaymentProgress for the
// Team, what it paid by method and its credit held, then every line on its account newest
// first: date, Player, amount, method (Card, Cash or Credit) and who recorded it. Read-only:
// a correction is a new reversing entry with a reason, never an edit, so nothing here
// changes an entry.

import { useParams } from "react-router";
import { api } from "../../api/client";
import { formatDate, formatRand, formatTime, localDate, WEEKDAYS } from "../../format";
import { LoadState, useClub, useLoad } from "../club/shared";
import { PaymentProgress } from "../payments/shared";
import { ScreenHeader } from "../teams/shared";
import { entryTitle, MethodChip, NOT_AN_ADMIN, Stat, type LedgerEntry } from "./shared";

export function TeamLedgerPage() {
  const { clubId, clubName } = useClub();
  const teamId = Number(useParams().teamId);
  const [ledger, reload] = useLoad(
    () =>
      api.GET("/api/v1/clubs/{club_id}/finance/teams/{team_id}/", {
        params: { path: { club_id: clubId, team_id: teamId } },
      }),
    `finance-team-${clubId}-${teamId}`,
  );
  const back = { label: "Finances", to: `/clubs/${clubId}/finances` };
  return (
    <main className="la-screen">
      {ledger.state !== "ok" && <ScreenHeader title="Team ledger" back={back} caption={clubName} />}
      <LoadState result={ledger} retry={reload} what="Team ledger" forbidden={NOT_AN_ADMIN}>
        {(data) => (
          <>
            <ScreenHeader
              title={data.team.name}
              back={back}
              caption={[clubName, data.season.name, WEEKDAYS[data.night.weekday], data.division.name].join(" · ")}
            />
            <PaymentProgress summary={data} title="Team payments" />
            <section className="la-stack-2" aria-labelledby="paid-by">
              <h2 id="paid-by" className="la-overline">
                Paid by method
              </h2>
              <div className="la-stats">
                <Stat label="Card" amount={data.paid_by_method.card} />
                <Stat label="Cash" amount={data.paid_by_method.cash} />
                <Stat label="Credit" amount={data.paid_by_method.credit} />
                <Stat label="Team credit held" amount={data.team_credit_held} />
              </div>
              {Number(data.outstanding) < 0 && (
                <p className="caption la-muted">
                  {data.team.name} has paid {formatRand(data.outstanding.replace("-", ""))} more than it owes.
                </p>
              )}
            </section>
            <section className="la-stack-2" aria-labelledby="entries">
              <h2 id="entries" className="la-overline">
                Ledger · newest first
              </h2>
              {data.entries.length === 0 ? (
                <p className="body la-muted">Nothing on this Team's account yet.</p>
              ) : (
                <ul className="la-group" aria-label="Ledger entries">
                  {data.entries.map((entry) => (
                    <Entry key={entry.id} entry={entry} />
                  ))}
                </ul>
              )}
              <p className="caption la-muted">
                Entries are never changed. A correction is a new entry that reverses one, with its reason.
              </p>
            </section>
          </>
        )}
      </LoadState>
    </main>
  );
}

function Entry({ entry }: { entry: LedgerEntry }) {
  const when = `${formatDate(localDate(entry.created_at))} · ${formatTime(entry.created_at)}`;
  const by = entry.recorded_by_name ? `Recorded by ${entry.recorded_by_name}` : "Recorded by the app";
  return (
    <li className="la-item" aria-label={`Entry ${entry.id}`}>
      <span className="la-item__body">
        <span className="caption la-muted">{when}</span>
        <span className="body-strong">{entryTitle(entry)}</span>
        <span className="caption la-muted">{[`Entry ${entry.id}`, by].join(" · ")}</span>
        {entry.reason && <span className="caption la-muted">{entry.reason}</span>}
      </span>
      <span className="la-stack-2">
        <span className="body-strong">{formatRand(entry.amount)}</span>
        <MethodChip method={entry.method} />
      </span>
    </li>
  );
}
