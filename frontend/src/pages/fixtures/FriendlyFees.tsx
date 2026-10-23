// A friendly's fee for the club's Admin (PRD FR-24, FR-49): the fee for the match, who pays
// it (the borrowed Players, the Team's Players or the club/manager) and the Captain who
// receives the friendly's Payment Barcode; what has been paid, and recording cash from a
// payer. Every amount, who may pay and what may still change is the API's decision: the
// screen shows it and the backend refuses anything else (409 with the reason).

import { useState, type FormEvent } from "react";
import { api, type Schemas } from "../../api/client";
import type { FormErrors } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { StatusChip, type Status } from "../../components/StatusChip";
import { TextField } from "../../components/TextField";
import { formatMoment, formatRand } from "../../format";
import { NO_ERRORS, send, useLoad } from "../club/shared";
import { AMOUNT_HELP, isAmount } from "../payments/shared";

type Friendly = Schemas["Friendly"];
type Payer = Schemas["FriendlyPayerEnum"];

export const PAYER_LABELS: Record<Payer, string> = {
  borrowed_players: "The borrowed Players",
  team_players: "The Team's Players",
  club: "The club/manager",
};

const BARCODE_CHIP: Partial<Record<Friendly["barcode"]["state"], { status: Status; label: string }>> = {
  valid: { status: "confirmed", label: "Barcode issued" },
  unpaid: { status: "pending", label: "Not paid" },
  no_captain: { status: "pending", label: "No Captain" },
  revoked: { status: "cancelled", label: "Revoked" },
  expired: { status: "info", label: "No longer valid" },
};

const FEE = /^\d+(\.\d{1,2})?$/;

/** "R 100 of R 150 paid", or why nothing is collected. */
function paidLine(f: Friendly): string {
  if (!f.terms) return "No fee set yet.";
  if (f.terms.payer === "club") return "Paid by the club/manager: nothing is collected from Players.";
  if (Number(f.terms.fee) === 0) return "Free: nothing is collected.";
  return `${formatRand(f.paid)} of ${formatRand(f.due)} paid · ${formatRand(f.outstanding)} to pay`;
}

export function FriendlyFeeSection({ clubId, fixtureId }: { clubId: number; fixtureId: number }) {
  const [version, setVersion] = useState(0);
  const [loaded, reload] = useLoad(
    () =>
      api.GET("/api/v1/clubs/{club_id}/fixtures/{id}/friendly/", {
        params: { path: { club_id: clubId, id: fixtureId } },
      }),
    `friendly-${clubId}-${fixtureId}-${version}`,
  );
  const changed = () => setVersion((n) => n + 1);

  if (loaded.state === "loading") return <p className="caption la-muted">Loading the friendly's fee…</p>;
  if (loaded.state !== "ok") {
    return (
      <Banner status="cancelled" title="The friendly's fee couldn't be loaded.">
        <button type="button" className="la-btn la-btn--quiet la-btn--sm" onClick={reload}>
          Try again
        </button>
      </Banner>
    );
  }
  const friendly = loaded.data;
  const chip = BARCODE_CHIP[friendly.barcode.state];

  return (
    <section className="la-stack-2" aria-labelledby="friendly-fee">
      <h2 id="friendly-fee" className="la-overline">
        Friendly fee
      </h2>
      <ul className="la-group" aria-label="Friendly fee">
        <li className="la-item">
          <span className="la-item__body">
            <span className="body-strong">
              {friendly.terms ? `${formatRand(friendly.terms.fee)} · ${PAYER_LABELS[friendly.terms.payer]}` : "Not set"}
            </span>
            <span className="caption la-muted">{paidLine(friendly)}</span>
            {friendly.terms && (
              <span className="caption la-muted">
                Captain: {friendly.terms.captain?.name ?? "none yet"} · set {formatMoment(friendly.terms.set_at)} by{" "}
                {friendly.terms.set_by.name}
              </span>
            )}
          </span>
          {friendly.terms && friendly.settled && <StatusChip status="confirmed">Paid</StatusChip>}
        </li>
        <li className="la-item">
          <span className="la-item__body">
            <span className="body-strong">Payment Barcode</span>
            <span className="caption la-muted">
              {friendly.barcode.state === "valid"
                ? `${friendly.terms?.captain?.name ?? "The Captain"} shows it at the gate.`
                : friendly.barcode.reason}
            </span>
          </span>
          {chip && <StatusChip status={chip.status}>{chip.label}</StatusChip>}
        </li>
      </ul>

      {friendly.can_change && <TermsForm clubId={clubId} fixtureId={fixtureId} friendly={friendly} onSaved={changed} />}

      {friendly.payments.length > 0 && (
        <ul className="la-group" aria-label="Friendly payments">
          {friendly.payments.map((p) => (
            <li key={p.id} className="la-item">
              <span className="la-item__body">
                <span className="body-strong">
                  {p.player.name} · {formatRand(p.amount)}
                </span>
                <span className="caption la-muted">
                  {formatMoment(p.created_at)} · {p.method}
                  {p.recorded_by && ` · recorded by ${p.recorded_by.name}`}
                </span>
              </span>
              {p.kind === "reversal" && <StatusChip status="cancelled">Reversed</StatusChip>}
            </li>
          ))}
        </ul>
      )}

      {friendly.is_on && friendly.payers.length > 0 && Number(friendly.outstanding) > 0 && (
        <FriendlyCashForm clubId={clubId} fixtureId={fixtureId} friendly={friendly} onRecorded={changed} />
      )}
    </section>
  );
}

type FormProps = { clubId: number; fixtureId: number; friendly: Friendly };

function TermsForm({ clubId, fixtureId, friendly, onSaved }: FormProps & { onSaved: () => void }) {
  const [fee, setFee] = useState(friendly.terms?.fee ?? friendly.default_fee ?? "");
  const [payer, setPayer] = useState<Payer | null>(friendly.terms?.payer ?? null);
  const [captain, setCaptain] = useState<number | null>(friendly.terms?.captain?.id ?? null);
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [busy, setBusy] = useState(false);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!FEE.test(fee.trim())) {
      setErrors({ fields: { fee: "Enter the fee in rand, like 150 or 150.50. 0 is free." }, general: null });
      return;
    }
    if (payer === null) {
      setErrors({ fields: { payer: "Choose who pays." }, general: null });
      return;
    }
    setBusy(true);
    const failed = await send(() =>
      api.POST("/api/v1/clubs/{club_id}/fixtures/{id}/friendly/", {
        params: { path: { club_id: clubId, id: fixtureId } },
        body: { fee: fee.trim(), payer, captain },
      }),
    );
    setBusy(false);
    setErrors(failed ?? NO_ERRORS);
    if (!failed) onSaved();
  }

  return (
    <form className="la-stack" aria-label="Set the friendly's fee" onSubmit={(event) => void save(event)} noValidate>
      <TextField
        label="Fee for the match (R)"
        inputMode="decimal"
        autoComplete="off"
        value={fee}
        disabled={friendly.money_fixed}
        onChange={(event) => setFee(event.target.value)}
        error={errors.fields.fee}
        help={
          friendly.money_fixed
            ? "Payments have been recorded, so the fee and who pays are fixed."
            : friendly.default_fee !== null
              ? `The club's friendly fee is ${formatRand(friendly.default_fee)}. 0 is free.`
              : "0 is free."
        }
      />
      <fieldset className="la-fieldset la-stack-2">
        <legend className="la-overline">Who pays</legend>
        <div className="la-choices">
          {friendly.payer_choices.map((choice) => (
            <ChoiceChip
              key={choice}
              pressed={payer === choice}
              onToggle={() => !friendly.money_fixed && setPayer(choice)}
            >
              {PAYER_LABELS[choice]}
            </ChoiceChip>
          ))}
        </div>
        {errors.fields.payer && <span className="la-field__error">{errors.fields.payer}</span>}
      </fieldset>
      <fieldset className="la-fieldset la-stack-2">
        <legend className="la-overline">Captain (receives the Barcode)</legend>
        {friendly.captain_candidates.length === 0 ? (
          <p className="caption la-muted">No one has joined yet. Pick a Captain once Players join.</p>
        ) : (
          <div className="la-choices">
            <ChoiceChip pressed={captain === null} onToggle={() => setCaptain(null)}>
              None yet
            </ChoiceChip>
            {friendly.captain_candidates.map((person) => (
              <ChoiceChip key={person.id} pressed={captain === person.id} onToggle={() => setCaptain(person.id)}>
                {person.name}
              </ChoiceChip>
            ))}
          </div>
        )}
        {errors.fields.captain && <span className="la-field__error">{errors.fields.captain}</span>}
      </fieldset>
      {errors.general && <Banner status="cancelled" title={errors.general} />}
      <button type="submit" className="la-btn la-btn--primary la-btn--block" disabled={busy}>
        Save the friendly's fee
      </button>
    </form>
  );
}

function FriendlyCashForm({ clubId, fixtureId, friendly, onRecorded }: FormProps & { onRecorded: () => void }) {
  const [amount, setAmount] = useState("");
  const [payer, setPayer] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [busy, setBusy] = useState(false);

  async function record(event: FormEvent) {
    event.preventDefault();
    if (!isAmount(amount)) {
      setErrors({ fields: { amount: AMOUNT_HELP }, general: null });
      return;
    }
    if (payer === null) {
      setErrors({ fields: { player: "Choose who paid." }, general: null });
      return;
    }
    setBusy(true);
    const failed = await send(() =>
      api.POST("/api/v1/clubs/{club_id}/fixtures/{id}/friendly/payments/", {
        params: { path: { club_id: clubId, id: fixtureId } },
        body: { player: payer, amount: amount.trim(), reason: reason.trim() },
      }),
    );
    setBusy(false);
    setErrors(failed ?? NO_ERRORS);
    if (!failed) onRecorded();
  }

  return (
    <form className="la-stack" aria-labelledby="friendly-cash" onSubmit={(event) => void record(event)} noValidate>
      <h3 id="friendly-cash" className="la-overline">
        Record cash
      </h3>
      <TextField
        label="Cash received (R)"
        inputMode="decimal"
        autoComplete="off"
        value={amount}
        onChange={(event) => setAmount(event.target.value)}
        error={errors.fields.amount}
        help={`Up to ${formatRand(friendly.outstanding)}, what the friendly still owes.`}
      />
      <fieldset className="la-fieldset la-stack-2">
        <legend className="la-overline">Paid by</legend>
        <div className="la-choices">
          {friendly.payers.map((person) => (
            <ChoiceChip key={person.id} pressed={payer === person.id} onToggle={() => setPayer(person.id)}>
              {person.name}
            </ChoiceChip>
          ))}
        </div>
        {errors.fields.player && <span className="la-field__error">{errors.fields.player}</span>}
      </fieldset>
      <TextField
        label="Note (optional)"
        value={reason}
        maxLength={300}
        onChange={(event) => setReason(event.target.value)}
        error={errors.fields.reason}
      />
      {errors.general && <Banner status="cancelled" title={errors.general} />}
      <button type="submit" className="la-btn la-btn--primary la-btn--block" disabled={busy}>
        {isAmount(amount) ? `Record ${formatRand(amount.trim())} cash` : "Record cash"}
      </button>
    </form>
  );
}
