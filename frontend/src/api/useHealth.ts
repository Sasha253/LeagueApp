import { useEffect, useState } from "react";
import { api, type Health } from "./client";

export type HealthResult =
  | { state: "loading" }
  | { state: "ok"; health: Health }
  // The API answered but reported a problem (HTTP 503 with a body).
  | { state: "degraded"; health: Health }
  | { state: "unreachable" };

/** Asks /api/v1/health/ once and reports what the server said. */
export function useHealth(): HealthResult {
  const [result, setResult] = useState<HealthResult>({ state: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    api
      .GET("/api/v1/health/", { signal: controller.signal })
      .then(({ data, error, response }) => {
        if (data) setResult({ state: "ok", health: data });
        else if (response.status === 503 && error) setResult({ state: "degraded", health: error });
        // Anything else (e.g. the dev proxy's 500 when Django is down) means no answer.
        else setResult({ state: "unreachable" });
      })
      .catch(() => {
        if (!controller.signal.aborted) setResult({ state: "unreachable" });
      });
    return () => controller.abort();
  }, []);

  return result;
}
