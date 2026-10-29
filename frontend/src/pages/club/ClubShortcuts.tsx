// The buttons that open a Club's screens, for a role held there: on Profile for each role
// the user holds, and on All clubs for a superuser, who opens every Club as its Admin. An
// Admin opens Club home, which reaches every Admin screen, or goes straight to the gate
// scanner; a Referee has the scanner only.

import { Link } from "react-router";

const OPEN = { path: "", label: "Open club", aria: "Open" };
const SCAN = { path: "/scan", label: "Scan", aria: "Scan at" };
const SCREENS = { admin: [OPEN, SCAN], referee: [SCAN] };

export function ClubShortcuts({
  clubId,
  clubName,
  role,
}: {
  clubId: number;
  clubName: string;
  role: "admin" | "referee";
}) {
  return (
    <span className="la-confirm">
      {SCREENS[role].map((screen) => (
        <Link
          key={screen.path}
          className="la-btn la-btn--secondary la-btn--sm"
          to={`/clubs/${clubId}${screen.path}`}
          aria-label={`${screen.aria} ${clubName}`}
        >
          {screen.label}
        </Link>
      ))}
    </span>
  );
}
