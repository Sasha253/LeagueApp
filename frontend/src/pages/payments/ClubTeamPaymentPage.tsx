// One Team's payments as its club's Admin sees them (PRD FR-21, FR-22; Screens.md Admin 5
// "Mark cash paid"): the Team total against what is due, who has paid, and recording cash
// paid to the club, for one Player or the whole Team. The backend decides what may be
// recorded (no more than the Team owes) and its answer is shown.

import { useState, type FormEvent } from "react";
import { useParams } from "react-router";
import { api } from "../../api/client";
import type { FormErrors } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { TextField } from "../../components/TextField";
import { formatRand } from "../../format";
import { LoadState, NO_ERRORS, send, useClub, useLoad } from "../club/shared";
import { NOT_AN_ADMIN } from "../teams/ClubTeamsPage";
import { ScreenHeader } from "../teams/shared";
import { AMOUNT_HELP, isAmount, PaymentProgress, type TeamPaymentSummary } from "./shared";

export function ClubTeamPaymentPage() {
  const { clubId, clubName } = useClub();
  const teamId = Number(useParams().teamId);
  const [summary, reload] = useLoad(
    () => api.GET("/api/v1/teams/{team_id}/payments/summary/", { params: { path: { team_id: teamId } } }),
    `club-team-payment-${teamId}`,
  );
  const back = { label: "Payments", to: `/clubs/${clubId}/payments` };
  return (
    <main className="la-screen">
      <LoadState result={summary} retry={reload} what="payments" forbidden={NOT_AN_ADMIN}>
        {(data) => (
          <>
            <ScreenHeader title={data.team.name} back={back} caption={clubName} />
            <PaymentProgress summary={data} />
            <CashForm summary={data} onRecorded={reload} />
          </>
        )}
      </LoadState>
    </main>
  );
}

function CashForm({ summary, onRecorded }: { summary: TeamPaymentSummary; onRecorded: () => void }) {
  const [amount, setAmount] = useState("");
  const [payer, setPayer] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const players = summary.players.filter((player) => player.in_team);

  if (Number(summary.outstanding) <= 0) {
    return (
      <>
        {done && <Banner status="confirmed" title={done} />}
        <p className="caption la-muted">{summary.team.name} owes nothing, so there is no cash to record.</p>
      </>
    );
  }

  async function record(event: FormEvent) {
    event.preventDefault();
    setDone(null);
    if (!isAmount(amount)) {
      setErrors({ fields: { amount: AMOUNT_HELP }, general: null });
      return;
    }
    setBusy(true);
    const failed = await send(() =>
      api.POST("/api/v1/teams/{team_id}/cash-payments/", {
        params: { path: { team_id: summary.team.id } },
        body: { amount: amount.trim(), player_id: payer, reason: reason.trim() },
      }),
    );
    setBusy(false);
    setErrors(failed ?? NO_ERRORS);
    if (!failed) {
      const who = players.find((player) => player.player_id === payer)?.name ?? summary.team.name;
      setDone(`${formatRand(amount.trim())} cash recorded for ${who}.`);
      setAmount("");
      setReason("");
      setPayer(null);
      onRecorded();
    }
  }

  return (
    <form className="la-stack" aria-labelledby="cash" onSubmit={(event) => void record(event)} noValidate>
      <h2 id="cash" className="la-overline">
        Record cash
      </h2>
      <TextField
        label="Cash received (R)"
        inputMode="decimal"
        autoComplete="off"
        value={amount}
        onChange={(event) => setAmount(event.target.value)}
        error={errors.fields.amount}
        help={`Up to ${formatRand(summary.outstanding)}, what the Team still owes.`}
      />
      <fieldset className="la-fieldset la-stack-2">
        <legend className="la-overline">Paid by</legend>
        <div className="la-choices">
          <ChoiceChip pressed={payer === null} onToggle={() => setPayer(null)}>
            The whole Team
          </ChoiceChip>
          {players.map((player) => (
            <ChoiceChip key={player.player_id} pressed={payer === player.player_id} onToggle={() => setPayer(player.player_id)}>
              {player.name}
            </ChoiceChip>
          ))}
        </div>
        {errors.fields.player_id && <span className="la-field__error">{errors.fields.player_id}</span>}
      </fieldset>
      <TextField
        label="Note (optional)"
        value={reason}
        maxLength={300}
        onChange={(event) => setReason(event.target.value)}
        error={errors.fields.reason}
        help="Shown on the Team's account, for example who handed it over."
      />
      {errors.general && <Banner status="cancelled" title={errors.general} />}
      {done && <Banner status="confirmed" title={done} />}
      <button type="submit" className="la-btn la-btn--primary la-btn--block" disabled={busy}>
        {isAmount(amount) ? `Record ${formatRand(amount.trim())} cash` : "Record cash"}
      </button>
    </form>
  );
}
