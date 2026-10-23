// Captains' requests to cancel or postpone a match (FR-18): how they are labelled, shared by
// the Captain's and the Admin's screens. What a request does is decided by the backend.

import type { Schemas } from "../../api/client";
import { StatusChip, type Status } from "../../components/StatusChip";
import { formatMoment } from "../../format";

export type CaptainRequest = Schemas["CaptainRequest"];
export type RequestKind = CaptainRequest["kind"];

export const REQUEST_KIND: Record<RequestKind, string> = {
  cancel: "Cancel",
  postpone: "Postpone",
};

const REQUEST_STATUS: Record<CaptainRequest["status"], { status: Status; label: string }> = {
  pending: { status: "pending", label: "Waiting for the Admin" },
  accepted: { status: "confirmed", label: "Accepted" },
  declined: { status: "cancelled", label: "Declined" },
  withdrawn: { status: "info", label: "Withdrawn" },
  closed: { status: "info", label: "No longer applies" },
};

export function RequestStatus({ request }: { request: Pick<CaptainRequest, "status"> }) {
  const { status, label } = REQUEST_STATUS[request.status];
  return <StatusChip status={status}>{label}</StatusChip>;
}

/** "Red Lions asks to cancel" */
export function requestTitle(request: Pick<CaptainRequest, "team" | "kind">): string {
  return `${request.team.name} asks to ${request.kind === "cancel" ? "cancel" : "postpone"}`;
}

/** "Sent Mon 26 Oct · 08:00 by Thandi" and, once decided, by whom and their note. */
export function requestDetail(request: CaptainRequest): string {
  const parts = [`Sent ${formatMoment(request.requested_at)} by ${request.requested_by_name}`];
  if (request.decided_at && request.status !== "pending") {
    const by = request.decided_by_name ? ` by ${request.decided_by_name}` : "";
    parts.push(`${REQUEST_STATUS[request.status].label} ${formatMoment(request.decided_at)}${by}`);
  }
  if (request.note) parts.push(request.note);
  return parts.join(" · ");
}
