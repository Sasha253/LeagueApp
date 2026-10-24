// Export for the accountant (PRD FR-51; Screens.md Admin 5 "Export to CSV / Excel"): every
// ledger entry the club recorded between two days, as an Excel or CSV file. The API builds
// the file (chunk 28); this screen only picks the days and saves what comes back.

import { useState } from "react";
import { api } from "../../api/client";
import { formErrors, unreachable, type FormErrors } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { TextField } from "../../components/TextField";
import { formatDate, localDate } from "../../format";
import { saveFile } from "../../native/files";
import { useClub } from "../club/shared";
import { ScreenHeader } from "../teams/shared";
import { NOT_AN_ADMIN } from "./shared";

type FileType = "xlsx" | "csv";

const NO_ERRORS: FormErrors = { fields: {}, general: null };

/** The South African month so far: its first day and today. Only the fields' starting values. */
export function thisMonthSoFar(now = new Date()): { starts_on: string; ends_on: string } {
  const today = localDate(now.toISOString());
  return { starts_on: `${today.slice(0, 8)}01`, ends_on: today };
}

export function ExportPage() {
  const { clubId, clubName } = useClub();
  const [range, setRange] = useState(thisMonthSoFar);
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [busy, setBusy] = useState<FileType | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  async function download(fileType: FileType) {
    setErrors(NO_ERRORS);
    setSaved(null);
    if (!range.starts_on || !range.ends_on) {
      setErrors({
        fields: {
          ...(!range.starts_on && { starts_on: "Pick the first day." }),
          ...(!range.ends_on && { ends_on: "Pick the last day." }),
        },
        general: null,
      });
      return;
    }
    setBusy(fileType);
    try {
      const { data, error, response } = await api.GET("/api/v1/clubs/{club_id}/finance/export/", {
        params: { path: { club_id: clubId }, query: { ...range, file_type: fileType } },
        parseAs: "blob",
      });
      if (response.status === 403) setErrors({ fields: {}, general: NOT_AN_ADMIN });
      else if (error || !data) setErrors(error ? formErrors(error) : { fields: {}, general: "Couldn't export. Try again." });
      else if (!saveFile(data as Blob, `ledger-${range.starts_on}-to-${range.ends_on}.${fileType}`))
        setErrors({ fields: {}, general: "Export from League App in a web browser." });
      else setSaved(fileType === "xlsx" ? "Excel" : "CSV");
    } catch {
      setErrors(unreachable);
    } finally {
      setBusy(null);
    }
  }

  const period =
    range.starts_on && range.ends_on ? `${formatDate(range.starts_on)} to ${formatDate(range.ends_on)}` : null;

  return (
    <main className="la-screen">
      <ScreenHeader
        title="Export for accountant"
        back={{ label: "Finances", to: `/clubs/${clubId}/finances` }}
        caption={clubName}
      />
      <p className="body la-muted">
        Every ledger entry recorded between the two days, South African time: charges, payments, credits, refunds and
        corrections, one row each. Money in and out shows card and cash only.
      </p>
      <form className="la-stack" noValidate onSubmit={(event) => event.preventDefault()}>
        <TextField
          label="From"
          type="date"
          value={range.starts_on}
          onChange={(event) => setRange({ ...range, starts_on: event.target.value })}
          error={errors.fields.starts_on}
        />
        <TextField
          label="To"
          type="date"
          value={range.ends_on}
          onChange={(event) => setRange({ ...range, ends_on: event.target.value })}
          error={errors.fields.ends_on}
        />
        {errors.fields.file_type && <Banner status="cancelled" title={errors.fields.file_type} />}
        {errors.general && <Banner status="cancelled" title={errors.general} />}
        {saved && period && <Banner status="confirmed" title={`${saved} file downloaded`}>{period}</Banner>}
        <div className="la-actions">
          <button
            type="button"
            className="la-btn la-btn--primary"
            disabled={busy !== null}
            onClick={() => void download("xlsx")}
          >
            Download Excel
          </button>
          <button
            type="button"
            className="la-btn la-btn--secondary"
            disabled={busy !== null}
            onClick={() => void download("csv")}
          >
            Download CSV
          </button>
        </div>
      </form>
    </main>
  );
}
