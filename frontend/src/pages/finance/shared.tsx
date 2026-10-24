// What the Finances screens share (PRD FR-25 to FR-27, FR-49; Screens.md Admin 5 and 6).
// Every figure comes from the API (finance tracker, chunk 25); these screens only draw it.

import type { Schemas } from "../../api/client";
import { formatRand, localDate } from "../../format";

export type SeasonSummary = Schemas["SeasonSummary"];
export type IncomeLine = Schemas["IncomeLine"];
export type LedgerEntry = Schemas["LedgerEntry"];
export type TeamLedger = Schemas["TeamLedger"];
export type SeasonIncome = Schemas["SeasonIncome"];
type Season = Schemas["Season"];

export const NOT_AN_ADMIN = "Only this club's Admins can see its finances.";

/** The Season the Finances screen opens on: the earliest one that hasn't ended (the one
 * running now), else the latest. Only which filter is picked first; figures are the API's. */
export function openingSeason(seasons: Season[], today = localDate(new Date().toISOString())): number | null {
  const running = seasons
    .filter((season) => season.ends_on >= today)
    .sort((a, b) => a.starts_on.localeCompare(b.starts_on));
  if (running[0]) return running[0].id;
  const latest = [...seasons].sort((a, b) => b.starts_on.localeCompare(a.starts_on));
  return latest[0]?.id ?? null;
}

/** "Card R 15,960 · Cash R 2,450 · Credit R 700": how a line's money came in. */
export function bySource(line: IncomeLine): string {
  const parts = [`Card ${formatRand(line.card)}`, `Cash ${formatRand(line.cash)}`];
  if (Number(line.credit_spent) !== 0) parts.push(`Credit used ${formatRand(line.credit_spent)}`);
  if (Number(line.returned_as_credit) !== 0) parts.push(`Returned as credit ${formatRand(line.returned_as_credit)}`);
  return parts.join(" · ");
}

/** One total in a `la-stats` grid. `owed` colours what is still owed (pending ink). */
export function Stat({ label, amount, owed = false }: { label: string; amount: string; owed?: boolean }) {
  return (
    <div className="la-stat">
      <span className="la-stat__label">{label}</span>
      <span className={`la-stat__value${owed && Number(amount) > 0 ? " la-stat__value--owed" : ""}`}>
        {formatRand(amount)}
      </span>
    </div>
  );
}

const METHODS: Record<string, string> = { card: "Card", cash: "Cash", credit: "Credit" };

/** How a payment or refund was made: Card, Cash or Credit. A word, not a status, so no icon. */
export function MethodChip({ method }: { method: string }) {
  const label = METHODS[method];
  if (!label) return null;
  return (
    <span className="la-chip la-chip--info">
      <span className="sr-only">Method: </span>
      {label}
    </span>
  );
}

const KINDS: Record<LedgerEntry["kind"], string> = {
  charge: "Fee charged",
  payment: "Payment",
  credit: "Credit given",
  refund: "Refund",
  reversal: "Correction",
};

/** "Payment · Sipho Dlamini", "Correction of entry 12". */
export function entryTitle(entry: LedgerEntry): string {
  if (entry.kind === "reversal" && entry.reverses_id !== null) return `Correction of entry ${entry.reverses_id}`;
  return entry.player ? `${KINDS[entry.kind]} · ${entry.player.name}` : KINDS[entry.kind];
}

/** One income line: what was received, and by card, cash and credit. */
export function IncomeRow({ title, line }: { title: string; line: IncomeLine }) {
  return (
    <li className="la-item">
      <span className="la-item__body">
        <span className="body-strong">{title}</span>
        <span className="caption la-muted">{bySource(line)}</span>
      </span>
      <span className="body-strong">{formatRand(line.received)}</span>
    </li>
  );
}
