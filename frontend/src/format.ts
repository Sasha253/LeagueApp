// How the app shows money and dates (CLAUDE.md): "R 18,550", "Tue 27 Oct".

/** A rand amount from the API (a decimal string, never a float): "350.00" → "R 350". */
export function formatRand(amount: string): string {
  const [whole = "0", cents = ""] = amount.split(".");
  const negative = whole.startsWith("-");
  const digits = negative ? whole.slice(1) : whole;
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const tail = /^0*$/.test(cents) ? "" : `.${cents.padEnd(2, "0")}`;
  return `${negative ? "-" : ""}R ${grouped}${tail}`;
}

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** A calendar date from the API ("2026-10-27") → "Tue 27 Oct". No time zone is involved. */
export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number) as [number, number, number];
  const weekday = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
  return `${DAYS[weekday]} ${day} ${MONTHS[month - 1]}`;
}

/** Night weekdays as the API numbers them: 0 is Monday. */
export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
export const WEEKDAYS_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** The South African calendar date of a moment from the API (UTC): "2026-10-26T23:30:00Z" → "2026-10-27". */
export function localDate(isoDateTime: string): string {
  // en-CA writes dates as YYYY-MM-DD.
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Africa/Johannesburg",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(isoDateTime));
}

/** The South African time of a moment from the API, 24-hour: "2026-10-27T17:40:00Z" → "19:40". */
export function formatTime(isoDateTime: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Africa/Johannesburg",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date(isoDateTime));
}

/** A moment from the API as South Africans read it: "Tue 27 Oct · 19:40". */
export function formatMoment(isoDateTime: string): string {
  return `${formatDate(localDate(isoDateTime))} · ${formatTime(isoDateTime)}`;
}

/** The moment of a South African date and 24-hour time, for the API: ("2026-10-27", "19:40")
 * → "2026-10-27T19:40:00+02:00". South Africa has no daylight saving, so it is always +02:00. */
export function southAfricanMoment(isoDate: string, time: string): string {
  return `${isoDate}T${time}:00+02:00`;
}
