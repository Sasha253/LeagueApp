// Which Teams have paid (PRD FR-21, Admin): the club's active Teams, unpaid first, each
// opening the Team's payments, where cash is recorded (FR-22).

import { Link } from "react-router";
import { api } from "../../api/client";
import { LoadState, useClub, useLoad } from "../club/shared";
import { NOT_AN_ADMIN } from "../teams/ClubTeamsPage";
import { ScreenHeader } from "../teams/shared";
import { formatRand } from "../../format";
import { PaidChip } from "./shared";

export function ClubPaymentsPage() {
  const { clubId, clubName } = useClub();
  const [teams, reload] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/team-payments/", { params: { path: { club_id: clubId } } }),
    `club-team-payments-${clubId}`,
  );
  return (
    <main className="la-screen">
      <ScreenHeader title="Payments" back={{ label: "Profile", to: "/profile" }} caption={clubName} />
      <LoadState result={teams} retry={reload} what="payments" forbidden={NOT_AN_ADMIN}>
        {(list) =>
          list.length === 0 ? (
            <p className="body la-muted">No active Teams yet.</p>
          ) : (
            <ul className="la-group" aria-label="Teams">
              {list.map((row) => (
                <li key={row.team.id}>
                  <Link className="la-item la-item--link" to={`/clubs/${clubId}/payments/${row.team.id}`}>
                    <span className="la-item__body">
                      <span className="body-strong">{row.team.name}</span>
                      <span className="caption la-muted">
                        {[row.division.name, row.season.name, `${formatRand(row.paid)} of ${formatRand(row.due)}`].join(" · ")}
                      </span>
                    </span>
                    <PaidChip balance={row} />
                  </Link>
                </li>
              ))}
            </ul>
          )
        }
      </LoadState>
    </main>
  );
}
