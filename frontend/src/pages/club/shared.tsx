// What every club setup screen shares: loading from the API, the screen header, and a
// delete button that asks first.

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router";
import { api } from "../../api/client";
import { formErrors, unreachable, type FormErrors } from "../../api/errors";
import { useAuth } from "../../auth/AuthProvider";
import { Banner } from "../../components/Banner";

export const NO_ERRORS: FormErrors = { fields: {}, general: null };

/** The Club in the URL, and its name from the signed-in user's roles. A superuser holds
 *  no role at most Clubs, so their name comes from the API. */
export function useClub(): { clubId: number; clubName: string } {
  const { clubId } = useParams();
  const { state } = useAuth();
  const id = Number(clubId);
  const me = state.status === "signedIn" ? state.me : null;
  const role = me?.club_roles.find((r) => r.club_id === id);
  const askApi = !role && !!me?.is_superuser;
  const [fetched, setFetched] = useState<{ id: number; name: string } | null>(null);

  useEffect(() => {
    if (!askApi) return;
    let cancelled = false;
    api
      .GET("/api/v1/clubs/{club_id}/", { params: { path: { club_id: id } } })
      .then(({ data }) => {
        if (!cancelled && data) setFetched(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [askApi, id]);

  const name = role?.club_name ?? (fetched?.id === id ? fetched.name : null);
  return { clubId: id, clubName: name ?? "Club" };
}

export type Loaded<T> =
  | { state: "loading" }
  | { state: "ok"; data: T }
  | { state: "forbidden" }
  | { state: "error" };

type Answer<T> = { data?: T; error?: unknown; response: Response };

/** Calls `load` now and on reload(). 403 means this user isn't an Admin of the Club. */
export function useLoad<T>(load: () => Promise<Answer<T>>, key: string): [Loaded<T>, () => void] {
  const [result, setResult] = useState<Loaded<T>>({ state: "loading" });
  const [attempt, setAttempt] = useState(0);
  // `key` names what is loaded, so `load` itself needn't be stable.
  const run = useCallback(load, [key]);

  useEffect(() => {
    let cancelled = false;
    run()
      .then(({ data, response }) => {
        if (cancelled) return;
        if (data !== undefined) setResult({ state: "ok", data });
        else setResult({ state: response.status === 403 ? "forbidden" : "error" });
      })
      .catch(() => {
        if (!cancelled) setResult({ state: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [run, attempt]);

  return [result, useCallback(() => setAttempt((n) => n + 1), [])];
}

/** Sends a change. Answers the errors to show, or null when it worked. */
export async function send(call: () => Promise<{ error?: unknown; response: Response }>) {
  try {
    const { error, response } = await call();
    return response.ok ? null : formErrors(error);
  } catch {
    return unreachable;
  }
}

/** Shows what isn't loaded yet, or the screen once it is. */
export function LoadState<T>({
  result,
  retry,
  what,
  forbidden = "Only this club's Admins can open club setup.",
  children,
}: {
  result: Loaded<T>;
  retry: () => void;
  what: string;
  /** What a 403 means on this screen. */
  forbidden?: string;
  children: (data: T) => ReactNode;
}) {
  if (result.state === "loading") {
    return (
      <p className="caption la-muted" role="status">
        Loading {what}
      </p>
    );
  }
  if (result.state === "forbidden") {
    return <Banner status="cancelled" title={forbidden} />;
  }
  if (result.state === "error") {
    return (
      <Banner status="cancelled" title={`Couldn't load the ${what}`}>
        <button type="button" className="la-btn la-btn--quiet" onClick={retry}>
          Retry
        </button>
      </Banner>
    );
  }
  return <>{children(result.data)}</>;
}

/** Back to Club home or the setup hub, the title, and the Club it belongs to. */
const BACK = {
  setup: { label: "Club setup", path: "setup" },
  nights: { label: "Nights and Divisions", path: "setup/nights" },
} as const;

export function SetupHeader({ title, back = "setup" }: { title: string; back?: "setup" | "nights" | "home" }) {
  const { clubId, clubName } = useClub();
  const to = back === "home" ? `/clubs/${clubId}` : `/clubs/${clubId}/${BACK[back].path}`;
  return (
    <div className="la-stack-2">
      <Link className="la-btn la-btn--quiet la-back" to={to}>
        {back === "home" ? "Club home" : BACK[back].label}
      </Link>
      <h1 className="title-1">{title}</h1>
      <p className="caption la-muted">{clubName}</p>
    </div>
  );
}

/** A Delete or Remove button that asks once more before it acts. */
export function ConfirmButton({
  label,
  confirmLabel,
  onConfirm,
}: {
  label: string;
  confirmLabel: string;
  onConfirm: () => void;
}) {
  const [asking, setAsking] = useState(false);
  if (!asking) {
    return (
      <button type="button" className="la-btn la-btn--quiet la-btn--sm" onClick={() => setAsking(true)}>
        {label}
      </button>
    );
  }
  return (
    <span className="la-confirm">
      <button type="button" className="la-btn la-btn--danger la-btn--sm" onClick={onConfirm}>
        {confirmLabel}
      </button>
      <button type="button" className="la-btn la-btn--quiet la-btn--sm" onClick={() => setAsking(false)}>
        Keep
      </button>
    </span>
  );
}
