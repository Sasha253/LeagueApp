// What the payment screens share: PaymentProgress from the design system (README,
// Components; design/src/ui.mjs `payProgress`), the payment status chip, and what a Payment
// and a Team's payments look like. Every amount comes from the API; this file only draws.

import type { Schemas } from "../../api/client";
import { StatusChip, type Status } from "../../components/StatusChip";
import { formatRand } from "../../format";

export type Payment = Schemas["Payment"];
export type PaymentOptions = Schemas["PaymentOptions"];
export type TeamPaymentSummary = Schemas["TeamPaymentSummary"];
export type TeamPaymentStatus = Schemas["TeamPaymentStatus"];

const PAYMENT_STATUS: Record<Payment["status"], { status: Status; label: string }> = {
  pending: { status: "pending", label: "Waiting" },
  complete: { status: "confirmed", label: "Paid" },
  failed: { status: "cancelled", label: "Failed" },
  cancelled: { status: "cancelled", label: "Cancelled" },
};

export function PaymentStatus({ payment }: { payment: Pick<Payment, "status"> }) {
  const { status, label } = PAYMENT_STATUS[payment.status];
  return <StatusChip status={status}>{label}</StatusChip>;
}

/** "Paid", or what is still owed: "R 200 to go". */
export function PaidChip({ balance }: { balance: { is_paid: boolean; outstanding: string } }) {
  if (balance.is_paid) return <StatusChip status="confirmed">Paid</StatusChip>;
  return <StatusChip status="pending">{`${formatRand(balance.outstanding)} to go`}</StatusChip>;
}

/** How far along the bar is. Drawing only: the amounts themselves come from the API. */
function share(paid: string, due: string): number {
  const total = Number(due);
  if (!(total > 0)) return Number(paid) > 0 ? 100 : 0;
  return Math.max(0, Math.min(100, (Number(paid) / total) * 100));
}

/** PaymentProgress: a Team's payments against the amount due, with who has paid (FR-21). */
export function PaymentProgress({
  summary,
  title = "Payments",
}: {
  summary: Pick<TeamPaymentSummary, "due" | "paid" | "outstanding" | "is_paid"> &
    Partial<Pick<TeamPaymentSummary, "players" | "paid_for_team">>;
  title?: string;
}) {
  const { due, paid, is_paid: done } = summary;
  const label = `${formatRand(paid)} of ${formatRand(due)} paid`;
  const players = summary.players ?? [];
  const forTeam = summary.paid_for_team;
  const showForTeam = forTeam !== undefined && Number(forTeam) !== 0;
  return (
    <section className="la-card la-progress" aria-label={title}>
      <div className="la-row">
        <span className="la-progress__label">
          <b>{formatRand(paid)}</b> of {formatRand(due)}
        </span>
        <PaidChip balance={summary} />
      </div>
      <div className="la-progress__track" role="img" aria-label={label}>
        <div
          className={`la-progress__fill${done ? " la-progress__fill--done" : ""}`}
          style={{ width: `${share(paid, due)}%` }}
        />
      </div>
      {(players.length > 0 || showForTeam) && (
        <>
          <hr className="la-divider" />
          <ul className="la-stack-2" aria-label="Who has paid">
            {players.map((player) => (
              <li key={player.player_id} className="la-row body">
                <span>
                  {player.name}
                  {player.is_captain && <span className="la-progress__hint"> Captain</span>}
                  {!player.in_team && <span className="la-progress__hint"> Left the Team</span>}
                </span>
                {player.has_paid ? (
                  <StatusChip status="confirmed">{formatRand(player.paid)}</StatusChip>
                ) : (
                  <StatusChip status="pending">Unpaid</StatusChip>
                )}
              </li>
            ))}
            {showForTeam && (
              <li className="la-row body">
                <span>For the whole Team</span>
                <StatusChip status="confirmed">{formatRand(forTeam)}</StatusChip>
              </li>
            )}
          </ul>
        </>
      )}
    </section>
  );
}

/** An amount as typed: rand, up to two decimals ("70", "70.50"). Format only: whether it
 * may be paid is the backend's to decide. */
export function isAmount(value: string): boolean {
  return /^\d+(\.\d{1,2})?$/.test(value.trim()) && Number(value) > 0;
}

export const AMOUNT_HELP = "Enter an amount in rand, like 70 or 70.50.";

/** "70.00" → "70", "70.50" → "70.50": an API amount as the amount field shows it. */
export function amountField(amount: string): string {
  return amount.endsWith(".00") ? amount.slice(0, -3) : amount;
}
