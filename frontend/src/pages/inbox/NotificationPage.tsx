// Notification detail (design/src/ds/Screens.md, Shared 4; f02-confirmation.mjs): a
// ConfirmationCard for the kinds that take an answer, a plain message for the rest.
// Opening it marks it read. The answer can be changed while the API says it can (FR-3);
// confirming a match shows "You're in!".

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { api } from "../../api/client";
import type { FormErrors } from "../../api/errors";
import { useAuth } from "../../auth/AuthProvider";
import { Banner } from "../../components/Banner";
import { StatusChip } from "../../components/StatusChip";
import { formatMoment } from "../../format";
import { inboxChanged } from "../../push/events";
import { FIND_MATCH, FIND_MATCH_PATH } from "../../push/links";
import { LoadState, send, useLoad } from "../club/shared";
import { ScreenHeader } from "../teams/shared";
import {
  answerChip,
  buttonLabel,
  day,
  deadline,
  Disc,
  KIND_LABEL,
  type AnswerKey,
  type Notification,
} from "./shared";

export function NotificationPage() {
  const id = Number(useParams().notificationId);
  const [result, reload] = useLoad(
    () => api.GET("/api/v1/inbox/{notification_id}/", { params: { path: { notification_id: id } } }),
    `notification-${id}`,
  );

  return (
    <main className="la-screen">
      {result.state !== "ok" && <ScreenHeader title="Notification" back={{ label: "Inbox", to: "/inbox" }} />}
      <LoadState result={result} retry={reload} what="notification" forbidden="This notification isn't yours.">
        {(notification) => <Detail key={notification.id} initial={notification} />}
      </LoadState>
    </main>
  );
}

function Detail({ initial }: { initial: Notification }) {
  const [n, setN] = useState(initial);
  const [changing, setChanging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<FormErrors | null>(null);
  const [justIn, setJustIn] = useState(false);
  const { state } = useAuth();

  // Opening it reads it. A failure only leaves it unread.
  useEffect(() => {
    if (initial.read_at !== null) return;
    api
      .POST("/api/v1/inbox/{notification_id}/read/", { params: { path: { notification_id: initial.id } } })
      .then(({ data }) => {
        if (data) {
          setN((current) => ({ ...current, read_at: data.read_at }));
          inboxChanged();
        }
      })
      .catch(() => {});
  }, [initial.id, initial.read_at]);

  async function answer(key: AnswerKey) {
    setBusy(true);
    setErrors(null);
    let saved: Notification | undefined;
    const failed = await send(async () => {
      const answered = await api.POST("/api/v1/inbox/{notification_id}/answer/", {
        params: { path: { notification_id: n.id } },
        body: { answer: key },
      });
      saved = answered.data;
      return answered;
    });
    setBusy(false);
    if (failed || !saved) {
      setErrors(failed);
      return;
    }
    setN(saved);
    setChanging(false);
    setJustIn(saved.kind === "confirmation" && saved.answer === "confirm");
    inboxChanged();
  }

  const answerButtons = n.actions.filter((a) => a.action === "answer");
  const findMatch = n.actions.find((a) => a.action === "open" && a.key === FIND_MATCH);
  const showButtons = n.can_answer && answerButtons.length > 0 && (!n.answer || changing);
  const isAdmin =
    state.status === "signedIn" && state.me.club_roles.some((r) => r.club_id === n.club_id && r.role === "admin");
  const matchPath = n.fixture_id === null ? null : isAdmin ? `/clubs/${n.club_id}/fixtures/${n.fixture_id}` : `/fixtures/${n.fixture_id}`;

  return (
    <>
      <ScreenHeader title={KIND_LABEL[n.kind]} back={{ label: "Inbox", to: "/inbox" }} caption={formatMoment(n.created_at)} />

      {justIn && (
        <div className="la-hero" role="status">
          <Disc notification={n} xl />
          <p className="title-1">You're in!</p>
          {n.body && <p className="body la-muted">{n.body}</p>}
        </div>
      )}

      <article className="la-card la-stack" aria-labelledby="notification-title">
        <div style={{ display: "flex", gap: "var(--space-3)" }}>
          <Disc notification={n} />
          <div className="la-stack-2">
            <h2 id="notification-title" className="headline">
              {n.title}
            </h2>
            {n.body && <p className="body la-muted">{n.body}</p>}
            {n.needs_reply && n.answer_by && (
              <p className="caption la-muted">
                Reply by {deadline(n.answer_by)}. You can change your answer until then.
              </p>
            )}
          </div>
        </div>

        {errors?.general && <Banner status="cancelled" title={errors.general} />}

        {showButtons && (
          <div className="la-actions">
            {answerButtons.map((a, i) => (
              <button
                key={a.key}
                type="button"
                className={`la-btn ${i === 0 ? "la-btn--primary" : "la-btn--secondary"}`}
                disabled={busy}
                onClick={() => answer(a.key as AnswerKey)}
              >
                {buttonLabel(n.kind, a.key, a.label)}
              </button>
            ))}
          </div>
        )}

        {n.answer && !changing && (
          <div className="la-row">
            <div className="la-stack-2">
              <span className="body-strong">Your answer</span>
              {n.answered_at && <span className="caption la-muted">Answered {day(n.answered_at)}</span>}
            </div>
            <span style={{ display: "flex", gap: "var(--space-1)", alignItems: "center" }}>
              <StatusChip status={answerChip(n.kind, n.answer).status}>{answerChip(n.kind, n.answer).label}</StatusChip>
              {n.can_answer && (
                <button type="button" className="la-btn la-btn--quiet la-btn--sm" onClick={() => setChanging(true)}>
                  Change
                </button>
              )}
            </span>
          </div>
        )}

        {answerButtons.length > 0 && !n.can_answer && !n.answer && (
          <Banner status="info" title="Replies are closed">
            This can't be answered any more.
          </Banner>
        )}

        {findMatch && (
          <Link className="la-btn la-btn--primary" to={FIND_MATCH_PATH}>
            {findMatch.label}
          </Link>
        )}
      </article>

      {matchPath && (
        <Link className="la-btn la-btn--secondary" to={matchPath}>
          Open the match
        </Link>
      )}
    </>
  );
}
