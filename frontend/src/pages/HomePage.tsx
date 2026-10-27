import { useHealth } from "../api/useHealth";
import { Logo } from "../components/Logo";
import { StatusChip } from "../components/StatusChip";

/** Placeholder home until the first flow lands: the app name and whether the API answers. */
export function HomePage() {
  const health = useHealth();

  return (
    <main style={{ display: "grid", gap: "var(--space-3)", padding: "var(--space-6) var(--gutter)" }}>
      <h1 className="title-2">
        <Logo />
      </h1>
      <p className="body" style={{ color: "var(--ink-muted)" }}>
        Floodlit football, organised: reply, pay, play.
      </p>
      <div>
        {health.state === "loading" && <StatusChip status="pending">Checking the API</StatusChip>}
        {health.state === "ok" && <StatusChip status="confirmed">API connected</StatusChip>}
        {health.state === "degraded" && (
          <StatusChip status="cancelled">API can't reach the database</StatusChip>
        )}
        {health.state === "unreachable" && (
          <StatusChip status="cancelled">API not reachable</StatusChip>
        )}
      </div>
    </main>
  );
}
