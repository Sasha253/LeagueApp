// Import Fixtures (FR-53), the same flow as Import Nights and Divisions: the Admin picks a
// Season, uploads a spreadsheet, sees what each row would do, and confirms. The API checks
// every row and saves all or nothing; re-importing the same file changes nothing.

import { useState } from "react";
import { Link } from "react-router";
import { api, type Schemas } from "../../api/client";
import { formErrors, unreachable } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { StatusChip, type Status } from "../../components/StatusChip";
import { formatMoment, WEEKDAYS } from "../../format";
import { saveFile } from "../../native/files";
import { LoadState, useClub, useLoad } from "../club/shared";
import { ScreenHeader } from "../teams/shared";

type Result = Schemas["FixtureImportResult"];
type Row = Schemas["FixtureImportRow"];
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

const COLUMNS = [
  ["Date", "Like 2026-10-27, 27/10/2026 or 27 Oct 2026"],
  ["Time", "Kick-off, 24-hour, like 19:40"],
  ["Night", "Optional. Must be the date's weekday"],
  ["Division", "The Division's name, like Division 2"],
  ["Pitch", "As named in Club setup"],
  ["Home and Away", "Confirmed Teams of that Division this Season"],
  ["Friendly eligible", "Optional: yes or no. Empty: no"],
];

const count = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

function summaryLine(summary: Result["summary"], committed: boolean): string {
  const [changesOne, changesMany] = committed
    ? ["Fixture changed", "Fixtures changed"]
    : ["Fixture changes", "Fixtures change"];
  const parts = [
    summary.fixtures_created && count(summary.fixtures_created, "new Fixture", "new Fixtures"),
    summary.fixtures_updated && count(summary.fixtures_updated, changesOne, changesMany),
    summary.unchanged && `${summary.unchanged} unchanged`,
  ].filter(Boolean);
  return parts.length ? parts.join(", ") : "No rows to import";
}

function rowTitle(row: Row): string {
  if (row.home && row.away) return `${row.home} vs ${row.away}`;
  return row.home || row.away || "No teams";
}

function rowDetail(row: Row): string {
  return [
    row.kick_off ? formatMoment(row.kick_off) : null,
    row.pitch || null,
    row.night === null ? null : WEEKDAYS[row.night],
    row.division || null,
    row.friendly_eligible ? "Friendly-eligible" : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

function sendFile(step: "preview" | "commit", clubId: number, season: number, file: File) {
  const options = {
    params: { path: { club_id: clubId } },
    body: { season, file },
    bodySerializer: () => {
      const form = new FormData();
      form.append("season", String(season));
      form.append("file", file, file.name);
      return form;
    },
  };
  return step === "preview"
    ? api.POST("/api/v1/clubs/{club_id}/imports/fixtures/preview/", options)
    : api.POST("/api/v1/clubs/{club_id}/imports/fixtures/commit/", options);
}

export function ImportFixturesPage() {
  const { clubId, clubName } = useClub();
  const [seasons, reloadSeasons] = useLoad(
    () => api.GET("/api/v1/seasons/", { params: { query: { club: clubId } } }),
    `open-seasons-${clubId}`,
  );
  const [season, setSeason] = useState<number | null>(null);
  const [step, setStep] = useState<Step>({ name: "choose" });
  const [error, setError] = useState<string | null>(null);

  async function run(call: () => Promise<{ data?: Result; error?: unknown; response: Response }>) {
    try {
      const { data, error: body, response } = await call();
      if (data) return data;
      // A commit that finds errors answers 400 with the rows, to show like a preview.
      if (response.status === 400 && body && typeof body === "object" && "rows" in body) return body as Result;
      const failed = formErrors(body);
      setError(
        failed.fields.file ??
          failed.fields.season ??
          failed.general ??
          Object.values(failed.fields)[0] ??
          "That didn't work.",
      );
    } catch {
      setError(unreachable.general);
    }
    return null;
  }

  async function check(file: File, seasonId: number) {
    setError(null);
    setStep({ name: "checking", file });
    const result = await run(() => sendFile("preview", clubId, seasonId, file));
    setStep(result ? { name: "preview", file, result } : { name: "choose" });
  }

  async function commit(file: File, previous: Result, seasonId: number) {
    setError(null);
    setStep({ name: "saving", file, result: previous });
    const result = await run(() => sendFile("commit", clubId, seasonId, file));
    if (result?.committed) setStep({ name: "done", result });
    else setStep({ name: "preview", file, result: result ?? previous });
  }

  async function downloadTemplate(fileType: "xlsx" | "csv") {
    setError(null);
    try {
      const { data } = await api.GET("/api/v1/clubs/{club_id}/imports/fixtures/template/", {
        params: { path: { club_id: clubId }, query: { file_type: fileType } },
        parseAs: "blob",
      });
      if (!data) setError("Couldn't download the template. Try again.");
      else if (!saveFile(data as Blob, `fixtures.${fileType}`))
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
  const toApply = result ? result.summary.fixtures_created + result.summary.fixtures_updated : 0;
  const choosing = step.name === "choose" || step.name === "checking";

  return (
    <main className="la-screen">
      <ScreenHeader
        title="Import fixtures"
        back={{ label: "Fixtures", to: `/clubs/${clubId}/fixtures` }}
        caption={clubName}
      />
      {error && <Banner status="cancelled" title={error} />}

      {choosing && (
        <>
          <LoadState result={seasons} retry={reloadSeasons} what="Seasons">
            {(list) =>
              list.length === 0 ? (
                <Banner status="pending" title="No Season to import into">
                  Add a Season in Club setup first.
                </Banner>
              ) : (
                <fieldset className="la-fieldset la-stack-2">
                  <legend className="la-overline">Season</legend>
                  <div className="la-choices">
                    {list.map((s) => (
                      <ChoiceChip key={s.id} pressed={season === s.id} onToggle={() => setSeason(s.id)}>
                        {s.name}
                      </ChoiceChip>
                    ))}
                  </div>
                </fieldset>
              )
            }
          </LoadState>
          <section className="la-stack-2" aria-labelledby="import-columns">
            <h2 id="import-columns" className="la-overline">
              One row per Fixture
            </h2>
            <ul className="la-group">
              {COLUMNS.map(([name, help]) => (
                <li key={name} className="la-item">
                  <span className="la-item__body">
                    <span className="body-strong">{name}</span>
                    <span className="caption la-muted">{help}</span>
                  </span>
                </li>
              ))}
            </ul>
            <p className="caption la-muted">
              Importing the same file again creates nothing twice. Fixtures missing from the file stay as they are, and
              the import never moves a Fixture: reschedule it instead.
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
            {step.name === "checking"
              ? `Checking ${step.file.name}`
              : season === null
                ? "Pick a Season, then a spreadsheet"
                : "Choose a spreadsheet"}
            <input
              className="sr-only"
              type="file"
              accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
              disabled={step.name === "checking" || season === null}
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file && season !== null) void check(file, season);
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
                  <span className="body-strong">{rowTitle(row)}</span>
                  <span className="caption la-muted">
                    Row {row.row}
                    {rowDetail(row) && ` · ${rowDetail(row)}`}
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
            {!hasErrors && toApply > 0 && season !== null && (
              <button
                type="button"
                className="la-btn la-btn--primary"
                disabled={step.name === "saving"}
                onClick={() => "file" in step && void commit(step.file, result, season)}
              >
                {step.name === "saving" ? "Importing" : `Import ${count(toApply, "Fixture", "Fixtures")}`}
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
          <Link className="la-btn la-btn--primary" to={`/clubs/${clubId}/fixtures`}>
            See fixtures
          </Link>
        </>
      )}
    </main>
  );
}
