// The Outstanding list (PRD FR-48; Screens.md Admin 5; design/src/screens/f14-finances.mjs
// owedRow): Teams and Players who owe, largest first, each with Remind (a notification) and
// Mark cash paid (a cash ledger entry). The backend decides who owes what, who a Remind
// reaches (only those opted into the Night) and what cash is recorded; this only shows it.

import { useState } from "react";
import { api, type Schemas } from "../../api/client";
import { formErrors, unreachable } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { formatRand, WEEKDAYS } from "../../format";
import { LoadState, useClub, useLoad } from "../club/shared";
import { scopeQuery, type Scope } from "./Planner";
import { NOT_AN_ADMIN } from "./shared";

type TeamOwed = Schemas["TeamOwed"];
type PlayerOwed = Schemas["PlayerOwed"];
type Row = { team_id: number; player_id: number | null; amount: string; who: string };
type Note = { status: "confirmed" | "pending" | "cancelled"; title: string; detail?: string };

/** "Thandi", "Thandi and Sipho", "Thandi, Sipho and Pieter". */
export function names(list: string[]): string {
  if (list.length <= 1) return list.join("");
  return `${list.slice(0, -1).join(", ")} and ${list[list.length - 1]}`;
}

export function Outstanding({ scope, onPaid }: { scope: Scope; onPaid: () => void }) {
  const { clubId } = useClub();
  const [who, setWho] = useState<"teams" | "players">("teams");
  const [note, setNote] = useState<Note | null>(null);
  const [busy, setBusy] = useState(false);
  const [owed, reload] = useLoad(
    () =>
      api.GET("/api/v1/clubs/{club_id}/finance/outstanding/", {
        params: { path: { club_id: clubId }, query: scopeQuery(scope) },
      }),
    `finance-outstanding-${clubId}-${scope.season}-${scope.night}-${scope.division}`,
  );

  async function remind(row: Row) {
    setBusy(true);
    setNote(null);
    try {
      const { data, error } = await api.POST("/api/v1/clubs/{club_id}/finance/outstanding/remind/", {
        params: { path: { club_id: clubId } },
        body: { team_id: row.team_id, player_id: row.player_id },
      });
      if (data) {
        const sent = data.sent_to.map((u) => u.name);
        const missed = data.not_reached.map((u) => u.name);
        const detail = missed.length
          ? `${names(missed)} ${missed.length === 1 ? "doesn't" : "don't"} get notifications for this Night, so ${missed.length === 1 ? "wasn't" : "weren't"} told.`
          : undefined;
        setNote(
          sent.length
            ? { status: "confirmed", title: `Reminder sent to ${names(sent)}.`, detail }
            : { status: "pending", title: `Nobody was reminded about ${row.who}.`, detail },
        );
      } else {
        setNote({ status: "cancelled", title: formErrors(error).general ?? "Couldn't send the reminder." });
        reload();
      }
    } catch {
      setNote({ status: "cancelled", title: unreachable.general! });
    }
    setBusy(false);
  }

  async function markCash(row: Row) {
    setBusy(true);
    setNote(null);
    try {
      const { data, error } = await api.POST("/api/v1/clubs/{club_id}/finance/outstanding/cash/", {
        params: { path: { club_id: clubId } },
        body: { team_id: row.team_id, player_id: row.player_id, amount: row.amount },
      });
      if (data) {
        setNote({ status: "confirmed", title: `${formatRand(data.amount)} cash recorded for ${row.who}.` });
        onPaid();
      } else {
        setNote({ status: "cancelled", title: formErrors(error).general ?? "Couldn't record the cash." });
      }
      reload();
    } catch {
      setNote({ status: "cancelled", title: unreachable.general! });
    }
    setBusy(false);
  }

  return (
    <section className="la-stack-2" aria-labelledby="outstanding">
      <h2 id="outstanding" className="la-overline">
        Outstanding · largest first
      </h2>
      <LoadState result={owed} retry={reload} what="Outstanding list" forbidden={NOT_AN_ADMIN}>
        {(data) => (
          <>
            <div className="la-choices" role="group" aria-label="Who owes">
              <ChoiceChip pressed={who === "teams"} onToggle={() => setWho("teams")}>
                Teams · {data.teams.length}
              </ChoiceChip>
              <ChoiceChip pressed={who === "players"} onToggle={() => setWho("players")}>
                Players · {data.players.length}
              </ChoiceChip>
            </div>
            {note && (
              <Banner status={note.status} title={note.title}>
                {note.detail}
              </Banner>
            )}
            {who === "teams" ? (
              data.teams.length === 0 ? (
                <p className="body la-muted">No Team owes anything here.</p>
              ) : (
                <ul className="la-group" aria-label="Outstanding teams">
                  {data.teams.map((t) => (
                    <OwedRow
                      key={t.team.id}
                      title={t.team.name}
                      sub={teamSub(t)}
                      row={{ team_id: t.team.id, player_id: null, amount: t.outstanding, who: t.team.name }}
                      busy={busy}
                      onRemind={remind}
                      onCash={markCash}
                    />
                  ))}
                </ul>
              )
            ) : data.players.length === 0 ? (
              <p className="body la-muted">No Player owes anything here.</p>
            ) : (
              <ul className="la-group" aria-label="Outstanding players">
                {data.players.map((p) => (
                  <OwedRow
                    key={`${p.team.id}-${p.player.id}`}
                    title={p.player.name}
                    sub={playerSub(p)}
                    row={{ team_id: p.team.id, player_id: p.player.id, amount: p.owes, who: p.player.name }}
                    busy={busy}
                    cantRemind={p.gets_notifications ? undefined : "Doesn't get notifications for this Night."}
                    onRemind={remind}
                    onCash={markCash}
                  />
                ))}
              </ul>
            )}
          </>
        )}
      </LoadState>
    </section>
  );
}

function teamSub(t: TeamOwed): string {
  const parts = [`${WEEKDAYS[t.night.weekday]} · ${t.division.name}`];
  if (t.short_since_week !== null) parts.push(`Short since week ${t.short_since_week}`);
  parts.push(t.unpaid_players.length ? `${names(t.unpaid_players)} unpaid` : "Owed by the Team");
  return parts.join(" · ");
}

function playerSub(p: PlayerOwed): string {
  return `${p.team.name} · Share ${formatRand(p.share)}, paid ${formatRand(p.paid)}`;
}

/** One row: who, why, what they owe, then Remind and Mark cash paid (which asks first). */
function OwedRow({
  title,
  sub,
  row,
  busy,
  cantRemind,
  onRemind,
  onCash,
}: {
  title: string;
  sub: string;
  row: Row;
  busy: boolean;
  cantRemind?: string;
  onRemind: (row: Row) => Promise<void>;
  onCash: (row: Row) => Promise<void>;
}) {
  const [asking, setAsking] = useState(false);
  return (
    <li className="la-item la-owed">
      <span className="la-item__body">
        <span className="body-strong">{title}</span>
        <span className="caption la-muted">{sub}</span>
        {cantRemind && <span className="caption la-muted">{cantRemind}</span>}
      </span>
      <span className="title-2 la-owed__amount">{formatRand(row.amount)}</span>
      <span className="la-owed__actions">
        {asking ? (
          <span className="la-confirm">
            <button
              type="button"
              className="la-btn la-btn--primary la-btn--sm"
              disabled={busy}
              onClick={() => {
                setAsking(false);
                void onCash(row);
              }}
            >
              Record {formatRand(row.amount)} cash
            </button>
            <button type="button" className="la-btn la-btn--quiet la-btn--sm" onClick={() => setAsking(false)}>
              Keep
            </button>
          </span>
        ) : (
          <>
            <button
              type="button"
              className="la-btn la-btn--quiet la-btn--sm"
              disabled={busy || cantRemind !== undefined}
              onClick={() => void onRemind(row)}
            >
              Remind
            </button>
            <button type="button" className="la-btn la-btn--quiet la-btn--sm" disabled={busy} onClick={() => setAsking(true)}>
              Mark cash paid
            </button>
          </>
        )}
      </span>
    </li>
  );
}
