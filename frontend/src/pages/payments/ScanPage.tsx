// The gate scanner for a club's Admins and Referees (FR-23; Screens.md Admin 9 and Referee 2;
// design/src/screens/f13-scan.mjs). In the installed app the camera opens straight away
// through frontend/src/native/scanner.ts; typing the code printed under the barcode is the
// fallback, and the only way in a browser. The result is large and clear: Paid or Not paid,
// the Team, the match and why not. Whether a Team is let in is the API's decision; this
// screen only shows it.

import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, type Schemas } from "../../api/client";
import { formErrors, unreachable } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { Icon } from "../../components/Icon";
import { TextField } from "../../components/TextField";
import { formatDate, formatMoment, formatRand, formatTime, localDate } from "../../format";
import { canScan, scanBarcode } from "../../native/scanner";
import { useClub } from "../club/shared";
import { ScreenHeader } from "../teams/shared";

type ScanResult = Schemas["ScanResult"];
type Method = Schemas["BarcodeScanMethodEnum"];
type State = Schemas["BarcodeScanStateEnum"];

const NOT_STAFF = "Only this club's Admins and Referees can scan Payment Barcodes.";
const DENIED = "Camera access is off for League App. Allow it in Settings, or enter the code.";
const FAILED = "The camera couldn't scan. Enter the code printed under the barcode instead.";

/** What the gate does next after a Not paid result. Copy only: the reason is the API's. */
function nextStep(state: State): string {
  switch (state) {
    case "not_found":
      return "Check the code and try again, or ask the Captain to open the Barcode in the app.";
    case "used":
      return "This Team has been let in already. Ask an Admin if that looks wrong.";
    case "not_today":
    case "expired":
    case "wrong_match":
      return "Ask the Captain to open tonight's Barcode.";
    case "unpaid":
      return "The Team can pay in the app, or pay cash to an Admin.";
    default:
      return "Ask an Admin of the club.";
  }
}

/** "vs Old Boys · 19:40 · Pitch 3", with the date when the match isn't today. */
function matchLine(result: ScanResult): string | null {
  const { fixture, team } = result;
  if (!fixture) return null;
  const opponent = team?.id === fixture.away_team.id ? fixture.home_team : fixture.away_team;
  const today = localDate(new Date().toISOString());
  const when = localDate(fixture.kick_off) === today ? formatTime(fixture.kick_off) : formatMoment(fixture.kick_off);
  const who = team ? `vs ${opponent.name}` : `${fixture.home_team.name} vs ${fixture.away_team.name}`;
  return `${who} · ${when} · ${fixture.pitch.name}`;
}

function validFor(result: ScanResult): string | null {
  if (!result.mode || !result.valid_until) return null;
  return result.mode === "match" ? "This match only" : `Until ${formatDate(result.valid_until)}`;
}

function paidLine(result: ScanResult): string | null {
  if (!result.paid || result.paid_amount === null) return null;
  const how = result.paid_methods.join(", ");
  return how ? `${formatRand(result.paid_amount)} · ${how}` : formatRand(result.paid_amount);
}

function Kv({ label, value }: { label: string; value: string }) {
  return (
    <div className="la-kv body">
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}

function Result({
  result,
  camera,
  onScanNext,
  onEnterCode,
}: {
  result: ScanResult;
  camera: boolean;
  onScanNext: () => void;
  onEnterCode: () => void;
}) {
  const { paid } = result;
  const line = matchLine(result);
  const valid = validFor(result);
  const money = paidLine(result);
  return (
    <section className="la-card la-stack" aria-label="Scan result">
      <div className={`la-result la-result--${paid ? "paid" : "notpaid"}`} role="status">
        <Icon name={paid ? "check" : "x"} />
        <span className="la-result__word">{paid ? "Paid" : "Not paid"}</span>
      </div>
      <div className="la-stack-1">
        <p className="title-2">{result.team?.name ?? "Unknown Barcode"}</p>
        {line && <p className="body la-muted">{line}</p>}
      </div>
      {!paid && (
        <div className="la-stack-1">
          <p className="body-strong">{result.reason}</p>
          <p className="body la-muted">{nextStep(result.state)}</p>
        </div>
      )}
      <div className="la-stack-2">
        <Kv label="Barcode" value={result.display_code ?? result.code} />
        {valid && <Kv label="Valid for" value={valid} />}
        {money && <Kv label="Paid" value={money} />}
      </div>
      {paid ? (
        <button type="button" className="la-btn la-btn--primary la-btn--block" onClick={onScanNext}>
          <Icon name="scan" />
          Scan next
        </button>
      ) : (
        <div className="la-actions">
          <button type="button" className="la-btn la-btn--primary" onClick={onScanNext}>
            <Icon name="scan" />
            Scan next
          </button>
          <button type="button" className="la-btn la-btn--secondary" onClick={onEnterCode}>
            Enter code
          </button>
        </div>
      )}
      {!camera && <p className="caption la-muted">Camera scanning works in the League App app.</p>}
    </section>
  );
}

export function ScanPage() {
  const { clubId, clubName } = useClub();
  const camera = canScan();
  const [view, setView] = useState<"camera" | "manual" | "result">(camera ? "camera" : "manual");
  const [code, setCode] = useState("");
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const opened = useRef(false);

  async function check(entered: string, method: Method) {
    setBusy(true);
    setError(null);
    try {
      const { data, error: body, response } = await api.POST("/api/v1/clubs/{club_id}/scans/", {
        params: { path: { club_id: clubId } },
        body: { code: entered, method },
      });
      if (data) {
        setResult(data);
        setView("result");
        setCode("");
      } else if (response.status === 403) {
        setError(NOT_STAFF);
      } else {
        const failed = formErrors(body);
        setError(failed.general ?? Object.values(failed.fields)[0] ?? "That didn't work.");
      }
    } catch {
      setError(unreachable.general);
    } finally {
      setBusy(false);
    }
  }

  async function openCamera() {
    setError(null);
    const outcome = await scanBarcode();
    if (outcome.kind === "code") {
      await check(outcome.code, "camera");
    } else if (outcome.kind === "cancelled") {
      setView("camera");
    } else {
      setError(outcome.kind === "denied" ? DENIED : FAILED);
      setView("manual");
    }
  }

  // In the app the camera opens straight away (design: "Camera opens directly from the Scan
  // tab"). Once only, also under React's development double effects.
  useEffect(() => {
    if (camera && !opened.current) {
      opened.current = true;
      void openCamera();
    }
  }, []);

  function scanNext() {
    setResult(null);
    if (camera) {
      setView("camera");
      void openCamera();
    } else {
      setView("manual");
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || !code.trim()) return;
    void check(code.trim(), "manual");
  }

  return (
    <main className="la-screen">
      <ScreenHeader title="Scan" back={{ label: "Profile", to: "/profile" }} caption={`Gate · ${clubName}`} />
      {error && <Banner status="cancelled" title={error} />}

      {view === "result" && result && (
        <Result
          result={result}
          camera={camera}
          onScanNext={scanNext}
          onEnterCode={() => {
            setResult(null);
            setView("manual");
          }}
        />
      )}

      {view === "camera" && (
        <section className="la-card la-stack" aria-label="Scan a Payment Barcode">
          <p className="la-overline">Scan a Payment Barcode</p>
          <p className="body">Hold the barcode inside the frame. Use the torch at a dark gate.</p>
          <button
            type="button"
            className="la-btn la-btn--primary la-btn--block"
            disabled={busy}
            onClick={() => void openCamera()}
          >
            <Icon name="scan" />
            Open camera
          </button>
          <button type="button" className="la-btn la-btn--secondary la-btn--block" onClick={() => setView("manual")}>
            Enter code instead
          </button>
        </section>
      )}

      {view === "manual" && (
        <form className="la-stack" onSubmit={submit} aria-label="Enter code">
          <p className="body la-muted">Type the code printed under the barcode.</p>
          <TextField
            label="Barcode code"
            help="10 letters and numbers. Spaces are optional."
            value={code}
            onChange={(e) => setCode(e.target.value)}
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            maxLength={40}
          />
          <button type="submit" className="la-btn la-btn--primary la-btn--block" disabled={busy || !code.trim()}>
            {busy ? "Checking" : "Check code"}
          </button>
          {camera && (
            <button
              type="button"
              className="la-btn la-btn--secondary la-btn--block"
              onClick={() => {
                setView("camera");
                void openCamera();
              }}
            >
              <Icon name="scan" />
              Scan with camera
            </button>
          )}
        </form>
      )}
    </main>
  );
}
