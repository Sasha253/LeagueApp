// The buttons that open a Club's screens, for a role held there: on Profile for each role
// the user holds, and on All clubs for a superuser, who opens every Club as its Admin.

import { Link } from "react-router";

const ADMIN_SCREENS = [
  { path: "scan", label: "Scan", aria: "Scan at" },
  { path: "tonight", label: "Tonight", aria: "Tonight at" },
  { path: "fixtures", label: "Fixtures", aria: "Fixtures for" },
  { path: "teams", label: "Team requests", aria: "Team requests for" },
  { path: "bookings", label: "Bookings", aria: "Bookings at" },
  { path: "payments", label: "Payments", aria: "Payments at" },
  { path: "finances", label: "Finances", aria: "Finances for" },
  { path: "setup", label: "Club setup", aria: "Club setup for" },
];

const SCREENS = { admin: ADMIN_SCREENS, referee: ADMIN_SCREENS.slice(0, 1) };

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
          to={`/clubs/${clubId}/${screen.path}`}
          aria-label={`${screen.aria} ${clubName}`}
        >
          {screen.label}
        </Link>
      ))}
    </span>
  );
}
