// Back from PayFast (PAYMENT_RETURN_URL and PAYMENT_CANCEL_URL, ?payment=<reference>), or
// from the in-app browser: what happened to the payment. Only PayFast's notification to
// the backend records a card payment, so while it is pending this screen asks again.

import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { api } from "../../api/client";
import { Banner } from "../../components/Banner";
import { formatRand } from "../../format";
import { openCheckout } from "../../native/browser";
import { LoadState, useLoad } from "../club/shared";
import { PaymentStatus, type Payment } from "./shared";

/** How often, and how many times, a pending payment is checked again by itself. */
const RECHECK_MS = 3000;
const RECHECKS = 10;

export function PaymentResultPage({ left = false }: { left?: boolean }) {
  const [params] = useSearchParams();
  const reference = params.get("payment") ?? "";
  return (
    <main className="la-screen">
      <div className="la-stack-2">
        <Link className="la-btn la-btn--quiet la-back" to="/teams">
          Teams
        </Link>
        <h1 className="title-1">Payment</h1>
      </div>
      {reference ? (
        <Result reference={reference} left={left} />
      ) : (
        <Banner status="cancelled" title="No payment to show">
          Open your Team to pay or see what is owed.
        </Banner>
      )}
    </main>
  );
}

function Result({ reference, left }: { reference: string; left: boolean }) {
  const [checks, setChecks] = useState(0);
  const [payment, reload] = useLoad(
    () => api.GET("/api/v1/payments/{reference}/", { params: { path: { reference } } }),
    `payment-${reference}`,
  );
  const pending = payment.state === "ok" && payment.data.status === "pending";

  // While PayFast hasn't told the backend yet, check again a few times by itself.
  useEffect(() => {
    if (!pending || left || checks >= RECHECKS) return;
    const timer = setTimeout(() => {
      setChecks((n) => n + 1);
      reload();
    }, RECHECK_MS);
    return () => clearTimeout(timer);
  }, [pending, left, checks, reload, payment]);

  return (
    <LoadState result={payment} retry={reload} what="payment">
      {(data) => <Outcome payment={data} left={left} recheck={reload} />}
    </LoadState>
  );
}

function Outcome({ payment, left, recheck }: { payment: Payment; left: boolean; recheck: () => void }) {
  const [error, setError] = useState<string | null>(null);
  // A payment is for a Team (a Player's share) or a Booking (its Booking User).
  const target = payment.booking
    ? { name: `your ${payment.booking.field.name} booking`, to: `/bookings/${payment.booking.id}`, back: "Back to the booking" }
    : {
        name: payment.team!.name,
        to: `/teams/${payment.team!.id}`,
        back: `Back to ${payment.team!.name}`,
      };
  const payAgain = payment.booking ? target.to : `/teams/${payment.team!.id}/pay`;
  const credit = Number(payment.credit_amount) > 0;
  const card = Number(payment.card_amount) > 0;

  async function payByCard() {
    if (!payment.checkout) return;
    setError(null);
    try {
      if (await openCheckout(payment.checkout.url)) recheck();
    } catch {
      setError("Couldn't open PayFast. Try again.");
    }
  }

  return (
    <>
      <section className="la-card la-stack-2" aria-label="Your payment">
        <div className="la-row">
          <span className="body-strong">
            {formatRand(payment.amount)} towards {target.name}
          </span>
          <PaymentStatus payment={payment} />
        </div>
        {credit && <span className="caption la-muted">{formatRand(payment.credit_amount)} from credit</span>}
        {card && <span className="caption la-muted">{formatRand(payment.card_amount)} by card</span>}
      </section>

      {payment.status === "complete" && (
        <Banner status="confirmed" title="Paid">
          Thanks. Your payment is recorded for {target.name}.
        </Banner>
      )}
      {payment.status === "pending" && left && (
        <Banner status="pending" title="Not paid yet">
          You left PayFast before paying. {credit ? "Your credit is already used. " : ""}Pay{" "}
          {formatRand(payment.card_amount)} by card to finish.
        </Banner>
      )}
      {payment.status === "pending" && !left && (
        <Banner status="pending" title="Waiting for PayFast">
          PayFast tells us once the card payment goes through. This can take a minute.
        </Banner>
      )}
      {(payment.status === "failed" || payment.status === "cancelled") && (
        <Banner status="cancelled" title={payment.status === "failed" ? "The card payment failed" : "The card payment was cancelled"}>
          {credit ? `The credit you used still counts towards ${target.name}. ` : ""}You can pay again.
        </Banner>
      )}
      {error && <Banner status="cancelled" title={error} />}

      <div className="la-stack-2">
        {payment.status === "pending" && payment.checkout && (
          <button type="button" className="la-btn la-btn--primary la-btn--block" onClick={() => void payByCard()}>
            {`Pay ${formatRand(payment.card_amount)} by card`}
          </button>
        )}
        {payment.status === "pending" && !payment.checkout && (
          <p className="caption la-muted">This card payment can't be finished any more. Pay again.</p>
        )}
        {payment.status === "pending" && (
          <button type="button" className="la-btn la-btn--secondary la-btn--block" onClick={recheck}>
            Check again
          </button>
        )}
        {(payment.status === "failed" || payment.status === "cancelled") && (
          <Link className="la-btn la-btn--primary la-btn--block" to={payAgain}>
            Pay again
          </Link>
        )}
        <Link className="la-btn la-btn--quiet la-btn--block" to={target.to}>
          {target.back}
        </Link>
      </div>
    </>
  );
}
