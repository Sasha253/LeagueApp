// The signed-in session's tokens and the middleware that sends them.
//
// The app authenticates with tokens, never cookies (CLAUDE.md). The access token is short
// lived; when the API answers 401, the middleware swaps the refresh token for a new pair
// once and retries the request. If the refresh token is refused too, the session has
// ended and every onSessionEnded listener hears about it.

import type { Middleware } from "openapi-fetch";
import { storage } from "../native/storage";

export type Tokens = { access: string; refresh: string };

const STORAGE_KEY = "leagueapp.tokens";
const REFRESH_PATH = "/api/v1/auth/refresh/";

let tokens: Tokens | null = null;
let refreshing: Promise<boolean> | null = null;
const sessionEndedListeners = new Set<() => void>();

/** Reads the saved tokens at start-up. */
export async function loadTokens(): Promise<Tokens | null> {
  const saved = await storage.get(STORAGE_KEY);
  try {
    tokens = saved ? (JSON.parse(saved) as Tokens) : null;
  } catch {
    tokens = null;
  }
  return tokens;
}

export function currentTokens(): Tokens | null {
  return tokens;
}

/** Saves the tokens of a new session, or forgets them with null. */
export async function setTokens(next: Tokens | null): Promise<void> {
  tokens = next;
  if (next) await storage.set(STORAGE_KEY, JSON.stringify(next));
  else await storage.remove(STORAGE_KEY);
}

export function onSessionEnded(listener: () => void): () => void {
  sessionEndedListeners.add(listener);
  return () => sessionEndedListeners.delete(listener);
}

/** Swaps the refresh token for a new pair. True when it worked. Shared by callers. */
function refreshTokens(baseUrl: string): Promise<boolean> {
  refreshing ??= (async () => {
    const refresh = tokens?.refresh;
    if (!refresh) return false;
    const response = await globalThis.fetch(new URL(REFRESH_PATH, baseUrl), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (response.ok) {
      const body = (await response.json()) as Tokens;
      await setTokens({ access: body.access, refresh: body.refresh ?? refresh });
      return true;
    }
    // 401: the refresh token expired or was blacklisted. Anything else may pass.
    if (response.status === 401) {
      await setTokens(null);
      sessionEndedListeners.forEach((listener) => listener());
    }
    return false;
  })()
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

// A copy of each signed request, kept until its answer arrives, for the one retry.
const sentRequests = new Map<string, Request>();

export const authMiddleware: Middleware = {
  onRequest({ request, id }) {
    if (!tokens) return request;
    request.headers.set("Authorization", `Bearer ${tokens.access}`);
    sentRequests.set(id, request.clone());
    return request;
  },

  async onResponse({ response, id, options }) {
    const sent = sentRequests.get(id);
    sentRequests.delete(id);
    if (response.status !== 401 || !sent) return response;
    if (!(await refreshTokens(options.baseUrl)) || !tokens) return response;
    sent.headers.set("Authorization", `Bearer ${tokens.access}`);
    return globalThis.fetch(sent);
  },

  onError({ id }) {
    sentRequests.delete(id);
  },
};
