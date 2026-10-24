// The income planner (PRD FR-47; Screens.md Admin 5, FinanceSummary's week-by-week planner;
// design/src/screens/f14-finances.mjs): league income expected week by week from the
// fixture list, with what Teams have paid overlaid so a shortfall shows early. Every
// amount is the API's (chunk 27); bar heights are only drawn from them.

import { useState } from "react";
import { api, type Schemas } from "../../api/client";
import { formatDate, formatRand } from "../../format";
import { LoadState, useClub, useLoad } from "../club/shared";
import { NOT_AN_ADMIN, Stat } from "./shared";

type Plan = Schemas["Planner"];
type Week = Schemas["PlannerWeek"];

export type Scope = { season: number; night: number | null; division: number | null };

export function scopeQuery({ season, night, division }: Scope) {
  return { season, ...(night !== null && { night }), ...(division !== null && { division }) };
}

export function Planner({ scope, label, version }: { scope: Scope; label: string; version: number }) {
  const { clubId } = useClub();
  const [plan, reload] = useLoad(
    () =>
      api.GET("/api/v1/clubs/{club_id}/finance/planner/", {
        params: { path: { club_id: clubId }, query: scopeQuery(scope) },
      }),
    `finance-planner-${clubId}-${scope.season}-${scope.night}-${scope.division}-${version}`,
  );
  return (
    <LoadState result={plan} retry={reload} what="planner" forbidden={NOT_AN_ADMIN}>
      {(data) => <PlannerCard plan={data} label={label} />}
    </LoadState>
  );
}

/** "Week 7 is R 140 short; season R 490 behind." */
export function reading(plan: Plan): string {
  const first = plan.weeks[0];
  if (plan.weeks.length === 0) return "This Season has no weeks.";
  if (first && !first.is_due) return `The Season starts ${formatDate(first.starts_on)}; nothing is due yet.`;
  const now = plan.weeks.find((w) => w.is_current);
  const parts: string[] = [];
  if (now) {
    parts.push(
      Number(now.short) > 0 ? `Week ${now.week} is ${formatRand(now.short)} short` : `Week ${now.week} is paid`,
    );
  }
  parts.push(Number(plan.behind) > 0 ? `season ${formatRand(plan.behind)} behind` : "season on track");
  const text = parts.join("; ");
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}.`;
}

function percent(amount: string, peak: number): string {
  return peak > 0 ? `${Math.round((Number(amount) / peak) * 100)}%` : "0%";
}

function PlannerCard({ plan, label }: { plan: Plan; label: string }) {
  const [open, setOpen] = useState(false);
  const peak = Math.max(0, ...plan.weeks.map((w) => Number(w.expected)));
  const text = reading(plan);
  return (
    <section className="la-card la-stack" aria-label={`Planner, ${label}`}>
      <p className="la-overline">Week by week</p>
      <div className="la-stats">
        <Stat label="Due to date" amount={plan.due_to_date} />
        <Stat label="Paid to date" amount={plan.covered_to_date} />
        <Stat label="Behind" amount={plan.behind} owed />
        <Stat label="Season expected" amount={plan.season_expected} />
      </div>
      {peak > 0 ? (
        <div className="la-planner">
          <div className="la-planner__key" aria-hidden="true">
            <span>
              <i className="la-planner__swatch-exp" />
              Expected
            </span>
            <span>
              <i className="la-planner__swatch-got" />
              Paid
            </span>
          </div>
          <div className="la-planner__bars" role="img" aria-label={text}>
            {plan.weeks.map((w) => (
              <div key={w.week} className={`la-planner__week${w.is_current ? " la-planner__week--now" : ""}`}>
                <div className="la-planner__exp" style={{ height: percent(w.expected, peak) }} />
                {Number(w.covered) > 0 && <div className="la-planner__got" style={{ height: percent(w.covered, peak) }} />}
              </div>
            ))}
          </div>
          <div className="la-planner__axis" aria-hidden="true">
            {plan.weeks.map((w) => (
              <span key={w.week} className={w.is_current ? "la-planner__now" : undefined}>
                {w.week}
              </span>
            ))}
          </div>
          <span className="la-progress__hint">{text}</span>
        </div>
      ) : (
        <p className="caption la-muted">No league fees fall in a week yet: they are spread over the fixture list.</p>
      )}
      {Number(plan.unscheduled) > 0 && (
        <p className="caption la-muted">
          {formatRand(plan.unscheduled)} is from Teams with no fixtures yet, so it is in no week.
        </p>
      )}
      <button type="button" className="la-btn la-btn--quiet la-btn--sm" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? "Hide weeks" : "Show weeks"}
      </button>
      {open && (
        <ul className="la-group" aria-label="Weeks">
          {plan.weeks.map((w) => (
            <WeekRow key={w.week} week={w} />
          ))}
        </ul>
      )}
    </section>
  );
}

function WeekRow({ week: w }: { week: Week }) {
  const matches = `${w.matches} ${w.matches === 1 ? "match" : "matches"}`;
  const money = [`${formatRand(w.covered)} paid`];
  if (Number(w.short) > 0) money.push(`${formatRand(w.short)} short`);
  money.push(`${formatRand(w.received)} received that week`);
  return (
    <li className="la-item">
      <span className="la-item__body">
        <span className={w.is_current ? "body-strong" : "body"}>
          Week {w.week}
          {w.is_current && " · this week"}
        </span>
        <span className="caption la-muted">
          {formatDate(w.starts_on)} to {formatDate(w.ends_on)} · {matches}
        </span>
        <span className="caption la-muted">{money.join(" · ")}</span>
      </span>
      <span className="body-strong">{formatRand(w.expected)}</span>
    </li>
  );
}
