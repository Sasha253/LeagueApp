// What the Team screens share: how a Team and a request to join are labelled, and the
// screen header with its back link.

import { Link } from "react-router";
import type { Schemas } from "../../api/client";
import { StatusChip, type Status } from "../../components/StatusChip";
import { WEEKDAYS } from "../../format";

export type Team = Schemas["Team"];
export type JoinRequest = Schemas["JoinRequest"];

const TEAM_STATUS: Record<Team["status"], { status: Status; label: string }> = {
  requested: { status: "pending", label: "Waiting for the Admin" },
  active: { status: "confirmed", label: "Confirmed" },
  declined: { status: "cancelled", label: "Declined" },
};

const JOIN_STATUS: Record<NonNullable<JoinRequest["status"]>, { status: Status; label: string }> = {
  pending: { status: "pending", label: "Waiting for the Captain" },
  accepted: { status: "confirmed", label: "Accepted" },
  declined: { status: "cancelled", label: "Declined" },
  withdrawn: { status: "info", label: "Withdrawn" },
};

export function TeamStatus({ team }: { team: Pick<Team, "status"> }) {
  const { status, label } = TEAM_STATUS[team.status];
  return <StatusChip status={status}>{label}</StatusChip>;
}

export function JoinStatus({ request }: { request: Pick<JoinRequest, "status"> }) {
  const { status, label } = JOIN_STATUS[request.status ?? "pending"];
  return <StatusChip status={status}>{label}</StatusChip>;
}

/** "Tuesday · Division 2 · Spring 2026 · Club A" */
export function teamLine(team: Team): string {
  return [WEEKDAYS[team.weekday], team.division.name, team.season.name, team.club.name].join(" · ");
}

export function playersLine(count: number): string {
  return count === 1 ? "1 player" : `${count} players`;
}

export const POSITION_LABELS: Record<string, string> = {
  outfield: "Outfield",
  goalkeeper: "Goalkeeper",
  both: "Outfield and goalkeeper",
};

/** Back link, title and an optional line under it. */
export function ScreenHeader({
  title,
  back,
  caption,
}: {
  title: string;
  back: { label: string; to: string };
  caption?: string;
}) {
  return (
    <div className="la-stack-2">
      <Link className="la-btn la-btn--quiet la-back" to={back.to}>
        {back.label}
      </Link>
      <h1 className="title-1">{title}</h1>
      {caption && <p className="caption la-muted">{caption}</p>}
    </div>
  );
}
