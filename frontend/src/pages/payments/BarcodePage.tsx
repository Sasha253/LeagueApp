// The Captain's Payment Barcode (Screens.md Captain 6; PRD "Barcode authorisation"): the
// PaymentTicket to show at the gate, valid for this match only (gateway mode) or for the
// rest of the Season (cash-only mode). The backend decides whether there is a valid one;
// when there isn't, this screen shows its reason.

import { Link, useParams } from "react-router";
import { api, type Schemas } from "../../api/client";
import { Banner } from "../../components/Banner";
import { PaymentTicket } from "../../components/PaymentTicket";
import { formatDate, formatMoment } from "../../format";
import { LoadState, useLoad } from "../club/shared";
import { ScreenHeader } from "../teams/shared";

type Barcode = Schemas["Barcode"];

const NOT_CAPTAIN = "Only the Team's Captain can open its Payment Barcode.";

/** What the ticket says it is for, and how long it is valid. */
export function ticketText(barcode: Barcode): { kicker: string; status: string } {
  if (barcode.fixture) {
    return {
      kicker: `${formatMoment(barcode.fixture.kick_off)} · ${barcode.fixture.pitch.name}`,
      status: "Paid · valid for this match only",
    };
  }
  return {
    kicker: `${barcode.season.name} Season`,
    status: `Paid · valid until ${formatDate(barcode.valid_until)}`,
  };
}

export function BarcodePage() {
  const teamId = Number(useParams().teamId);
  const [current, reload] = useLoad(
    () => api.GET("/api/v1/teams/{team_id}/barcode/", { params: { path: { team_id: teamId } } }),
    `team-barcode-${teamId}`,
  );
  return (
    <main className="la-screen">
      <ScreenHeader title="Payment Barcode" back={{ label: "Team", to: `/teams/${teamId}` }} />
      <LoadState result={current} retry={reload} what="Payment Barcode" forbidden={NOT_CAPTAIN}>
        {(data) =>
          data.barcode ? (
            <div className="la-stack">
              <PaymentTicket
                {...ticketText(data.barcode)}
                team={data.barcode.team.name}
                code={data.barcode.code}
                displayCode={data.barcode.display_code}
              />
              <p className="caption la-muted">
                Show this at the gate. Turn your screen brightness up so it scans first time.
              </p>
            </div>
          ) : (
            <div className="la-stack">
              <Banner status={data.state === "unpaid" ? "pending" : "cancelled"} title="No Payment Barcode yet">
                {data.reason}
              </Banner>
              {data.state === "unpaid" && (
                <Link className="la-btn la-btn--primary la-btn--block" to={`/teams/${teamId}/pay`}>
                  Pay my share
                </Link>
              )}
              {data.state === "revoked" && (
                <p className="caption la-muted">Ask an Admin of the club for a new one.</p>
              )}
            </div>
          )
        }
      </LoadState>
    </main>
  );
}
