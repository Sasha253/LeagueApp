// The League App logo, "Kick-off stripes": two forward-leaning bars, like kit stripes or a
// "vs" slash, and an italic wordmark. A proposed component (docs/DECISIONS.md), drawn from
// tokens: the lead bar in `accent-ink`, the second bar and the wordmark in `ink`, so it reads
// on both themes. The bars match `stripesMark` in scripts/app-assets.mjs (the app icon).

/** The two bars on the app icon's 1024 square; the viewBox crops to them. */
export const STRIPES = [
  "194,832 391,832 549,192 352,192",
  "475,832 672,832 830,192 633,192",
] as const;

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="194 192 636 640" aria-hidden="true">
      <polygon points={STRIPES[0]} fill="var(--accent-ink)" />
      <polygon points={STRIPES[1]} fill="var(--ink)" />
    </svg>
  );
}

/** Mark and wordmark. Screen readers hear "League App"; the capitals are only CSS. */
export function Logo() {
  return (
    <span className="la-logo">
      <LogoMark className="la-logo__mark" />
      <span className="la-logo__word">League App</span>
    </span>
  );
}
