// The club's bookings (design/src/ds/Screens.md, Admin 3, the Bookings tab): field bookings
// waiting for an answer, or all of them, each with Accept and Decline (FR-29). Accepting
// sends the Booking User their Barcode (FR-30). An Admin records cash paid for a booking
// (FR-44) and cancels one for the club, which returns the club's percent as credit (the
// policy). What may be done, and every amount, is the API's call.

import { useState } from "react";
import { api } from "../../api/client";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { TextField } from "../../components/TextField";
import { formatRand } from "../../format";
import { LoadState, send, useClub, useLoad } from "../club/shared";
import { NOT_AN_ADMIN } from "../fixtures/ClubFixturesPage";
import { ScreenHeader } from "../teams/shared";
import { BookingStatus, type ClubBooking, hoursLabel, priceLine, whenLine } from "./shared";

type Filter = "pending" | "all";
type Acting = { id: number; kind: "decline" | "cancel" | "cash" };

export function ClubBookingsPage() {
  const { clubId, clubName } = useClub();
  const [filter, setFilter] = useState<Filter>("pending");
  const [bookings, reload] = useLoad(
    () =>
      api.GET("/api/v1/clubs/{club_id}/bookings/", {
        params: { path: { club_id: clubId }, query: filter === "pending" ? { status: "pending" } : {} },
      }),
    `club-bookings-${clubId}-${filter}`,
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [acting, setActing] = useState<Acting | null>(null);
  const [reason, setReason] = useState("");
  const [amount, setAmount] = useState("");

  function start(booking: ClubBooking, kind: Acting["kind"]) {
    setActing({ id: booking.id, kind });
    setReason("");
    setAmount(kind === "cash" ? booking.outstanding : "");
  }

  async function act(booking: ClubBooking, action: "accept" | Acting["kind"]) {
    setBusy(true);
    const path = { club_id: clubId, id: booking.id };
    const failed = await send(() => {
      switch (action) {
        case "accept":
          return api.POST("/api/v1/clubs/{club_id}/bookings/{id}/accept/", { params: { path } });
        case "decline":
          return api.POST("/api/v1/clubs/{club_id}/bookings/{id}/decline/", { params: { path }, body: { reason } });
        case "cancel":
          return api.POST("/api/v1/clubs/{club_id}/bookings/{id}/cancel/", { params: { path }, body: { reason } });
        case "cash":
          return api.POST("/api/v1/clubs/{club_id}/bookings/{id}/cash/", {
            params: { path },
            body: { amount: amount.trim(), reason: "" },
          });
      }
    });
    setBusy(false);
    setError(failed ? (failed.general ?? Object.values(failed.fields)[0] ?? "That didn't work.") : null);
    if (!failed) {
      setActing(null);
      setReason("");
      setAmount("");
      reload();
    }
  }

  return (
    <main className="la-screen">
      <ScreenHeader title="Bookings" back={{ label: "Club home", to: `/clubs/${clubId}` }} caption={clubName} />
      <div className="la-choices">
        <ChoiceChip pressed={filter === "pending"} onToggle={() => setFilter("pending")}>
          Waiting
        </ChoiceChip>
        <ChoiceChip pressed={filter === "all"} onToggle={() => setFilter("all")}>
          All
        </ChoiceChip>
      </div>
      {error && <Banner status="cancelled" title={error} />}
      <LoadState result={bookings} retry={reload} what="bookings" forbidden={NOT_AN_ADMIN}>
        {(list) =>
          list.length === 0 ? (
            <p className="caption la-muted">
              {filter === "pending" ? "No booking is waiting for an answer." : "No bookings yet."}
            </p>
          ) : (
            <ul className="la-group" aria-label="Bookings">
              {list.map((b) => (
                <li key={b.id} className="la-item" id={`booking-${b.id}`}>
                  <span className="la-item__body">
                    <span className="body-strong">{`${b.user.name} · ${b.field.name}`}</span>
                    <span className="caption">{`${whenLine(b)} · ${hoursLabel(b.hours)}`}</span>
                    <span className="caption la-muted">
                      {`${priceLine(b)} = ${formatRand(b.price)} · ${[b.user.phone, b.user.email].filter(Boolean).join(" · ")}`}
                    </span>
                    {b.status === "accepted" && (
                      <span className="caption">
                        {Number(b.outstanding) > 0
                          ? `Paid ${formatRand(b.paid)} · still to pay ${formatRand(b.outstanding)}`
                          : `Paid ${formatRand(b.paid)}`}
                      </span>
                    )}
                    {b.decline_reason && <span className="caption la-muted">{b.decline_reason}</span>}
                    {b.cancelled_by_club && <span className="caption la-muted">Cancelled by the club</span>}
                    {acting?.id !== b.id && (b.can_decide || b.can_record_cash || b.can_club_cancel) && (
                      <span className="la-actions">
                        {b.can_decide && (
                          <>
                            <button
                              type="button"
                              className="la-btn la-btn--primary la-btn--sm"
                              disabled={busy}
                              onClick={() => void act(b, "accept")}
                            >
                              Accept
                            </button>
                            <button
                              type="button"
                              className="la-btn la-btn--quiet la-btn--sm"
                              disabled={busy}
                              onClick={() => start(b, "decline")}
                            >
                              Decline
                            </button>
                          </>
                        )}
                        {b.can_record_cash && (
                          <button
                            type="button"
                            className="la-btn la-btn--secondary la-btn--sm"
                            disabled={busy}
                            onClick={() => start(b, "cash")}
                          >
                            Record cash
                          </button>
                        )}
                        {b.can_club_cancel && !b.can_decide && (
                          <button
                            type="button"
                            className="la-btn la-btn--quiet la-btn--sm"
                            disabled={busy}
                            onClick={() => start(b, "cancel")}
                          >
                            Cancel for the club
                          </button>
                        )}
                      </span>
                    )}
                    {acting?.id === b.id && acting.kind === "cash" && (
                      <span className="la-stack-2">
                        <TextField
                          label="Cash received (R)"
                          value={amount}
                          inputMode="decimal"
                          onChange={(event) => setAmount(event.target.value)}
                          help={`Up to ${formatRand(b.outstanding)}.`}
                        />
                        <span className="la-actions">
                          <button
                            type="button"
                            className="la-btn la-btn--primary la-btn--sm"
                            disabled={busy}
                            onClick={() => void act(b, "cash")}
                          >
                            Record cash
                          </button>
                          <button type="button" className="la-btn la-btn--quiet la-btn--sm" onClick={() => setActing(null)}>
                            Back
                          </button>
                        </span>
                      </span>
                    )}
                    {acting?.id === b.id && acting.kind === "cancel" && (
                      <span className="la-stack-2">
                        <span className="body-strong">{b.club_cancel_summary}</span>
                        <TextField
                          label="Why the club cancels"
                          value={reason}
                          maxLength={300}
                          onChange={(event) => setReason(event.target.value)}
                          help={`Told to ${b.user.name}.`}
                        />
                        <span className="la-actions">
                          <button
                            type="button"
                            className="la-btn la-btn--danger la-btn--sm"
                            disabled={busy || reason.trim() === ""}
                            onClick={() => void act(b, "cancel")}
                          >
                            Cancel booking
                          </button>
                          <button type="button" className="la-btn la-btn--quiet la-btn--sm" onClick={() => setActing(null)}>
                            Keep it
                          </button>
                        </span>
                      </span>
                    )}
                    {b.can_decide && acting?.id === b.id && acting.kind === "decline" && (
                      <span className="la-stack-2">
                        <TextField
                          label="Reason (optional)"
                          value={reason}
                          maxLength={300}
                          onChange={(event) => setReason(event.target.value)}
                          help={`Told to ${b.user.name}.`}
                        />
                        <span className="la-actions">
                          <button
                            type="button"
                            className="la-btn la-btn--danger la-btn--sm"
                            disabled={busy}
                            onClick={() => void act(b, "decline")}
                          >
                            Decline booking
                          </button>
                          <button
                            type="button"
                            className="la-btn la-btn--quiet la-btn--sm"
                            onClick={() => setActing(null)}
                          >
                            Keep it waiting
                          </button>
                        </span>
                      </span>
                    )}
                  </span>
                  <BookingStatus booking={b} />
                </li>
              ))}
            </ul>
          )
        }
      </LoadState>
    </main>
  );
}
