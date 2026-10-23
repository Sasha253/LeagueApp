// Import Nights and Divisions (FR-39): the Admin uploads a spreadsheet, sees what each row
// would do, and confirms. The API checks every row and saves all or nothing; re-importing
// the same file changes nothing (docs/DECISIONS.md).

import { useState } from "react";
import { Link } from "react-router";
import { api, type Schemas } from "../../api/client";
import { formErrors, unreachable } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { StatusChip, type Status } from "../../components/StatusChip";
import { formatRand, WEEKDAYS } from "../../format";
import { saveFile } from "../../native/files";
import { SetupHeader, useClub } from "./shared";

type Result = Schemas["ImportResult"];
type Row = Schemas["ImportRow"];
type Step =
  | { name: "choose" }
  | { name: "checking"; file: File }
  | { name: "preview"; file: File; result: Result }
  | { name: "saving"; file: File; result: Result }
  | { name: "done"; result: Result };

const ACTIONS: Record<Row["action"], { status: Status; label: string }> = {
  create: { status: "confirmed", label: "New" },
  update: { status: "pending", label: "Changes" },
  unchanged: { status: "info", label: "No change" },
  error: { status: "cancelled", label: "Error" },
};

const count = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** "2 new Divisions, 1 Division changes, 3 unchanged, 1 new Night" */
function summaryLine(summary: Result["summary"], committed: boolean): string {
  const [changesOne, changesMany] = committed
    ? ["Division changed", "Divisions changed"]
    : ["Division changes", "Divisions change"];
  const parts = [
    summary.divisions_created && count(summary.divisions_created, "new Division", "new Divisions"),
    summary.divisions_updated && count(summary.divisions_updated, changesOne, changesMany),
    summary.unchanged && `${summary.unchanged} unchanged`,
    summary.nights_created && count(summary.nights_created, "new Night", "new Nights"),
  ].filter(Boolean);
  return parts.length ? parts.join(", ") : "No rows to import";
}

function rowDetail(row: Row): string {
  const fee = row.league_fee === null ? "club fee" : `${formatRand(row.league_fee)} per Team`;
  return `Minimum ${row.min_players} players · ${fee}`;
}

function sendFile(step: "preview" | "commit", clubId: number, file: File) {
  const options = {
    params: { path: { club_id: clubId } },
    body: { file },
    bodySerializer: () => {
      const form = new FormData();
      form.append("file", file, file.name);
      return form;
    },
  };
  return step === "preview"
    ? api.POST("/api/v1/clubs/{club_id}/imports/nights-divisions/preview/", options)
    : api.POST("/api/v1/clubs/{club_id}/imports/nights-divisions/commit/", options);
}

export function ImportNightsPage() {
  const { clubId } = useClub();
  const [step, setStep] = useState<Step>({ name: "choose" });
  const [error, setError] = useState<string | null>(null);

  async function run(call: () => Promise<{ data?: Result; error?: unknown; response: Response }>) {
    try {
      const { data, error: body, response } = await call();
      if (data) return data;
      // A commit that finds errors answers 400 with the rows, to show like a preview.
      if (response.status === 400 && body && typeof body === "object" && "rows" in body) return body as Result;
      const failed = formErrors(body);
      setError(failed.fields.file ?? failed.general ?? Object.values(failed.fields)[0] ?? "That didn't work.");
    } catch {
      setError(unreachable.general);
    }
    return null;
  }

  async function check(file: File) {
    setError(null);
    setStep({ name: "checking", file });
    const result = await run(() => sendFile("preview", clubId, file));
    setStep(result ? { name: "preview", file, result } : { name: "choose" });
  }

  async function commit(file: File, previous: Result) {
    setError(null);
    setStep({ name: "saving", file, result: previous });
    const result = await run(() => sendFile("commit", clubId, file));
    if (result?.committed) setStep({ name: "done", result });
    else setStep({ name: "preview", file, result: result ?? previous });
  }

  async function downloadTemplate(fileType: "xlsx" | "csv") {
    setError(null);
    try {
      const { data } = await api.GET("/api/v1/clubs/{club_id}/imports/nights-divisions/template/", {
        params: { path: { club_id: clubId }, query: { file_type: fileType } },
        parseAs: "blob",
      });
      if (!data) setError("Couldn't download the template. Try again.");
      else if (!saveFile(data as Blob, `nights-and-divisions.${fileType}`))
        setError("Download the template from League App in a web browser.");
    } catch {
      setError(unreachable.general);
    }
  }

  function chooseAgain() {
    setError(null);
    setStep({ name: "choose" });
  }

  const result = step.name === "preview" || step.name === "saving" || step.name === "done" ? step.result : null;
  const hasErrors = (result?.summary.errors ?? 0) > 0;
  const toApply = result ? result.summary.divisions_created + result.summary.divisions_updated : 0;

  return (
    <main className="la-screen">
      <SetupHeader title="Import Nights and Divisions" back="nights" />
      {error && <Banner status="cancelled" title={error} />}

      {(step.name === "choose" || step.name === "checking") && (
        <>
          <section className="la-stack-2" aria-labelledby="import-columns">
            <h2 id="import-columns" className="la-overline">
              One row per Division
            </h2>
            <ul className="la-group">
              <li className="la-item">
                <span className="la-item__body">
                  <span className="body-strong">Night</span>
                  <span className="caption la-muted">The weekday, like Tuesday or Tue</span>
                </span>
              </li>
              <li className="la-item">
                <span className="la-item__body">
                  <span className="body-strong">Division</span>
                  <span className="caption la-muted">The Division's name, like Division 1</span>
                </span>
              </li>
              <li className="la-item">
                <span className="la-item__body">
                  <span className="body-strong">Min players</span>
                  <span className="caption la-muted">Optional. Empty: the club's minimum</span>
                </span>
              </li>
              <li className="la-item">
                <span className="la-item__body">
                  <span className="body-strong">League fee</span>
                  <span className="caption la-muted">Optional, in rand. Empty: the club's fee</span>
                </span>
              </li>
            </ul>
            <p className="caption la-muted">
              Importing the same file again creates nothing twice. An empty cell keeps what a Division already has,
              and Divisions missing from the file stay as they are.
            </p>
          </section>
          <div className="la-actions">
            <button type="button" className="la-btn la-btn--quiet" onClick={() => void downloadTemplate("xlsx")}>
              Excel template
            </button>
            <button type="button" className="la-btn la-btn--quiet" onClick={() => void downloadTemplate("csv")}>
              CSV template
            </button>
          </div>
          <label className="la-btn la-btn--primary la-file">
            {step.name === "checking" ? `Checking ${step.file.name}` : "Choose a spreadsheet"}
            <input
              className="sr-only"
              type="file"
              accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
              disabled={step.name === "checking"}
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) void check(file);
              }}
            />
          </label>
        </>
      )}

      {result && step.name !== "done" && (
        <>
          {hasErrors ? (
            <Banner status="cancelled" title={count(result.summary.errors, "row has errors", "rows have errors")}>
              Nothing is imported until every row is right. Fix the file and choose it again.
            </Banner>
          ) : (
            <Banner status="info" title={summaryLine(result.summary, false)}>
              {"file" in step ? step.file.name : ""}
            </Banner>
          )}
          <ul className="la-group" aria-label="Rows">
            {result.rows.map((row) => (
              <li key={row.row} className="la-item">
                <span className="la-item__body">
                  <span className="body-strong">
                    {row.night === null ? "?" : WEEKDAYS[row.night]} · {row.division || "No Division"}
                  </span>
                  <span className="caption la-muted">
                    Row {row.row}
                    {row.errors.length === 0 && ` · ${rowDetail(row)}`}
                    {row.new_night && " · new Night"}
                  </span>
                  {row.errors.map((message) => (
                    <span key={message} className="la-field__error">
                      {message}
                    </span>
                  ))}
                </span>
                <StatusChip status={ACTIONS[row.action].status}>{ACTIONS[row.action].label}</StatusChip>
              </li>
            ))}
          </ul>
          <div className="la-actions">
            {!hasErrors && toApply > 0 && (
              <button
                type="button"
                className="la-btn la-btn--primary"
                disabled={step.name === "saving"}
                onClick={() => "file" in step && void commit(step.file, result)}
              >
                {step.name === "saving" ? "Importing" : `Import ${count(toApply, "Division", "Divisions")}`}
              </button>
            )}
            <button type="button" className="la-btn la-btn--secondary" onClick={chooseAgain}>
              Choose another file
            </button>
          </div>
        </>
      )}

      {step.name === "done" && (
        <>
          <Banner status="confirmed" title="Imported">
            {summaryLine(step.result.summary, true)}.
          </Banner>
          <Link className="la-btn la-btn--primary" to={`/clubs/${clubId}/setup/nights`}>
            See Nights and Divisions
          </Link>
        </>
      )}
    </main>
  );
}
