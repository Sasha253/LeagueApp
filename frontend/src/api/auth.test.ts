import { describe, expect, it, vi } from "vitest";
import { fakeApi, json, TOKENS } from "../test/fakeApi";
import { currentTokens, loadTokens, onSessionEnded, setTokens } from "./auth";
import { api } from "./client";

const ME_PATH = "/api/v1/auth/me/";

describe("auth tokens", () => {
  it("are saved and loaded again after a restart", async () => {
    await setTokens(TOKENS);

    expect(window.localStorage.getItem("leagueapp.tokens")).toContain("access-1");
    expect(await loadTokens()).toEqual(TOKENS);
  });

  it("survive a corrupt saved value by signing out", async () => {
    window.localStorage.setItem("leagueapp.tokens", "{not json");

    expect(await loadTokens()).toBeNull();
  });

  it("are sent as a Bearer header", async () => {
    await setTokens(TOKENS);
    const { calls } = fakeApi({ [`GET ${ME_PATH}`]: { status: 200, body: {} } });

    await api.GET(ME_PATH);

    expect(calls[0]!.auth).toBe("Bearer access-1");
  });

  it("are refreshed once on a 401 and the request retried", async () => {
    await setTokens(TOKENS);
    const { calls } = fakeApi({
      [`GET ${ME_PATH}`]: [{ status: 401 }, { status: 200, body: { id: 1 } }],
      "POST /api/v1/auth/refresh/": { status: 200, body: { access: "access-2", refresh: "refresh-2" } },
    });

    const { data } = await api.GET(ME_PATH);

    expect(data).toEqual({ id: 1 });
    expect(calls.map((c) => `${c.method} ${c.path} ${c.auth ?? ""}`)).toEqual([
      `GET ${ME_PATH} Bearer access-1`,
      "POST /api/v1/auth/refresh/ ",
      `GET ${ME_PATH} Bearer access-2`,
    ]);
    expect(calls[1]!.body).toEqual({ refresh: "refresh-1" });
    expect(currentTokens()).toEqual({ access: "access-2", refresh: "refresh-2" });
  });

  it("share one refresh between requests that fail together", async () => {
    await setTokens(TOKENS);
    let firstRound = 2;
    const { calls } = fakeApi({
      [`GET ${ME_PATH}`]: () => json(firstRound-- > 0 ? 401 : 200, {}),
      "POST /api/v1/auth/refresh/": { status: 200, body: { access: "access-2", refresh: "refresh-2" } },
    });

    await Promise.all([api.GET(ME_PATH), api.GET(ME_PATH)]);

    expect(calls.filter((c) => c.path === "/api/v1/auth/refresh/")).toHaveLength(1);
  });

  it("end the session when the refresh token is refused", async () => {
    await setTokens(TOKENS);
    const ended = vi.fn();
    const stop = onSessionEnded(ended);
    fakeApi({
      [`GET ${ME_PATH}`]: { status: 401 },
      "POST /api/v1/auth/refresh/": { status: 401 },
    });

    const { response } = await api.GET(ME_PATH);

    expect(response.status).toBe(401);
    expect(ended).toHaveBeenCalledOnce();
    expect(currentTokens()).toBeNull();
    expect(window.localStorage.getItem("leagueapp.tokens")).toBeNull();
    stop();
  });

  it("are kept when the refresh can't reach the API", async () => {
    await setTokens(TOKENS);
    fakeApi({
      [`GET ${ME_PATH}`]: { status: 401 },
      "POST /api/v1/auth/refresh/": () => Promise.reject(new TypeError("Failed to fetch")),
    });

    await api.GET(ME_PATH);

    expect(currentTokens()).toEqual(TOKENS);
  });

  it("are not sent when signed out", async () => {
    const { calls } = fakeApi({ "GET /api/v1/health/": { status: 200, body: {} } });

    await api.GET("/api/v1/health/");

    expect(calls[0]!.auth).toBeNull();
  });
});
