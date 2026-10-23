// ChoiceChip (proposed component, docs/DECISIONS.md): a 48px option that is on or off.

import type { ReactNode } from "react";

type Props = { pressed: boolean; onToggle: () => void; children: ReactNode; label?: string };

export function ChoiceChip({ pressed, onToggle, children, label }: Props) {
  return (
    <button
      type="button"
      className="la-choice"
      aria-pressed={pressed}
      aria-label={label}
      onClick={onToggle}
    >
      {children}
    </button>
  );
}
