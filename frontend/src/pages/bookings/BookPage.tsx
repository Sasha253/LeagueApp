// Book a field (design/src/ds/Screens.md, Booking User 1 and 2; f15-booking.mjs): pick the
// club, then day, hours, field and start time from the API's free times, and request it.
// Every club approves each booking (FR-29), so it ends on "Booking requested".

import { useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import type { FormErrors } from "../../api/errors";
import { ChoiceChip } from "../../components/ChoiceChip";
import { Icon } from "../../components/Icon";
import { formatRand } from "../../format";
import { LoadState, send, useLoad } from "../club/shared";
import { ScreenHeader } from "../teams/shared";
import { BookingStatus, type Booking, hoursLabel, priceLine, SlotPicker, type Slot, whenLine } from "./shared";

export const NOT_A_BOOKING_USER = "Turn on “I hire a field” in your Profile to book a field.";

export function BookPage() {
  const [clubs, reload] = useLoad(() => api.GET("/api/v1/bookings/clubs/"), "booking-clubs");
  const [chosen, setChosen] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<FormErrors | null>(null);
  const [requested, setRequested] = useState<Booking | null>(null);

  async function request(clubId: number, slot: Slot) {
    setBusy(true);
    setErrors(null);
    let made: Booking | undefined;
    const failed = await send(async () => {
      const answer = await api.POST("/api/v1/me/bookings/", { body: { club: clubId, ...slot } });
      made = answer.data;
      return answer;
    });
    setBusy(false);
    if (failed || !made) return setErrors(failed);
    setRequested(made);
  }

  if (requested) {
    return (
      <main className="la-screen">
        <ScreenHeader title="Book a field" back={{ label: "My bookings", to: "/bookings" }} />
        <div className="la-hero" role="status">
          <span className="la-disc la-disc--pending la-disc--xl">
            <Icon name="clock" />
          </span>
          <p className="title-1">Booking requested</p>
          <p className="body la-muted">
            The club approves every booking. Your entry Barcode appears in My bookings once it's accepted.
          </p>
        </div>
        <div className="la-card la-stack-2">
          <div className="la-section-head">
            <span className="la-overline">{`${requested.club.name} · ${requested.field.name}`}</span>
            <BookingStatus booking={requested} />
          </div>
          <p className="title-2">{whenLine(requested)}</p>
          <div className="la-kv">
            <span>{priceLine(requested)}</span>
            <span>{formatRand(requested.price)}</span>
          </div>
          <p className="caption la-muted">{hoursLabel(requested.hours)}</p>
        </div>
        <Link className="la-btn la-btn--secondary la-btn--block" to="/bookings">
          View my bookings
        </Link>
      </main>
    );
  }

  return (
    <main className="la-screen">
      <ScreenHeader title="Book a field" back={{ label: "My bookings", to: "/bookings" }} />
      <LoadState result={clubs} retry={reload} what="clubs" forbidden={NOT_A_BOOKING_USER}>
        {(list) => {
          if (list.length === 0) return <p className="caption la-muted">No club is taking bookings yet.</p>;
          const club = list.find((c) => c.id === chosen) ?? (list.length === 1 ? list[0]! : null);
          return (
            <>
              {list.length > 1 && (
                <fieldset className="la-fieldset la-stack-2">
                  <legend className="la-overline">Which club?</legend>
                  <div className="la-choices">
                    {list.map((c) => (
                      <ChoiceChip key={c.id} pressed={club?.id === c.id} onToggle={() => setChosen(c.id)}>
                        {c.name}
                      </ChoiceChip>
                    ))}
                  </div>
                </fieldset>
              )}
              {club && (
                <>
                  <p className="caption la-muted">{`${club.name} · ${formatRand(club.hourly_fee)} an hour`}</p>
                  <SlotPicker
                    key={club.id}
                    clubId={club.id}
                    submitLabel="Request booking"
                    busy={busy}
                    errors={errors}
                    onSubmit={(slot) => void request(club.id, slot)}
                  />
                </>
              )}
            </>
          );
        }}
      </LoadState>
    </main>
  );
}
