// Club settings (design/src/ds/Screens.md, Admin 8, FR-42): the fees, cutoffs, booking
// policy and payment mode. The API checks every value; this screen only shows them.

import { useState } from "react";
import { api, type Schemas } from "../../api/client";
import type { FormErrors } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { TextField } from "../../components/TextField";
import { LoadState, NO_ERRORS, send, SetupHeader, useClub, useLoad } from "./shared";

type Settings = Schemas["ClubSettings"];
type MoneyName = "league_fee" | "friendly_fee" | "booking_hourly_fee";
type WholeName = Exclude<
  keyof Settings,
  MoneyName | "payment_mode" | "payment_provider" | "missing" | "updated_at" | "updated_by_name"
>;

export const SETTING_LABELS: Record<string, string> = {
  league_fee: "League fee per Team",
  friendly_fee: "Friendly fee per match",
  booking_hourly_fee: "Field hire per hour",
};

const MONEY: { name: MoneyName; help: string }[] = [
  { name: "league_fee", help: "For a Season. A Division can set its own." },
  { name: "friendly_fee", help: "The usual fee. You can change it for each friendly." },
  { name: "booking_hourly_fee", help: "A booking costs this times the hours booked." },
];

const WHOLE: { title: string; fields: { name: WholeName; label: string; help?: string }[] }[] = [
  {
    title: "Matches",
    fields: [
      { name: "confirmation_hours_before", label: "Confirmations go out (hours before kick-off)" },
      {
        name: "confirmation_resend_after_hours",
        label: "Resend unanswered Confirmations after (hours)",
        help: "Resent once.",
      },
      {
        name: "readiness_hours_before",
        label: "Reminder and squad check (hours before kick-off)",
        help: "Teams under their Division's minimum are out.",
      },
      { name: "division_min_players", label: "Minimum players for a new Division" },
    ],
  },
  {
    title: "Bookings",
    fields: [
      {
        name: "booking_payment_cutoff_hours",
        label: "Payment taken (hours before kick-off)",
        help: "Cancelling before this is free.",
      },
      { name: "booking_late_cancel_hours", label: "Late cancellation from (hours before kick-off)" },
      { name: "booking_late_cancel_credit_percent", label: "Credit for cancelling before that (%)" },
      { name: "booking_no_show_credit_percent", label: "Credit for a late cancel or no-show (%)" },
      { name: "booking_club_cancel_credit_percent", label: "Credit when the club cancels (%)" },
      { name: "booking_reschedule_window_days", label: "Late reschedule to a slot within (days)" },
      { name: "booking_reschedules_allowed", label: "Late reschedules allowed per booking" },
    ],
  },
];

type Draft = Record<MoneyName | WholeName, string> & { payment_mode: Settings["payment_mode"] };

function draftOf(settings: Settings): Draft {
  const draft = { payment_mode: settings.payment_mode } as Draft;
  for (const { name } of MONEY) draft[name] = settings[name] ?? "";
  for (const group of WHOLE) for (const { name } of group.fields) draft[name] = String(settings[name]);
  return draft;
}

function bodyOf(draft: Draft): Schemas["PatchedClubSettingsRequest"] {
  const body: Schemas["PatchedClubSettingsRequest"] = { payment_mode: draft.payment_mode };
  for (const { name } of MONEY) body[name] = draft[name].trim() || null;
  for (const group of WHOLE) for (const { name } of group.fields) body[name] = Number(draft[name]);
  return body;
}

export function ClubSettingsPage() {
  const { clubId } = useClub();
  const path = { club_id: clubId };
  const [settings, retry] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/settings/", { params: { path } }),
    `settings-${clubId}`,
  );

  return (
    <main className="la-screen">
      <SetupHeader title="Settings" />
      <LoadState result={settings} retry={retry} what="settings">
        {(loaded) => <SettingsForm clubId={clubId} settings={loaded} />}
      </LoadState>
    </main>
  );
}

function SettingsForm({ clubId, settings }: { clubId: number; settings: Settings }) {
  const [saved, setSaved] = useState(settings);
  const [draft, setDraft] = useState(() => draftOf(settings));
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const change = (next: Partial<Draft>) => {
    setDraft({ ...draft, ...next });
    setDone(false);
  };

  async function save() {
    setBusy(true);
    setErrors(NO_ERRORS);
    let answer: Settings | undefined;
    const failed = await send(async () => {
      const result = await api.PATCH("/api/v1/clubs/{club_id}/settings/", {
        params: { path: { club_id: clubId } },
        body: bodyOf(draft),
      });
      answer = result.data;
      return result;
    });
    setBusy(false);
    if (failed) return setErrors(failed);
    if (answer) {
      setSaved(answer);
      setDraft(draftOf(answer));
    }
    setDone(true);
  }

  return (
    <>
      {saved.missing.length > 0 && (
        <Banner status="pending" title="Set your fees">
          Teams and bookings need them. Still to set:{" "}
          {saved.missing.map((name) => SETTING_LABELS[name] ?? name).join(", ")}.
        </Banner>
      )}

      <fieldset className="la-fieldset la-stack">
        <legend className="la-overline">Fees</legend>
        {MONEY.map(({ name, help }) => (
          <TextField
            key={name}
            label={`${SETTING_LABELS[name]} (R)`}
            inputMode="decimal"
            value={draft[name]}
            onChange={(event) => change({ [name]: event.target.value })}
            help={help}
            error={errors.fields[name]}
          />
        ))}
      </fieldset>

      <fieldset className="la-fieldset la-stack-2">
        <legend className="la-overline">Payments</legend>
        <div className="la-choices">
          <ChoiceChip
            pressed={draft.payment_mode === "gateway"}
            onToggle={() => change({ payment_mode: "gateway" })}
          >
            Card and cash
          </ChoiceChip>
          <ChoiceChip
            pressed={draft.payment_mode === "cash_only"}
            onToggle={() => change({ payment_mode: "cash_only" })}
          >
            Cash only
          </ChoiceChip>
        </div>
        <p className="caption la-muted">
          {draft.payment_mode === "gateway"
            ? "Card payments go through PayFast. Cash is still accepted."
            : "An Admin confirms each cash payment in the app."}
        </p>
      </fieldset>

      {WHOLE.map((group) => (
        <fieldset key={group.title} className="la-fieldset la-stack">
          <legend className="la-overline">{group.title}</legend>
          {group.fields.map(({ name, label, help }) => (
            <TextField
              key={name}
              label={label}
              inputMode="numeric"
              value={draft[name]}
              onChange={(event) => change({ [name]: event.target.value })}
              help={help}
              error={errors.fields[name]}
            />
          ))}
        </fieldset>
      ))}

      {errors.general && <Banner status="cancelled" title={errors.general} />}
      {Object.keys(errors.fields).length > 0 && (
        <Banner status="cancelled" title="Some values need a change" />
      )}
      {done && <Banner status="confirmed" title="Saved" />}

      <button
        type="button"
        className="la-btn la-btn--primary la-btn--block"
        disabled={busy}
        onClick={save}
      >
        Save
      </button>
    </>
  );
}
