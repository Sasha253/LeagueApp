// What the booking screens share (design/src/screens/f15-booking.mjs): how a Booking is
// labelled, and the slot picker: day, hours, field and start time. Which times are free and
// what they cost come from the API (FR-28, FR-33); this only shows them.

import { useState } from "react";
import { api, type Schemas } from "../../api/client";
import type { FormErrors } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { Icon } from "../../components/Icon";
import { StatusChip, type Status } from "../../components/StatusChip";
import { formatDate, formatMoment, formatRand, formatTime, localDate } from "../../format";
import { LoadState, useLoad } from "../club/shared";

export type Booking = Schemas["Booking"];
export type ClubBooking = Schemas["ClubBooking"];
export type Slot = { field: number; starts_at: string; hours: number };

const STATUS: Record<Booking["status"], { status: Status; label: string }> = {
  pending: { status: "pending", label: "Waiting for the club" },
  accepted: { status: "confirmed", label: "Accepted" },
  declined: { status: "cancelled", label: "Declined" },
  cancelled: { status: "cancelled", label: "Cancelled" },
};

export function BookingStatus({ booking }: { booking: Pick<Booking, "status" | "is_over"> }) {
  if (booking.status === "pending" && booking.is_over) return <StatusChip status="info">Not answered</StatusChip>;
  const { status, label } = STATUS[booking.status];
  return <StatusChip status={status}>{label}</StatusChip>;
}

export function hoursLabel(hours: number): string {
  return hours === 1 ? "1 hour" : `${hours} hours`;
}

/** "Tue 27 Oct · 18:00 to 20:00" */
export function whenLine(booking: Pick<Booking, "starts_at" | "ends_at">): string {
  return `${formatMoment(booking.starts_at)} to ${formatTime(booking.ends_at)}`;
}

/** "R 600 × 2 h" */
export function priceLine(booking: Pick<Booking, "hourly_fee" | "hours">): string {
  return `${formatRand(booking.hourly_fee)} × ${booking.hours} h`;
}

/** A South African date plus `days`: ("2026-10-27", 1) → "2026-10-28". */
function addDays(isoDate: string, days: number): string {
  const [year, month, day] = isoDate.split("-").map(Number) as [number, number, number];
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10);
}

const DAYS_SHOWN = 14;

type PickerProps = {
  clubId: number;
  /** The Booking being rescheduled: its own time counts as free. */
  bookingId?: number;
  initial?: { field: number; date: string; hours: number };
  submitLabel: string;
  busy: boolean;
  errors: FormErrors | null;
  onSubmit: (slot: Slot) => void;
};

/** Day, hours, field and start time, from the API's free times. */
export function SlotPicker({ clubId, bookingId, initial, submitLabel, busy, errors, onSubmit }: PickerProps) {
  const today = localDate(new Date().toISOString());
  const days = Array.from({ length: DAYS_SHOWN }, (_, n) => addDays(today, n));
  const [date, setDate] = useState(initial?.date && initial.date >= today ? initial.date : today);
  const [hours, setHours] = useState(initial?.hours ?? 1);
  const [fieldId, setFieldId] = useState<number | null>(initial?.field ?? null);
  const [start, setStart] = useState<string | null>(null);
  const [free, retry] = useLoad(
    () =>
      api.GET("/api/v1/bookings/availability/", {
        params: { query: { club: clubId, date, hours, ...(bookingId ? { booking: bookingId } : {}) } },
      }),
    `availability-${clubId}-${date}-${hours}-${bookingId ?? ""}`,
  );

  const pickDate = (next: string) => {
    setDate(next);
    setStart(null);
  };
  const pickHours = (next: number) => {
    setHours(next);
    setStart(null);
  };

  return (
    <div className="la-stack">
      <section className="la-stack-2" aria-labelledby="pick-day">
        <h2 id="pick-day" className="la-overline">
          Which day?
        </h2>
        <div className="la-days">
          {days.map((day) => {
            const [weekday = "", number = ""] = formatDate(day).split(" ");
            return (
              <button
                key={day}
                type="button"
                className="la-day"
                aria-pressed={day === date}
                aria-label={formatDate(day)}
                onClick={() => pickDate(day)}
              >
                <span>{weekday}</span>
                <b>{number}</b>
              </button>
            );
          })}
        </div>
      </section>

      <section className="la-stack-2" aria-labelledby="pick-hours">
        <h2 id="pick-hours" className="la-overline">
          How long?
        </h2>
        <div className="la-stepper">
          <button
            type="button"
            className="la-stepper__btn"
            aria-label="Fewer hours"
            disabled={hours <= 1}
            onClick={() => pickHours(hours - 1)}
          >
            <Icon name="minus" />
          </button>
          <div className="la-stepper__val" aria-live="polite">
            {hours}
            <span className="la-stepper__unit">{hours === 1 ? "hour" : "hours"}</span>
          </div>
          <button
            type="button"
            className="la-stepper__btn"
            aria-label="More hours"
            disabled={hours >= 24}
            onClick={() => pickHours(hours + 1)}
          >
            <Icon name="plus" />
          </button>
        </div>
      </section>

      <LoadState result={free} retry={retry} what="free times" forbidden="Only Booking Users can book a field.">
        {(availability) => {
          const field = availability.fields.find((f) => f.field.id === fieldId) ?? null;
          return (
            <>
              <section className="la-stack-2" aria-labelledby="pick-field">
                <h2 id="pick-field" className="la-overline">
                  Which field?
                </h2>
                <ul className="la-group" aria-label="Fields">
                  {availability.fields.map((f) => (
                    <li key={f.field.id}>
                      <button
                        type="button"
                        className="la-item la-item--choice"
                        aria-pressed={f.field.id === fieldId}
                        onClick={() => {
                          setFieldId(f.field.id);
                          setStart(null);
                        }}
                      >
                        <span className="la-item__body">
                          <span className="body-strong">{f.field.name}</span>
                          <span className="caption la-muted">
                            {f.starts.length === 0
                              ? "Nothing free"
                              : f.starts.length === 1
                                ? "1 start time free"
                                : `${f.starts.length} start times free`}
                          </span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>

              {field && (
                <section className="la-stack-2" aria-labelledby="pick-start">
                  <h2 id="pick-start" className="la-overline">
                    Start time
                  </h2>
                  {field.starts.length === 0 ? (
                    <p className="caption la-muted">
                      {field.field.name} isn't free for {hoursLabel(hours)} on {formatDate(date)}.
                    </p>
                  ) : (
                    <div className="la-slots">
                      {field.starts.map((s) => (
                        <ChoiceChip key={s} pressed={s === start} onToggle={() => setStart(s)}>
                          {formatTime(s)}
                        </ChoiceChip>
                      ))}
                    </div>
                  )}
                </section>
              )}

              <div className="la-card la-stack-2">
                <div className="la-kv">
                  <span>{`${formatRand(availability.hourly_fee)} × ${availability.hours} h`}</span>
                  <span>{formatRand(availability.price)}</span>
                </div>
                {field && start && (
                  <p className="caption la-muted">
                    {`${field.field.name} · ${formatDate(date)} · ${formatTime(start)}, ${hoursLabel(hours)}`}
                  </p>
                )}
              </div>

              {errors?.general && <Banner status="cancelled" title={errors.general} />}
              {errors && Object.keys(errors.fields).length > 0 && (
                <Banner status="cancelled" title={Object.values(errors.fields)[0]!} />
              )}

              <button
                type="button"
                className="la-btn la-btn--primary la-btn--block"
                disabled={busy || !field || !start}
                onClick={() => field && start && onSubmit({ field: field.field.id, starts_at: start, hours })}
              >
                {submitLabel}
              </button>
            </>
          );
        }}
      </LoadState>
    </div>
  );
}
