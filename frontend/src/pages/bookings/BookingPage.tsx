// A booking (design/src/ds/Screens.md, Booking User 3; f15-booking.mjs "approved"): its
// status, the entry Barcode once the club accepts it (FR-30), and Reschedule and Cancel
// (FR-31). Whether each can be done, and whether the Barcode counts at the gate, is the
// API's decision. The cancellation policy and its outcome come with booking payments.

import { useState } from "react";
import { useParams } from "react-router";
import { api } from "../../api/client";
import type { FormErrors } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { PaymentTicket } from "../../components/PaymentTicket";
import { formatRand, formatTime, localDate, formatMoment } from "../../format";
import { LoadState, send, useLoad } from "../club/shared";
import { ScreenHeader } from "../teams/shared";
import { BookingStatus, type Booking, hoursLabel, priceLine, SlotPicker, type Slot, whenLine } from "./shared";

const NOT_YOURS = "This booking isn't yours.";

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
    setB(saved);
    setMoving(false);
    setCancelling(false);
  }

  const reschedule = (slot: Slot) =>
    void change(() => api.POST("/api/v1/me/bookings/{id}/reschedule/", { params: { path }, body: slot }));
  const cancel = () => void change(() => api.POST("/api/v1/me/bookings/{id}/cancel/", { params: { path } }));

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
      {b.status === "accepted" && !b.is_over && <EntryBarcode booking={b} />}

      {errors?.general && !moving && <Banner status="cancelled" title={errors.general} />}

      {moving && (
        <section className="la-stack" aria-labelledby="reschedule">
          <h2 id="reschedule" className="headline">
            Reschedule
          </h2>
          <p className="caption la-muted">The club approves the new time before your Barcode works again.</p>
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
          <button type="button" className="la-btn la-btn--danger la-btn--block" disabled={busy} onClick={cancel}>
            Yes, cancel it
          </button>
          <button type="button" className="la-btn la-btn--secondary la-btn--block" onClick={() => setCancelling(false)}>
            Keep booking
          </button>
        </div>
      )}

      {!moving && !cancelling && (b.can_reschedule || b.can_cancel) && (
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
      )}
    </>
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
