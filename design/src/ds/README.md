League App is the mobile app for social football leagues: Players confirm they are playing, Captains fill their squad and pay, Admins and Referees keep the night running, and Booking Users hire a field. The look is **floodlit night football**: a deep pitch-green ground, one floodlight-lime accent, condensed scoreboard numerals, and a white match ticket that scans at the gate. "League App" is a working name; swap it when the product is named.

## Principles

1. **One question per screen.** Most sessions are a single reply: "Are you in for Tuesday?" Lead with that question and its two answers; everything else sits below.
2. **Status is never colour alone.** Every state carries a word and an icon: *Confirmed*, *Waiting*, *Cancelled*, *Rescheduled*.
3. **Time is the hero.** Kick-off time and the reply deadline are the largest things on a match card, set in `scoreboard`.
4. **Built for the touchline.** Night theme first, big targets (`tap-min`), one-thumb reach: primary actions sit in the bottom third.
5. **The ticket is sacred.** The Payment Barcode always renders on `ticket` white with `ticket-ink`, at full brightness, whatever the theme.

## Voice and copy

- Talk like a good captain: short, friendly, direct. Second person ("You're in"), never "the user".
- Sentence case everywhere except `overline`, which is uppercase.
- Buttons are verbs or player phrases: "I'm in", "Can't make it", "Pay R 70", "Scan ticket", "Find a game".
- Lead with the consequence: "Your team has 4 of 5 players. Find 1 more by 13:40 or the match is cancelled."
- Times in 24h ("19:40"), dates as "Tue 21 Oct", money as "R 350" (ZAR, space after R). Relative deadlines under 24h: "in 5 h".
- No emoji, no exclamation marks except "You're in!" on the single confirmation moment.

## Colour

- Night (default) and Day themes. Night is for the pitch at 19:00; Day follows the phone's setting.
- Screens sit on `ground`; cards, sheets and the tab bar on `surface`; inputs and tracks on `surface-sunken`.
- Text is `ink`; metadata is `ink-muted`. Both read at 4.5:1 or better on every surface.
- `accent` is a fill for exactly one primary action per screen, the active tab indicator and progress fills; its content is `on-accent`. Use `accent-ink` for accent-coloured text and links. Selected rows use `accent-soft`.
- Statuses: `confirmed` (teal: confirmed, paid, accepted), `pending` (amber: waiting, unpaid, requested), `cancelled` (orange: declined, cancelled, failed), `info` (blue: rescheduled, update, friendly). Chips and banners pair the strong colour as text/icon on its `-soft` tint. Confirmed is teal, not green, so it never relies on red/green alone.
- The ticket: `ticket` face, `ticket-ink` bars and text, `shadow-ticket`. Never tint it.

## Type

- Two Google-hosted families, loaded with `https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@600;700&display=swap`.
- **Barlow Condensed** (`display`) for numbers and titles: `scoreboard` for kick-off times and countdowns (always `font-variant-numeric: tabular-nums`), `title-1` for screen titles, `title-2` for fixtures, `overline` for kickers.
- **Barlow** (`sans`) for everything read: `headline`, `body`, `body-strong`, `label` for buttons, `caption` for metadata.
- Support Dynamic Type / font scaling to 200%: rows grow, nothing truncates mid-word, team names wrap to two lines.

## Layout

- Design at 375 × 812 (iPhone 13 mini to Pixel class); check 320 and 430 widths. `gutter` side margins, content max 560px on tablets.
- 4px grid; use `space-*` steps. Cards are `space-4` padded, `space-4` apart; sections `space-5` apart.
- Structure: large-title nav bar (`title-1`) → content → tab bar (`tabbar-height`). Primary actions pin to the bottom above the tab bar or inside a bottom sheet.
- Corners: `radius-lg` for match cards, sheets and the ticket; `radius-md` for buttons and groups; `radius-sm` for inputs; `radius-pill` for chips and progress.
- Depth: Night separates by surface colour, not shadow (`shadow-card` is none there). Day uses `shadow-card`. Sheets use `shadow-sheet`.

## Iconography

- No brand icon set exists yet. Use **Lucide** outline icons, 24px (`icon-md`), 2px stroke, round caps, coloured with the text token beside them. Flagged substitution: replace if a brand set is made.
- Core icons: check (confirmed), clock (pending), x (cancelled), calendar-clock (rescheduled), users (team), shirt (player), hand (goalkeeper request), credit-card (pay), scan-line (scan), ticket (barcode), map-pin (pitch), bell (notifications).
- Logo, "Kick-off stripes": two forward-leaning bars (lead bar `accent-ink`, second bar `ink`) and "LEAGUE APP" in `font-display` 700 italic capitals, `ink`. The mark is as tall as the wordmark's line, a `space-3` gap between. App icon: the bars alone, `accent` then `ink`, on the Night `ground`; the bars in `on-accent` on an `accent` tile is the alternate. Never draw a club crest.

## States and motion

- Every list has an empty state (one line of copy + one action), a loading skeleton in `surface-sunken`, and an error state with Retry.
- Pressed: content at 0.72 opacity. Disabled: 0.4 opacity, never colour change only.
- Focus: 2px solid `focus-ring`, 2px offset, on every interactive element.
- Motion is short and functional: 200ms ease-out for sheets, a single scale-in check on "You're in!", a scan line sweep on the scanner. Respect Reduce Motion: replace with fades.

## Accessibility

- Touch targets at least `tap-min` (48 × 48).
- Text 4.5:1 and borders/icons 3:1 in both themes (all tokens above are checked).
- Every icon-only button has a label ("Scan ticket"); status chips read as "Status: Confirmed".
- Countdowns announce at most once a minute.

## Components

Each component below has a live preview and guidelines. They are HTML/CSS recipes: classes live in `components/bundle.css` with the `la-` prefix and read only tokens. Rebuild them natively in SwiftUI / Jetpack Compose / .NET MAUI with the same tokens.

- **Button**: primary, secondary, quiet and destructive.
- **StatusChip**: the four statuses with icon and word.
- **MatchCard**: the fixture with kick-off time, pitch, squad count and your status.
- **ConfirmationCard**: the in-app form of every Confirmation, Player Request and Booking notification.
- **SquadProgress**: confirmed players against the Division minimum.
- **PaymentProgress**: team payment against the amount due.
- **PaymentTicket**: the Payment Barcode pass.
- **FinanceSummary**: the Admin's money totals and the week-by-week income planner.
- **TabBar**: role-aware bottom navigation.

The **Screens** section lists every screen per role for building the app's UI.
