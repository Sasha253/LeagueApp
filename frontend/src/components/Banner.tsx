// Banner (proposed component, docs/DECISIONS.md): the strong status colour on its -soft
// tint, with an icon and a title so it never relies on colour alone.

import type { ReactNode } from "react";
import { ICON_PATHS, type Status } from "./StatusChip";

type Props = { status: Status; title: string; children?: ReactNode };

export function Banner({ status, title, children }: Props) {
  return (
    <div className={`la-banner la-banner--${status}`} role={status === "cancelled" ? "alert" : "status"}>
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d={ICON_PATHS[status]} />
      </svg>
      <div className="la-banner__body">
        <span className="body-strong la-banner__title">{title}</span>
        {children && <span className="caption">{children}</span>}
      </div>
    </div>
  );
}
