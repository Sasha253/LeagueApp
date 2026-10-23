// Pay my share (design/src/ds/Screens.md, Player 3; PRD FR-19, FR-22, FR-52): how much to
// pay towards your Team, credit used first if you choose, then the card part at PayFast.
// The amount starts at your share from the API; every rule (what is owed, the card
// minimum, how much credit is used) is checked by the backend, and its answer is shown.

import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router";
import { api, type Schemas } from "../../api/client";
import { NO_ERRORS, LoadState, send, useLoad } from "../club/shared";
import type { FormErrors } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { TextField } from "../../components/TextField";
import { formatRand } from "../../format";
import { openCheckout } from "../../native/browser";
import { ScreenHeader } from "../teams/shared";
import { AMOUNT_HELP, amountField, isAmount, PaidChip, type Payment, type PaymentOptions } from "./shared";

type Credit = Schemas["PaymentCreditEnum"];

export function PayPage() {
  const id = Number(useParams().teamId);
  const [options, retry] = useLoad(
    () => api.GET("/api/v1/teams/{team_id}/payments/options/", { params: { path: { team_id: id } } }),
    `payment-options-${id}`,
  );
  return (
    <main className="la-screen">
      <LoadState result={options} retry={retry} what="payment" forbidden="Only Players in this Team can pay towards it.">
        {(data) => <PayForm teamId={id} options={data} />}
      </LoadState>
    </main>
  );
}

function PayForm({ teamId, options }: { teamId: number; options: PaymentOptions }) {
  const navigate = useNavigate();
  const [amount, setAmount] = useState(options.suggested_amount ? amountField(options.suggested_amount) : "");
  const [credit, setCredit] = useState<Credit>("none");
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [busy, setBusy] = useState(false);
  const back = { label: options.team.name, to: `/teams/${teamId}` };

  const hasMyCredit = Number(options.my_credit) > 0;
  const hasTeamCredit = options.team_credit !== null && Number(options.team_credit) > 0;

  if (options.is_paid || options.suggested_amount === null) {
    return (
      <>
        <ScreenHeader title="Pay my share" back={back} caption={options.team.name} />
        <Banner status="confirmed" title={`${options.team.name} has paid`}>
          There's nothing left to pay for this Team.
        </Banner>
      </>
    );
  }

  async function pay(event: FormEvent) {
    event.preventDefault();
    if (!isAmount(amount)) {
      setErrors({ fields: { amount: AMOUNT_HELP }, general: null });
      return;
    }
    setBusy(true);
    let payment: Payment | undefined;
    const failed = await send(async () => {
      const answer = await api.POST("/api/v1/teams/{team_id}/payments/", {
        params: { path: { team_id: teamId } },
        body: { amount: amount.trim(), credit },
      });
      payment = answer.data;
      return answer;
    });
    setErrors(failed ?? NO_ERRORS);
    if (failed || !payment) {
      setBusy(false);
      return;
    }
    const result = `/payments/done?payment=${payment.reference}`;
    if (payment.status === "pending" && payment.checkout) {
      try {
        // In a browser this page leaves for PayFast, which sends the Player back to the
        // result screen itself.
        if (!(await openCheckout(payment.checkout.url))) return;
      } catch {
        // The result screen offers "Pay by card" again.
      }
    }
    navigate(result);
  }

  const card = options.card_enabled;
  return (
    <>
      <ScreenHeader title="Pay my share" back={back} caption={options.team.name} />
      <div className="la-stats">
        <div className="la-stat">
          <span className="la-stat__label">Team fee</span>
          <span className="la-stat__value">{formatRand(options.due)}</span>
        </div>
        <div className="la-stat">
          <span className="la-stat__label">Still to pay</span>
          <span className="la-stat__value la-stat__value--owed">{formatRand(options.outstanding)}</span>
        </div>
      </div>
      <div>
        <PaidChip balance={options} />
      </div>

      {!card && (
        <Banner status="info" title="This club takes cash">
          {hasMyCredit || hasTeamCredit
            ? "Pay with your credit here, or pay cash to an Admin of the club."
            : "Pay cash to an Admin of the club. They record it here."}
        </Banner>
      )}

      {(card || hasMyCredit || hasTeamCredit) && (
        <form className="la-stack" onSubmit={(event) => void pay(event)} noValidate>
          <TextField
            label="Amount (R)"
            inputMode="decimal"
            autoComplete="off"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            error={errors.fields.amount}
            help={
              card && options.minimum_card_amount
                ? `Pay any amount up to ${formatRand(options.outstanding)}. By card, at least ${formatRand(options.minimum_card_amount)}.`
                : `Pay any amount up to ${formatRand(options.outstanding)}.`
            }
          />
          <div className="la-choices">
            <ChoiceChip
              pressed={amount === amountField(options.suggested_amount)}
              onToggle={() => setAmount(amountField(options.suggested_amount!))}
            >
              {`My share ${formatRand(options.suggested_amount)}`}
            </ChoiceChip>
            {options.outstanding !== options.suggested_amount && (
              <ChoiceChip
                pressed={amount === amountField(options.outstanding)}
                onToggle={() => setAmount(amountField(options.outstanding))}
              >
                {`All that's owed ${formatRand(options.outstanding)}`}
              </ChoiceChip>
            )}
          </div>

          {(hasMyCredit || hasTeamCredit) && (
            <fieldset className="la-fieldset la-stack-2">
              <legend className="la-overline">Use credit first</legend>
              <div className="la-choices">
                <ChoiceChip pressed={credit === "none"} onToggle={() => setCredit("none")}>
                  No credit
                </ChoiceChip>
                {hasMyCredit && (
                  <ChoiceChip pressed={credit === "player"} onToggle={() => setCredit("player")}>
                    {`My credit ${formatRand(options.my_credit)}`}
                  </ChoiceChip>
                )}
                {hasTeamCredit && (
                  <ChoiceChip pressed={credit === "team"} onToggle={() => setCredit("team")}>
                    {`Team credit ${formatRand(options.team_credit!)}`}
                  </ChoiceChip>
                )}
              </div>
              <span className="caption la-muted">
                {credit === "none"
                  ? "Your credit stays for another time."
                  : card
                    ? "Credit is used as soon as you pay. Anything it doesn't cover is paid by card."
                    : "Credit is used as soon as you pay. It must cover the whole amount here."}
              </span>
            </fieldset>
          )}

          {errors.fields.credit && <Banner status="cancelled" title={errors.fields.credit} />}
          {errors.general && <Banner status="cancelled" title={errors.general} />}
          <button type="submit" className="la-btn la-btn--primary la-btn--block" disabled={busy}>
            {isAmount(amount) ? `Pay ${formatRand(amount.trim())}` : "Pay"}
          </button>
          {card && (
            <p className="caption la-muted">
              You pay by card on PayFast's secure page; your card details never reach League App. Cash to an Admin of
              the club is also accepted.
            </p>
          )}
        </form>
      )}
    </>
  );
}
