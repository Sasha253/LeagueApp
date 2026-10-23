// A friendly's Payment Barcode for the Captain the Admin assigned (PRD FR-24): the
// PaymentTicket to show at the gate, valid for that friendly only. The backend decides
// whether there is a valid one; when there isn't, this screen shows its reason.

import { useParams } from "react-router";
import { api } from "../../api/client";
import { Banner } from "../../components/Banner";
import { PaymentTicket } from "../../components/PaymentTicket";
import { LoadState, useLoad } from "../club/shared";
import { ScreenHeader } from "../teams/shared";
import { ticketText } from "./BarcodePage";

const NOT_CAPTAIN = "Only the friendly's Captain can open its Payment Barcode.";

export function FriendlyBarcodePage() {
  const fixtureId = Number(useParams().fixtureId);
  const [current, reload] = useLoad(
    () =>
      api.GET("/api/v1/friendlies/{fixture_id}/barcode/", { params: { path: { fixture_id: fixtureId } } }),
    `friendly-barcode-${fixtureId}`,
  );
  return (
    <main className="la-screen">
      <ScreenHeader title="Friendly Barcode" back={{ label: "My fixtures", to: "/fixtures" }} />
      <LoadState result={current} retry={reload} what="Payment Barcode" forbidden={NOT_CAPTAIN}>
        {(data) =>
          data.barcode ? (
            <div className="la-stack">
              <PaymentTicket
                {...ticketText(data.barcode)}
                team={data.barcode.holder}
                code={data.barcode.code}
                displayCode={data.barcode.display_code}
              />
              <p className="caption la-muted">
                You are the friendly's Captain. Show this at the gate; it lets the friendly in once.
              </p>
            </div>
          ) : (
            <Banner status={data.state === "unpaid" ? "pending" : "cancelled"} title="No Payment Barcode yet">
              {data.reason}
            </Banner>
          )
        }
      </LoadState>
    </main>
  );
}
