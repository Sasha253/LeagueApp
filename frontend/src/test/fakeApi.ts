// A stand-in for the backend: answers fetch by method and path, and records every call.

import { vi } from "vitest";

type Answer = { status: number; body?: unknown } | ((request: Request) => Promise<Response> | Response);
export type Routes = Record<string, Answer | Answer[]>;

export const json = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

/** Routes are "METHOD /path/". A list answers in turn, repeating the last answer. */
export function fakeApi(routes: Routes) {
  const calls: { method: string; path: string; auth: string | null; body: unknown }[] = [];
  const seen: Record<string, number> = {};

  const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init);
    const path = new URL(request.url).pathname;
    const key = `${request.method} ${path}`;
    const text = await request.clone().text();
    calls.push({
      method: request.method,
      path,
      auth: request.headers.get("Authorization"),
      body: text ? JSON.parse(text) : undefined,
    });
    const route = routes[key];
    if (!route) return json(404, { detail: `No fake for ${key}` });
    const answers = Array.isArray(route) ? route : [route];
    const n = seen[key] ?? 0;
    seen[key] = n + 1;
    const answer = answers[Math.min(n, answers.length - 1)]!;
    return typeof answer === "function" ? answer(request) : json(answer.status, answer.body);
  });

  vi.stubGlobal("fetch", fetch);
  return { fetch, calls };
}

export const ME = {
  id: 1,
  email: "sipho@example.com",
  name: "Sipho Dlamini",
  phone: "",
  is_booking_user: false,
  player: { position: "outfield", nights: [] as number[] },
  club_roles: [] as { club_id: number; club_name: string; role: "admin" | "referee" }[],
};

export const TOKENS = { access: "access-1", refresh: "refresh-1" };
