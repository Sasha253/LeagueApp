// My bookings (design/src/ds/Screens.md, Booking User 3): coming up and before, each with its
// status; open one for its Barcode, Reschedule and Cancel.

import { Link } from "react-router";
import { api } from "../../api/client";
import { LoadState, useLoad } from "../club/shared";
import { ScreenHeader } from "../teams/shared";
import { BookingStatus, type Booking, whenLine } from "./shared";

function Rows({ list, label }: { list: Booking[]; label: string }) {
  return (
    <ul className="la-group" aria-label={label}>
      {list.map((b) => (
        <li key={b.id}>
          <Link className="la-item la-item--link" to={`/bookings/${b.id}`}>
            <span className="la-item__body">
              <span className="body-strong">{`${b.field.name} · ${b.club.name}`}</span>
              <span className="caption la-muted">{whenLine(b)}</span>
            </span>
            <BookingStatus booking={b} />
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function MyBookingsPage() {
  const [bookings, reload] = useLoad(() => api.GET("/api/v1/me/bookings/"), "my-bookings");

  return (
    <main className="la-screen">
      <ScreenHeader title="My bookings" back={{ label: "Profile", to: "/profile" }} />
      <Link className="la-btn la-btn--primary la-btn--block" to="/book">
        Book a field
      </Link>
      <LoadState result={bookings} retry={reload} what="bookings" forbidden="Sign in to see your bookings.">
        {(list) => {
          const coming = list.filter((b) => !b.is_over);
          const before = list.filter((b) => b.is_over).reverse();
          return (
            <>
              <section className="la-stack-2" aria-labelledby="coming-up">
                <h2 id="coming-up" className="la-overline">
                  Coming up
                </h2>
                {coming.length === 0 ? (
                  <p className="caption la-muted">No bookings coming up.</p>
                ) : (
                  <Rows list={coming} label="Coming up" />
                )}
              </section>
              {before.length > 0 && (
                <section className="la-stack-2" aria-labelledby="before">
                  <h2 id="before" className="la-overline">
                    Before
                  </h2>
                  <Rows list={before} label="Before" />
                </section>
              )}
            </>
          );
        }}
      </LoadState>
    </main>
  );
}
