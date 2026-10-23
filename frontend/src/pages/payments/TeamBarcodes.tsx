// A Team's Payment Barcodes as an Admin of its club sees them (PRD "Barcode authorisation",
// NFR Barcode integrity): each one's state and why, how often it was scanned, issuing or
// reissuing one (only for a paid Team: the backend says no otherwise) and revoking one with
// a reason.

import { useState, type FormEvent } from "react";
import { api, type Schemas } from "../../api/client";
import type { FormErrors } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { StatusChip, type Status } from "../../components/StatusChip";
import { TextField } from "../../components/TextField";
import { formatDate, formatMoment } from "../../format";
import { NO_ERRORS, send, useLoad } from "../club/shared";

type AdminBarcode = Schemas["AdminBarcode"];

const STATE_CHIPS: Record<AdminBarcode["state"], { status: Status; label: string }> = {
  valid: { status: "confirmed", label: "Valid" },
  not_genuine: { status: "cancelled", label: "Not genuine" },
  revoked: { status: "cancelled", label: "Revoked" },
  expired: { status: "info", label: "No longer valid" },
  unpaid: { status: "pending", label: "Not paid" },
  inactive: { status: "cancelled", label: "Team not active" },
  no_match: { status: "info", label: "No match" },
  not_found: { status: "cancelled", label: "Not found" },
};

function validFor(barcode: AdminBarcode): string {
  return barcode.fixture
    ? `Match ${formatMoment(barcode.fixture.kick_off)}`
    : `${barcode.season.name} Season, until ${formatDate(barcode.valid_until)}`;
}

type Props = {
  teamId: number;
  teamName: string;
  /** What the Team has paid: recording cash can issue a Barcode, so a change reloads them. */
  paid: string;
};

export function TeamBarcodes({ teamId, teamName, paid }: Props) {
  const [barcodes, reload] = useLoad(
    () => api.GET("/api/v1/teams/{team_id}/barcodes/", { params: { path: { team_id: teamId } } }),
    `team-barcodes-${teamId}-${paid}`,
  );
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const list = barcodes.state === "ok" ? barcodes.data : [];
  const hasValid = list.some((barcode) => barcode.state === "valid");

  async function issue() {
    setDone(null);
    setBusy(true);
    const failed = await send(() =>
      api.POST("/api/v1/teams/{team_id}/barcodes/", { params: { path: { team_id: teamId } } }),
    );
    setBusy(false);
    setErrors(failed ?? NO_ERRORS);
    if (!failed) {
      setDone(`New Payment Barcode sent to the Captain of ${teamName}.`);
      reload();
    }
  }

  return (
    <section className="la-stack" aria-labelledby="barcodes">
      <h2 id="barcodes" className="la-overline">
        Payment Barcodes
      </h2>
      {barcodes.state === "loading" && (
        <p className="caption la-muted" role="status">
          Loading Payment Barcodes
        </p>
      )}
      {(barcodes.state === "error" || barcodes.state === "forbidden") && (
        <Banner status="cancelled" title="Couldn't load the Payment Barcodes">
          <button type="button" className="la-btn la-btn--quiet" onClick={reload}>
            Retry
          </button>
        </Banner>
      )}
      {barcodes.state === "ok" && list.length === 0 && (
        <p className="caption la-muted">None yet. One is issued when {teamName} has paid.</p>
      )}
      {list.length > 0 && (
        <ul className="la-group" aria-label="Payment Barcodes">
          {list.map((barcode) => (
            <BarcodeRow
              key={barcode.id}
              barcode={barcode}
              onRevoked={() => {
                setDone(null);
                reload();
              }}
            />
          ))}
        </ul>
      )}
      {errors.general && <Banner status="cancelled" title={errors.general} />}
      {done && <Banner status="confirmed" title={done} />}
      {barcodes.state === "ok" && (
        <button
          type="button"
          className="la-btn la-btn--secondary la-btn--block"
          disabled={busy}
          onClick={() => void issue()}
        >
          {hasValid ? "Reissue Payment Barcode" : "Issue Payment Barcode"}
        </button>
      )}
    </section>
  );
}

function BarcodeRow({ barcode, onRevoked }: { barcode: AdminBarcode; onRevoked: () => void }) {
  const [revoking, setRevoking] = useState(false);
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [busy, setBusy] = useState(false);
  const chip = STATE_CHIPS[barcode.state];

  async function revoke(event: FormEvent) {
    event.preventDefault();
    if (!reason.trim()) {
      setErrors({ fields: { reason: "Say why it no longer counts." }, general: null });
      return;
    }
    setBusy(true);
    const failed = await send(() =>
      api.POST("/api/v1/barcodes/{barcode_id}/revoke/", {
        params: { path: { barcode_id: barcode.id } },
        body: { reason: reason.trim() },
      }),
    );
    setBusy(false);
    setErrors(failed ?? NO_ERRORS);
    if (!failed) {
      setRevoking(false);
      onRevoked();
    }
  }

  return (
    <li className="la-item">
      <div className="la-item__body la-stack-2">
      <div className="la-row">
        <span className="body-strong">{barcode.display_code}</span>
        <StatusChip status={chip.status}>{chip.label}</StatusChip>
      </div>
      <span className="caption la-muted">{validFor(barcode)}</span>
      {barcode.reason && <span className="caption">{barcode.reason}</span>}
      <span className="caption la-muted">
        Issued {formatMoment(barcode.issued_at)}
        {barcode.issued_by ? ` by ${barcode.issued_by.name}` : " on payment"} · scanned {barcode.scans}{" "}
        {barcode.scans === 1 ? "time" : "times"}
      </span>
      {barcode.revoked_at === null &&
        (revoking ? (
          <form className="la-stack-2" onSubmit={(event) => void revoke(event)} noValidate>
            <TextField
              label="Why revoke it?"
              value={reason}
              maxLength={300}
              onChange={(event) => setReason(event.target.value)}
              error={errors.fields.reason}
              help="It stops counting at the gate at once. The Captain needs a new one."
            />
            {errors.general && <Banner status="cancelled" title={errors.general} />}
            <div className="la-row">
              <button type="button" className="la-btn la-btn--quiet" onClick={() => setRevoking(false)}>
                Keep it
              </button>
              <button type="submit" className="la-btn la-btn--danger" disabled={busy}>
                Revoke
              </button>
            </div>
          </form>
        ) : (
          <button type="button" className="la-btn la-btn--quiet la-btn--sm" onClick={() => setRevoking(true)}>
            Revoke
          </button>
        ))}
      </div>
    </li>
  );
}
