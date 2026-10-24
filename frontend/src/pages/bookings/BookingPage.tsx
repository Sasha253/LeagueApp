// A booking (design/src/ds/Screens.md, Booking User 3; f15-booking.mjs "approved"): its
// status, what is paid and owed, Pay once payment is due (FR-34; credit first, FR-46), the
// entry Barcode once the club accepts it (FR-30), and Reschedule and Cancel (FR-31) with the
// club's policy and what they would mean now (FR-45). Every amount, outcome and whether each
// can be done is the API's decision.

import { useState } from "react";
import { useNavigate, useParams } from "react-router";
import { api, type Schemas } from "../../api/client";
import type { FormErrors } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { PaymentTicket } from "../../components/PaymentTicket";
import { formatMoment, formatRand, formatTime, localDate } from "../../format";
import { openCheckout } from "../../native/browser";
import { LoadState, send, useLoad } from "../club/shared";
import { ScreenHeader } from "../teams/shared";
import {
  BookingStatus,
  type Booking,
  hoursLabel,
  PolicyList,
  priceLine,
  SlotPicker,
  type Slot,
  whenLine,
} from "./shared";

const NOT_YOURS = "This booking isn't yours.";

type Payment = Schemas["Payment"];

export function BookingPage() {
  const id = Number(useParams().bookingId);
  const [booking, reload] = useLoad(
    () => api.GET("/api/v1/me/bookings/{id}/", { params: { path: { id } } }),
    `booking-${id}`,
  );

  return (
    <main className="la-screen">
      <ScreenHeader title="Booking" back={{ label: "My bookings", to: "/bookings" }} />
      <LoadState result={booking} retry={reload} what="booking" forbidden={NOT_YOURS}>
        {(loaded) => <Detail key={`${loaded.id}-${loaded.status}-${loaded.starts_at}`} initial={loaded} />}
      </LoadState>
    </main>
  );
}

function Detail({ initial }: { initial: Booking }) {
  const [b, setB] = useState(initial);
  const owes = Number(b.outstanding) > 0;
  const paid = Number(b.paid) > 0;

  return (
    <>
      <div className="la-card la-stack-2">
        <div className="la-section-head">
          <span className="la-overline">{`${b.club.name} · ${b.field.name}`}</span>
          <BookingStatus booking={b} />
        </div>
        <p className="title-2">{whenLine(b)}</p>
        <div className="la-kv">
          <span>{priceLine(b)}</span>
          <span>{formatRand(b.price)}</span>
        </div>
        {paid && (
          <div className="la-kv">
            <span>Paid</span>
            <span>{formatRand(b.paid)}</span>
          </div>
        )}
        {b.status === "accepted" && owes && (
          <div className="la-kv">
            <span>Still to pay</span>
            <span>{formatRand(b.outstanding)}</span>
          </div>
        )}
        <p className="caption la-muted">{hoursLabel(b.hours)}</p>
      </div>

      {b.status === "pending" && !b.is_over && (
        <Banner status="pending" title="Waiting for the club">
          The club approves every booking. Your entry Barcode appears here once it's accepted.
        </Banner>
      )}
      {b.status === "declined" && (
        <Banner status="cancelled" title="The club declined this booking">
          {b.decline_reason || undefined}
        </Banner>
      )}
      {b.status === "cancelled" && b.cancelled_by_club && (
        <Banner status="cancelled" title="The club cancelled this booking">
          Any credit it returned is used first on your next booking. Your Updates say why it was cancelled.
        </Banner>
      )}
      {b.status === "accepted" && !b.is_over && owes && !b.payment_requested && (
        <p className="caption la-muted">{`Payment is taken ${formatMoment(b.payment_due_at)}.`}</p>
      )}
      {b.can_pay && <PayNow booking={b} />}
      {b.status === "accepted" && !b.is_over && owes && b.payment_requested && !b.can_pay && (
        <Banner status="pending" title={`Payment due: ${formatRand(b.outstanding)}`}>
          {`Pay ${formatRand(b.outstanding)} to the club before you play.`}
        </Banner>
      )}
      {b.status === "accepted" && !b.is_over && <EntryBarcode booking={b} />}

      {(b.can_cancel || b.can_reschedule) && <Changes booking={b} onChanged={setB} />}
    </>
  );
}

function PayNow({ booking }: { booking: Booking }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function pay() {
    setBusy(true);
    setError(null);
    let payment: Payment | undefined;
    const failed = await send(async () => {
      const answer = await api.POST("/api/v1/me/bookings/{id}/pay/", { params: { path: { id: booking.id } } });
      payment = answer.data;
      return answer;
    });
    if (failed || !payment) {
      setBusy(false);
      setError(failed?.general ?? "That didn't work. Try again.");
      return;
    }
    const result = `/payments/done?payment=${payment.reference}`;
    if (payment.status === "pending" && payment.checkout) {
      try {
        // In a browser this page leaves for PayFast, which sends the user back itself.
        if (!(await openCheckout(payment.checkout.url))) return;
      } catch {
        // The result screen offers "Pay by card" again.
      }
    }
    navigate(result);
  }

  return (
    <section className="la-stack-2" aria-label="Pay for this booking">
      <Banner status="pending" title={`Payment due: ${formatRand(booking.outstanding)}`}>
        Any credit you have at this club is used first. The rest is paid by card on PayFast.
      </Banner>
      {error && <Banner status="cancelled" title={error} />}
      <button type="button" className="la-btn la-btn--primary la-btn--block" disabled={busy} onClick={() => void pay()}>
        {`Pay ${formatRand(booking.outstanding)}`}
      </button>
    </section>
  );
}

function Changes({ booking: b, onChanged }: { booking: Booking; onChanged: (booking: Booking) => void }) {
  const [outcome, reload] = useLoad(
    () => api.GET("/api/v1/me/bookings/{id}/outcome/", { params: { path: { id: b.id } } }),
    `booking-outcome-${b.id}-${b.status}-${b.starts_at}`,
  );
  const [moving, setMoving] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<FormErrors | null>(null);
  const path = { id: b.id };

  async function change(call: () => Promise<{ data?: Booking; error?: unknown; response: Response }>) {
    setBusy(true);
    setErrors(null);
    let saved: Booking | undefined;
    const failed = await send(async () => {
      const answer = await call();
      saved = answer.data;
      return answer;
    });
    setBusy(false);
    if (failed || !saved) return setErrors(failed);
    setMoving(false);
    setCancelling(false);
    onChanged(saved);
  }

  const reschedule = (slot: Slot) =>
    void change(() => api.POST("/api/v1/me/bookings/{id}/reschedule/", { params: { path }, body: slot }));
  const cancel = () => void change(() => api.POST("/api/v1/me/bookings/{id}/cancel/", { params: { path } }));

  return (
    <LoadState result={outcome} retry={reload} what="cancellation policy" forbidden={NOT_YOURS}>
      {(now) => (
        <>
          {errors?.general && !moving && <Banner status="cancelled" title={errors.general} />}

          {moving && (
            <section className="la-stack" aria-labelledby="reschedule">
              <h2 id="reschedule" className="headline">
                Reschedule
              </h2>
              <p className="caption la-muted">
                {`${now.reschedule.summary} The club approves the new time before your Barcode works again.`}
              </p>
              <SlotPicker
                clubId={b.club.id}
                bookingId={b.id}
                initial={{ field: b.field.id, date: localDate(b.starts_at), hours: b.hours }}
                submitLabel="Move my booking"
                busy={busy}
                errors={errors}
                onSubmit={reschedule}
              />
              <button type="button" className="la-btn la-btn--quiet" onClick={() => setMoving(false)}>
                Keep the time I have
              </button>
            </section>
          )}

          {cancelling && (
            <div className="la-card la-stack-2" role="group" aria-label="Cancel booking">
              <p className="title-2">Cancel this booking?</p>
              <p className="body">{`${b.field.name}, ${formatMoment(b.starts_at)} to ${formatTime(b.ends_at)}.`}</p>
              <p className="body-strong">{now.cancel.summary}</p>
              <button type="button" className="la-btn la-btn--danger la-btn--block" disabled={busy} onClick={cancel}>
                Yes, cancel it
              </button>
              <button
                type="button"
                className="la-btn la-btn--secondary la-btn--block"
                onClick={() => setCancelling(false)}
              >
                Keep booking
              </button>
            </div>
          )}

          {!moving && !cancelling && (
            <>
              <div className="la-actions">
                {b.can_reschedule && (
                  <button type="button" className="la-btn la-btn--secondary" onClick={() => setMoving(true)}>
                    Reschedule
                  </button>
                )}
                {b.can_cancel && (
                  <button type="button" className="la-btn la-btn--danger" onClick={() => setCancelling(true)}>
                    Cancel booking
                  </button>
                )}
              </div>
              {!b.can_reschedule && <p className="caption la-muted">{now.reschedule.summary}</p>}
            </>
          )}

          <section className="la-stack-2" aria-labelledby="policy">
            <h2 id="policy" className="headline">
              If plans change
            </h2>
            {Number(now.credit) > 0 && (
              <p className="caption la-muted">{`Your credit at ${b.club.name}: ${formatRand(now.credit)}.`}</p>
            )}
            <PolicyList rows={now.rows} current={now.cancel.window} />
          </section>
        </>
      )}
    </LoadState>
  );
}

function EntryBarcode({ booking }: { booking: Booking }) {
  const [current, reload] = useLoad(
    () => api.GET("/api/v1/me/bookings/{id}/barcode/", { params: { path: { id: booking.id } } }),
    `booking-barcode-${booking.id}`,
  );
  return (
    <LoadState result={current} retry={reload} what="Barcode" forbidden={NOT_YOURS}>
      {(data) =>
        data.barcode ? (
          <div className="la-stack">
            <PaymentTicket
              kicker={whenLine(booking)}
              team={`${booking.field.name} · ${booking.hours} h`}
              status={data.state === "valid" ? "Paid · valid for this booking only" : "Accepted · not paid yet"}
              code={data.barcode.code}
              displayCode={data.barcode.display_code}
            />
            {data.state === "valid" ? (
              <p className="caption la-muted">Show this at the gate. It works once, for this booking only.</p>
            ) : (
              <Banner status="pending" title="Not valid at the gate yet">
                {data.reason}
              </Banner>
            )}
          </div>
        ) : (
          <Banner status="cancelled" title="No entry Barcode">
            {data.reason}
          </Banner>
        )
      }
    </LoadState>
  );
}
