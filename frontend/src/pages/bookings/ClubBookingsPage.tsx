// The club's bookings (design/src/ds/Screens.md, Admin 3, the Bookings tab): field bookings
// waiting for an answer, or all of them, each with Accept and Decline (FR-29). Accepting
// sends the Booking User their Barcode (FR-30). What may be decided is the API's call.

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
  const [declining, setDeclining] = useState<number | null>(null);
  const [reason, setReason] = useState("");

  async function decide(booking: ClubBooking, decision: "accept" | "decline") {
    setBusy(true);
    const path = { club_id: clubId, id: booking.id };
    const failed = await send(() =>
      decision === "accept"
        ? api.POST("/api/v1/clubs/{club_id}/bookings/{id}/accept/", { params: { path } })
        : api.POST("/api/v1/clubs/{club_id}/bookings/{id}/decline/", { params: { path }, body: { reason } }),
    );
    setBusy(false);
    setError(failed ? (failed.general ?? Object.values(failed.fields)[0] ?? "That didn't work.") : null);
    if (!failed) {
      setDeclining(null);
      setReason("");
      reload();
    }
  }

  return (
    <main className="la-screen">
      <ScreenHeader title="Bookings" back={{ label: "Profile", to: "/profile" }} caption={clubName} />
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
                    {b.decline_reason && <span className="caption la-muted">{b.decline_reason}</span>}
                    {b.can_decide && declining !== b.id && (
                      <span className="la-actions">
                        <button
                          type="button"
                          className="la-btn la-btn--primary la-btn--sm"
                          disabled={busy}
                          onClick={() => void decide(b, "accept")}
                        >
                          Accept
                        </button>
                        <button
                          type="button"
                          className="la-btn la-btn--quiet la-btn--sm"
                          disabled={busy}
                          onClick={() => {
                            setDeclining(b.id);
                            setReason("");
                          }}
                        >
                          Decline
                        </button>
                      </span>
                    )}
                    {b.can_decide && declining === b.id && (
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
                            onClick={() => void decide(b, "decline")}
                          >
                            Decline booking
                          </button>
                          <button
                            type="button"
                            className="la-btn la-btn--quiet la-btn--sm"
                            onClick={() => setDeclining(null)}
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
