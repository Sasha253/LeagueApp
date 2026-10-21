// StatusChip from the design system (design/src/ds/README.md, components/StatusChip):
// always an icon and a word, never colour alone. Screen readers hear "Status: …".

export type Status = "confirmed" | "pending" | "cancelled" | "info";

const ICON_PATHS: Record<Status, string> = {
  confirmed: "M20 6 9 17l-5-5",
  pending: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v5l3 2",
  cancelled: "M18 6 6 18M6 6l12 12",
  info: "M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zM16 3v4M8 3v4M3 10h18",
};

export function StatusChip({ status, children }: { status: Status; children: string }) {
  return (
    <span className={`la-chip la-chip--${status}`}>
      <span className="sr-only">Status: </span>
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
      {children}
    </span>
  );
}
