// What the Fixture screens share: how a Fixture's status is labelled, and the match card.
// Kick-off comes from the API as a moment and is shown in South African time, 24-hour.

import type { ReactNode } from "react";
import type { Schemas } from "../../api/client";
import { StatusChip, type Status } from "../../components/StatusChip";
import { formatDate, formatTime, localDate, WEEKDAYS } from "../../format";

export type FixtureStatus = Schemas["FixtureStatusEnum"];
type FixtureLike = Pick<
  Schemas["MyFixture"],
  "kick_off" | "pitch" | "home_team" | "away_team" | "division" | "weekday" | "status" | "friendly_eligible"
>;

export const FIXTURE_STATUS: Record<FixtureStatus, { status: Status; label: string }> = {
  scheduled: { status: "info", label: "Scheduled" },
  confirming: { status: "pending", label: "Confirming" },
  ready: { status: "confirmed", label: "Ready" },
  one_team_out: { status: "cancelled", label: "One team out" },
  replacement_offered: { status: "pending", label: "Finding an opponent" },
  friendly: { status: "info", label: "Friendly" },
  cancelled: { status: "cancelled", label: "Cancelled" },
  played: { status: "confirmed", label: "Played" },
};

export function FixtureStatusChip({ status }: { status: FixtureStatus }) {
  const { status: tone, label } = FIXTURE_STATUS[status];
  return <StatusChip status={tone}>{label}</StatusChip>;
}

/** "Tue 27 Oct" for a kick-off, in South Africa. */
export function kickOffDate(kickOff: string): string {
  return formatDate(localDate(kickOff));
}

/** "Red Lions vs Old Boys" */
export function matchName(fixture: Pick<FixtureLike, "home_team" | "away_team">): string {
  return `${fixture.home_team.name} vs ${fixture.away_team.name}`;
}

/** MatchCard from the design system: date and pitch, the teams, kick-off in scoreboard type. */
export function MatchCard({ fixture, children }: { fixture: FixtureLike; children?: ReactNode }) {
  return (
    <article className="la-card la-stack-2" aria-label={matchName(fixture)}>
      <div className="la-row">
        <p className="la-overline">
          {kickOffDate(fixture.kick_off)} · {fixture.pitch.name}
        </p>
        <FixtureStatusChip status={fixture.status} />
      </div>
      <p className="la-fixture">
        {fixture.home_team.name} <span className="la-vs">vs</span> {fixture.away_team.name}
      </p>
      <div className="la-row">
        <span className="la-time">{formatTime(fixture.kick_off)}</span>
        <span className="la-meta">
          <span>{WEEKDAYS[fixture.weekday]}</span>
          <span>{fixture.division.name}</span>
          {fixture.friendly_eligible && <span>Friendly-eligible</span>}
        </span>
      </div>
      {children}
    </article>
  );
}
