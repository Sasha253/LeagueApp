// Payments on the Team screen: "Pay my share" for a Player in the Team and, for its
// Captain, who has paid, the Team total against what is due, the Team's credit and its
// Payment Barcode (design/src/ds/Screens.md Captain 1 and 6; PRD FR-21, FR-52).

import { Link } from "react-router";
import { api } from "../../api/client";
import { Banner } from "../../components/Banner";
import { formatRand } from "../../format";
import { useLoad } from "../club/shared";
import { PaymentProgress } from "./shared";

export function TeamPayments({ teamId, isCaptain }: { teamId: number; isCaptain: boolean }) {
  return (
    <section className="la-stack-2" aria-labelledby="payments">
      <h2 id="payments" className="la-overline">
        Payments
      </h2>
      {isCaptain && <CaptainPayments teamId={teamId} />}
      {isCaptain && (
        <Link className="la-btn la-btn--secondary la-btn--block" to={`/teams/${teamId}/barcode`}>
          Payment Barcode
        </Link>
      )}
      <Link className="la-btn la-btn--primary la-btn--block" to={`/teams/${teamId}/pay`}>
        Pay my share
      </Link>
    </section>
  );
}

function CaptainPayments({ teamId }: { teamId: number }) {
  const [summary, reload] = useLoad(
    () => api.GET("/api/v1/teams/{team_id}/payments/summary/", { params: { path: { team_id: teamId } } }),
    `team-payment-summary-${teamId}`,
  );
  if (summary.state === "loading") {
    return (
      <p className="caption la-muted" role="status">
        Loading payments
      </p>
    );
  }
  if (summary.state !== "ok") {
    return (
      <Banner status="cancelled" title="Couldn't load who has paid">
        <button type="button" className="la-btn la-btn--quiet" onClick={reload}>
          Retry
        </button>
      </Banner>
    );
  }
  const data = summary.data;
  return (
    <>
      <PaymentProgress summary={data} title="Team payments" />
      {data.team_credit !== null && (
        <div className="la-stat">
          <span className="la-stat__label">Team credit</span>
          <span className="la-stat__value">{formatRand(data.team_credit)}</span>
          <span className="caption la-muted">Only you, the Captain, can use it, when you pay.</span>
        </div>
      )}
    </>
  );
}
