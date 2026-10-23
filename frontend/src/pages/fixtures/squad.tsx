// Who is playing (FR-38) and your reply (FR-3), for one match of your Team.
// SquadProgress is the design system's (README, Components; design/src/ui.mjs `squad`); the
// squad list and the reply card follow design/src/screens/f06-short.mjs and
// f02-confirmation.mjs. Whether replies are open, the minimum and the cutoff all come from
// the API: this file only draws them.

import { useState } from "react";
import { api, type Schemas } from "../../api/client";
import type { FormErrors } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { Icon, type IconName } from "../../components/Icon";
import { StatusChip } from "../../components/StatusChip";
import { send } from "../club/shared";
import { day, deadline } from "../inbox/shared";

export type Squad = Schemas["Squad"];
type Reply = Schemas["ConfirmationAnswerEnum"];

const REPLY_LABEL: Record<Reply, string> = { confirm: "I'm in", decline: "Can't make it" };
const REPLY_CHIP: Record<Reply, { status: "confirmed" | "cancelled"; label: string }> = {
  confirm: { status: "confirmed", label: "You're in" },
  decline: { status: "cancelled", label: "Can't make it" },
};

/** SquadProgress: confirmed Players against the Division minimum. */
export function SquadProgress({ squad, hint = true }: { squad: Squad; hint?: boolean }) {
  const { confirmed: n, min_players: min } = squad;
  const size = Math.max(squad.players.length, min, n) + 2;
  const done = !squad.below_minimum;
  const label = `${n} of ${min} confirmed`;
  let text: string | null = null;
  if (hint && squad.replies_open) {
    text = done
      ? "Your team meets the minimum for this match."
      : `Your team needs ${squad.short_by} more by ${deadline(squad.answer_by)} or it's out of the match.`;
  }
  return (
    <section className="la-card la-progress" aria-label="Squad">
      <div className="la-row">
        <span className="la-progress__label">
          <b>{n}</b> of {min} confirmed · {squad.team.name}
        </span>
        {done ? (
          <StatusChip status="confirmed">Ready</StatusChip>
        ) : (
          <StatusChip status="pending">{`Short ${squad.short_by}`}</StatusChip>
        )}
      </div>
      <div className="la-progress__track" role="img" aria-label={label}>
        <div
          className={`la-progress__fill${done ? " la-progress__fill--done" : ""}`}
          style={{ width: `${Math.min(100, (n / size) * 100)}%` }}
        />
        <div className="la-progress__min" style={{ left: `${(min / size) * 100}%` }} />
      </div>
      {text && <span className="la-progress__hint">{text}</span>}
    </section>
  );
}

const GROUPS: { answer: Reply | ""; title: string; tone: "confirmed" | "pending" | "cancelled"; icon: IconName }[] = [
  { answer: "confirm", title: "Confirmed", tone: "confirmed", icon: "check" },
  { answer: "", title: "Waiting", tone: "pending", icon: "clock" },
  { answer: "decline", title: "Declined", tone: "cancelled", icon: "x" },
];

/** The squad list: who confirmed, who hasn't answered, who declined. */
export function SquadReplies({ squad }: { squad: Squad }) {
  return (
    <ul className="la-group" aria-label="Squad replies">
      {GROUPS.map((group) => {
        const players = squad.players.filter((p) => p.answer === group.answer);
        const names = players.map((p) => `${p.name}${p.is_me ? " (you)" : ""}${p.is_captain ? " (captain)" : ""}`);
        // Borrowed through a Player or Goalkeeper Request (FR-37): counted as confirmed.
        if (group.answer === "confirm") {
          names.push(...squad.borrowed.map((p) => `${p.name} (${p.kind === "goalkeeper" ? "borrowed goalkeeper" : "borrowed"})`));
        }
        const count = names.length;
        return (
          <li key={group.title} className="la-item">
            <span className={`la-disc la-disc--${group.tone}`} aria-hidden="true">
              <Icon name={group.icon} />
            </span>
            <span className="la-item__body">
              <span className={group.answer === "confirm" ? "body-strong" : "body"}>
                {group.title} · {count}
              </span>
              <span className="caption la-muted">{names.length > 0 ? names.join(", ") : "No one"}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** Your reply: the two answers, or your answer with "Change" until the cutoff. */
export function YourReply({
  fixtureId,
  squad,
  notOpenYet,
  onAnswered,
}: {
  fixtureId: number;
  squad: Squad;
  /** The Confirmations haven't gone out yet. */
  notOpenYet: boolean;
  onAnswered: (squad: Squad) => void;
}) {
  const [changing, setChanging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<FormErrors | null>(null);
  const mine = squad.my_answer || null;
  const me = squad.players.find((p) => p.is_me);

  async function answer(reply: Reply) {
    setBusy(true);
    setErrors(null);
    let saved: Squad | undefined;
    const failed = await send(async () => {
      const answered = await api.POST("/api/v1/fixtures/{id}/answer/", {
        params: { path: { id: fixtureId } },
        body: { answer: reply },
      });
      saved = answered.data;
      return answered;
    });
    setBusy(false);
    if (failed || !saved) {
      setErrors(failed);
      return;
    }
    setChanging(false);
    onAnswered(saved);
  }

  const asking = squad.replies_open && (!mine || changing);
  return (
    <article className="la-card la-stack" aria-labelledby="your-reply">
      <div className="la-stack-2">
        <h2 id="your-reply" className="headline">
          Are you playing?
        </h2>
        {squad.replies_open && (
          <p className="caption la-muted">
            Reply by {deadline(squad.answer_by)}. You can change your answer until then.
          </p>
        )}
      </div>

      {errors?.general && <Banner status="cancelled" title={errors.general} />}

      {asking && (
        <div className="la-actions">
          {(["confirm", "decline"] as const).map((reply, i) => (
            <button
              key={reply}
              type="button"
              className={`la-btn ${i === 0 ? "la-btn--primary" : "la-btn--secondary"}`}
              disabled={busy}
              onClick={() => answer(reply)}
            >
              {REPLY_LABEL[reply]}
            </button>
          ))}
        </div>
      )}

      {mine && !asking && (
        <div className="la-row">
          <div className="la-stack-2">
            <span className="body-strong">Your answer</span>
            {me?.answered_at && <span className="caption la-muted">Answered {day(me.answered_at)}</span>}
          </div>
          <span style={{ display: "flex", gap: "var(--space-1)", alignItems: "center" }}>
            <StatusChip status={REPLY_CHIP[mine].status}>{REPLY_CHIP[mine].label}</StatusChip>
            {squad.replies_open && (
              <button type="button" className="la-btn la-btn--quiet la-btn--sm" onClick={() => setChanging(true)}>
                Change
              </button>
            )}
          </span>
        </div>
      )}

      {!squad.replies_open && !mine && (
        <p className="body la-muted">
          {notOpenYet
            ? "Replies open when the Confirmations go out."
            : "Replies are closed for this match. You didn't answer."}
        </p>
      )}
    </article>
  );
}
