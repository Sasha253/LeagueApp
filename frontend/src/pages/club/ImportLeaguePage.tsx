// Import from Excel (FR-39, FR-53): the Admin uploads one workbook with any of the sheets
// Seasons, Nights and Divisions, and Fixtures, sees what each row would do, and confirms.
// The API checks every row and saves all or nothing; re-importing the same file changes
// nothing (docs/DECISIONS.md).

import { useState } from "react";
import { Link } from "react-router";
import { api, type Schemas } from "../../api/client";
import { formErrors, unreachable } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { StatusChip, type Status } from "../../components/StatusChip";
import { formatDate, formatMoment, formatRand, WEEKDAYS } from "../../format";
import { saveFile } from "../../native/files";
import { SetupHeader, useClub } from "./shared";

type Result = Schemas["LeagueImportResult"];
type Summary = Result["summary"];
type Action = Schemas["ImportActionEnum"];
type Step =
  | { name: "choose" }
  | { name: "checking"; file: File }
  | { name: "preview"; file: File; result: Result }
  | { name: "saving"; file: File; result: Result }
  | { name: "done"; result: Result };

/** A row of any sheet, as the screen lists it. */
type Line = { row: number; title: string; detail: string; errors: string[]; action: Action };

const ACTIONS: Record<Action, { status: Status; label: string }> = {
  create: { status: "confirmed", label: "New" },
  update: { status: "pending", label: "Changes" },
  unchanged: { status: "info", label: "No change" },
  error: { status: "cancelled", label: "Error" },
};

const SHEETS = [
  {
    name: "Seasons",
    columns: "Season, Starts on, Ends on",
    help: "A Season the club has takes the new dates, unless its Fixtures fall outside them",
  },
  {
    name: "Nights and Divisions",
    columns: "Night, Division, Min players, League fee",
    help: "Empty Min players or League fee: the club's, or what the Division has",
  },
  {
    name: "Fixtures",
    columns: "Season, Date, Time, Night, Division, Pitch, Home, Away, Friendly eligible",
    help: "A Team name the Division doesn't have adds the Team",
  },
];

const count = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** "1 new Season, 2 new Divisions, 6 new Teams, 12 new Fixtures, 3 unchanged" */
function summaryLine(summary: Summary, committed: boolean): string {
  const changed = (n: number, what: string) =>
    n && `${n} ${n === 1 ? what : `${what}s`} ${committed ? "changed" : n === 1 ? "changes" : "change"}`;
  const parts = [
    summary.seasons_created && count(summary.seasons_created, "new Season", "new Seasons"),
    changed(summary.seasons_updated, "Season"),
    summary.nights_created && count(summary.nights_created, "new Night", "new Nights"),
    summary.divisions_created && count(summary.divisions_created, "new Division", "new Divisions"),
    changed(summary.divisions_updated, "Division"),
    summary.teams_created && count(summary.teams_created, "new Team", "new Teams"),
    summary.fixtures_created && count(summary.fixtures_created, "new Fixture", "new Fixtures"),
    changed(summary.fixtures_updated, "Fixture"),
    summary.unchanged && `${summary.unchanged} unchanged`,
  ].filter(Boolean);
  return parts.length ? parts.join(", ") : "No rows to import";
}

const joined = (parts: (string | null | false)[]) => parts.filter(Boolean).join(" · ");

function seasonLines(rows: Result["seasons"]): Line[] {
  return rows.map((row) => ({
    ...row,
    title: row.name || "No name",
    detail: joined([row.starts_on && row.ends_on && `${formatDate(row.starts_on)} to ${formatDate(row.ends_on)}`]),
  }));
}

function divisionLines(rows: Result["divisions"]): Line[] {
  return rows.map((row) => ({
    ...row,
    title: `${row.night === null ? "?" : WEEKDAYS[row.night]} · ${row.division || "No Division"}`,
    detail: joined([
      row.errors.length === 0 && `Minimum ${row.min_players} players`,
      row.errors.length === 0 && (row.league_fee === null ? "club fee" : `${formatRand(row.league_fee)} per Team`),
      row.new_night && "new Night",
    ]),
  }));
}

function fixtureLines(rows: Result["fixtures"]): Line[] {
  return rows.map((row) => ({
    ...row,
    title: row.home && row.away ? `${row.home} vs ${row.away}` : row.home || row.away || "No teams",
    detail: joined([
      row.season,
      row.kick_off && formatMoment(row.kick_off),
      row.pitch,
      row.division,
      row.friendly_eligible && "Friendly-eligible",
      row.new_teams.length > 0 && `new ${row.new_teams.length === 1 ? "Team" : "Teams"}: ${row.new_teams.join(", ")}`,
    ]),
  }));
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
    ? api.POST("/api/v1/clubs/{club_id}/imports/league/preview/", options)
    : api.POST("/api/v1/clubs/{club_id}/imports/league/commit/", options);
}

function Rows({ title, lines }: { title: string; lines: Line[] }) {
  if (lines.length === 0) return null;
  return (
    <section className="la-stack-2" aria-label={title}>
      <h2 className="la-overline">{title}</h2>
      <ul className="la-group">
        {lines.map((line) => (
          <li key={line.row} className="la-item">
            <span className="la-item__body">
              <span className="body-strong">{line.title}</span>
              <span className="caption la-muted">
                Row {line.row}
                {line.detail && ` · ${line.detail}`}
              </span>
              {line.errors.map((message) => (
                <span key={message} className="la-field__error">
                  {message}
                </span>
              ))}
            </span>
            <StatusChip status={ACTIONS[line.action].status}>{ACTIONS[line.action].label}</StatusChip>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ImportLeaguePage() {
  const { clubId } = useClub();
  const [step, setStep] = useState<Step>({ name: "choose" });
  const [error, setError] = useState<string | null>(null);

  async function run(call: () => Promise<{ data?: Result; error?: unknown; response: Response }>) {
    try {
      const { data, error: body, response } = await call();
      if (data) return data;
      // A commit that finds errors answers 400 with the rows, to show like a preview.
      if (response.status === 400 && body && typeof body === "object" && "summary" in body) return body as Result;
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

  async function downloadTemplate() {
    setError(null);
    try {
      const { data } = await api.GET("/api/v1/clubs/{club_id}/imports/league/template/", {
        params: { path: { club_id: clubId } },
        parseAs: "blob",
      });
      if (!data) setError("Couldn't download the template. Try again.");
      else if (!saveFile(data as Blob, "league-import.xlsx"))
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
  const toApply = result ? result.summary.rows - result.summary.unchanged - result.summary.errors : 0;

  return (
    <main className="la-screen">
      <SetupHeader title="Import from Excel" />
      {error && <Banner status="cancelled" title={error} />}

      {(step.name === "choose" || step.name === "checking") && (
        <>
          <section className="la-stack-2" aria-labelledby="import-sheets">
            <h2 id="import-sheets" className="la-overline">
              One workbook, a sheet for each
            </h2>
            <ul className="la-group">
              {SHEETS.map((sheet) => (
                <li key={sheet.name} className="la-item">
                  <span className="la-item__body">
                    <span className="body-strong">{sheet.name}</span>
                    <span className="caption">{sheet.columns}</span>
                    <span className="caption la-muted">{sheet.help}</span>
                  </span>
                </li>
              ))}
            </ul>
            <p className="caption la-muted">
              Leave out any sheet you don't need. A Team the import adds is confirmed and charged the league fee, and the
              first Player to join it is its Captain. Importing the same file again creates nothing twice, nothing missing
              from the file is deleted, and the import never moves a Fixture: reschedule it instead.
            </p>
          </section>
          <button type="button" className="la-btn la-btn--quiet" onClick={() => void downloadTemplate()}>
            Excel template
          </button>
          <label className="la-btn la-btn--primary la-file">
            {step.name === "checking" ? `Checking ${step.file.name}` : "Choose a workbook"}
            <input
              className="sr-only"
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
          <Rows title="Seasons" lines={seasonLines(result.seasons)} />
          <Rows title="Nights and Divisions" lines={divisionLines(result.divisions)} />
          <Rows title="Fixtures" lines={fixtureLines(result.fixtures)} />
          <div className="la-actions">
            {!hasErrors && toApply > 0 && (
              <button
                type="button"
                className="la-btn la-btn--primary"
                disabled={step.name === "saving"}
                onClick={() => "file" in step && void commit(step.file, result)}
              >
                {step.name === "saving" ? "Importing" : `Import ${count(toApply, "row", "rows")}`}
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
          <div className="la-actions">
            <Link className="la-btn la-btn--secondary" to={`/clubs/${clubId}/setup/seasons`}>
              Seasons
            </Link>
            <Link className="la-btn la-btn--secondary" to={`/clubs/${clubId}/setup/nights`}>
              Nights and Divisions
            </Link>
            <Link className="la-btn la-btn--primary" to={`/clubs/${clubId}/fixtures`}>
              Fixtures
            </Link>
          </div>
        </>
      )}
    </main>
  );
}
