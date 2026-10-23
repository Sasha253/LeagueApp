// Inbox (design/src/ds/Screens.md, Shared 3; design/src/screens/f02-confirmation.mjs):
// every notification, unanswered ones pinned on top with a pending chip. Filters: All,
// Needs reply, Updates. Unread rows carry a dot and a bold title.

import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import { StatusChip } from "../../components/StatusChip";
import { onInboxChanged } from "../../push/events";
import { LoadState, useLoad } from "../club/shared";
import { ScreenHeader } from "../teams/shared";
import { day, deadline, Disc, KIND_LABEL, type Notification } from "./shared";

type Filter = "all" | "needs_reply" | "updates";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "needs_reply", label: "Needs reply" },
  { key: "updates", label: "Updates" },
];

const EMPTY: Record<Filter, string> = {
  all: "Nothing here yet. Match confirmations, requests and updates arrive here.",
  needs_reply: "You're all caught up. Nothing is waiting for your answer.",
  updates: "No updates yet.",
};

function caption(n: Notification): string {
  if (n.needs_reply) return n.body || KIND_LABEL[n.kind];
  if (n.answer && n.answered_at) return `${KIND_LABEL[n.kind]} · answered ${day(n.answered_at)}`;
  return `${KIND_LABEL[n.kind]} · ${n.body || day(n.created_at)}`;
}

function Row({ notification: n }: { notification: Notification }) {
  const unread = n.read_at === null;
  return (
    <li>
      <Link className="la-item la-item--link" to={`/inbox/${n.id}`}>
        <Disc notification={n} />
        <span className="la-item__body">
          <span className={unread ? "body-strong" : "body"}>
            {unread && <span className="sr-only">Unread: </span>}
            {n.title}
          </span>
          <span className="caption la-muted">{caption(n)}</span>
          {n.needs_reply && (
            <span>
              <StatusChip status="pending">{n.answer_by ? `Reply by ${deadline(n.answer_by)}` : "Reply needed"}</StatusChip>
            </span>
          )}
        </span>
        {unread && <span className="la-unread" aria-hidden="true" />}
      </Link>
    </li>
  );
}

function Section({ title, id, items }: { title?: string; id: string; items: Notification[] }) {
  if (items.length === 0) return null;
  return (
    <section className="la-stack-2" aria-labelledby={title ? id : undefined} aria-label={title ? undefined : "Notifications"}>
      {title && (
        <h2 id={id} className="la-overline">
          {title}
        </h2>
      )}
      <ul className="la-group">
        {items.map((n) => (
          <Row key={n.id} notification={n} />
        ))}
      </ul>
    </section>
  );
}

/** The notifications for one filter; reloads when the inbox changes. */
function List({ filter, onSeeAll }: { filter: Filter; onSeeAll: () => void }) {
  const [list, reloadList] = useLoad(
    () => api.GET("/api/v1/inbox/", { params: { query: { filter } } }),
    `inbox-${filter}`,
  );
  useEffect(() => onInboxChanged(reloadList), [reloadList]);

  return (
    <LoadState result={list} retry={reloadList} what="inbox" forbidden="Sign in to see your inbox.">
      {(items) =>
        items.length === 0 ? (
          <div className="la-stack-2">
            <p className="body la-muted">{EMPTY[filter]}</p>
            {filter === "all" ? (
              <Link className="la-btn la-btn--secondary" to="/profile">
                Choose your Nights
              </Link>
            ) : (
              <button type="button" className="la-btn la-btn--secondary" onClick={onSeeAll}>
                See all
              </button>
            )}
          </div>
        ) : filter === "all" ? (
          <>
            <Section title="Needs reply" id="needs-reply" items={items.filter((n) => n.needs_reply)} />
            <Section title="Earlier" id="earlier" items={items.filter((n) => !n.needs_reply)} />
          </>
        ) : (
          <Section id="list" items={items} />
        )
      }
    </LoadState>
  );
}

export function InboxPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const [summary, reloadSummary] = useLoad(() => api.GET("/api/v1/inbox/summary/"), "inbox-summary");

  useEffect(() => onInboxChanged(reloadSummary), [reloadSummary]);

  const waiting = summary.state === "ok" ? summary.data.needs_reply : 0;
  const unread = summary.state === "ok" ? summary.data.unread : 0;

  return (
    <main className="la-screen">
      <ScreenHeader
        title="Inbox"
        back={{ label: "Profile", to: "/profile" }}
        caption={unread > 0 ? `${unread} unread` : undefined}
      />
      <div className="la-choices" role="group" aria-label="Show">
        {FILTERS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            className="la-choice"
            aria-pressed={filter === key}
            onClick={() => setFilter(key)}
          >
            {label}
            {key === "needs_reply" && waiting > 0 && (
              <span className="la-choice__count">
                <span className="sr-only">, </span>
                {waiting}
              </span>
            )}
          </button>
        ))}
      </div>
      {/* Keyed by filter: a new filter starts loading afresh, never showing the last one's rows. */}
      <List key={filter} filter={filter} onSeeAll={() => setFilter("all")} />
    </main>
  );
}
