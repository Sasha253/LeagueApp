// Who is signed in. Loads the saved session at start-up and ends it when the refresh
// token stops working.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { currentTokens, loadTokens, onSessionEnded, setTokens, type Tokens } from "../api/auth";
import { api, type Me } from "../api/client";
import { forgetDevice } from "../push/device";

export type AuthState =
  | { status: "loading" }
  | { status: "signedOut" }
  // A session is saved but the API could not be reached to load it.
  | { status: "unreachable" }
  | { status: "signedIn"; me: Me };

type AuthContextValue = {
  state: AuthState;
  startSession: (tokens: Tokens, me: Me) => Promise<void>;
  endSession: () => Promise<void>;
  setMe: (me: Me) => void;
  retry: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!(await loadTokens())) return setState({ status: "signedOut" });
      try {
        const { data } = await api.GET("/api/v1/auth/me/");
        if (cancelled) return;
        if (data) setState({ status: "signedIn", me: data });
        else if (!currentTokens()) setState({ status: "signedOut" });
        else setState({ status: "unreachable" });
      } catch {
        if (!cancelled) setState({ status: "unreachable" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  useEffect(() => onSessionEnded(() => setState({ status: "signedOut" })), []);

  const startSession = useCallback(async (tokens: Tokens, me: Me) => {
    await setTokens(tokens);
    setState({ status: "signedIn", me });
  }, []);

  const endSession = useCallback(async () => {
    const refresh = currentTokens()?.refresh;
    // While the session still works, so this phone gets no more pushes for this account.
    await forgetDevice().catch(() => {});
    // Best effort: signing out on the phone must work even when the API can't be reached.
    if (refresh) await api.POST("/api/v1/auth/logout/", { body: { refresh } }).catch(() => {});
    await setTokens(null);
    setState({ status: "signedOut" });
  }, []);

  const setMe = useCallback((me: Me) => setState({ status: "signedIn", me }), []);
  const retry = useCallback(() => {
    setState({ status: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  const value = useMemo(
    () => ({ state, startSession, endSession, setMe, retry }),
    [state, startSession, endSession, setMe, retry],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth needs an AuthProvider above it.");
  return value;
}
