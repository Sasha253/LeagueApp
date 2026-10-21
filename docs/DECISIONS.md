# Decisions

Newest first. Each entry: the date, what was decided, and why.

## 2026-10-21: React + Django web app

The app is built as a web app: a React frontend (`frontend/`) over a Django REST API
(`backend/`), the same stack as Swingbok.

- The PRD lists iOS and Android as the platforms, and the designs in `design/` are mobile
  screens at 375 × 812. The web app is therefore built mobile-first from those designs.
- **Still open:** push notifications are the PRD's core mechanism. A web app sends them with
  Web Push, and iOS delivers Web Push only to a web app added to the home screen (iOS 16.4 and
  later). Whether that is enough, or the app needs a native wrapper, is not decided yet.

## 2026-10-21: Design source

The UI follows the League App design system: tokens, type styles and `la-` components.
Its files are in `design/src/ds/`, copied unchanged from `League App Design System.zip`
(dated 2026-10-20) because the claude.ai artifact link could not be read from Claude Code.
`design/` also holds the canvas generator and the key-moments draft
(`design/key-moments-draft.html`).

## Open questions

Raised while drawing the key moments; the PRD does not answer them.

1. Does a borrowed Player pay for a league match, how much, and who pays? FR-24 sets a fee
   only for friendlies.
2. Is the Captain notified when a Player or Goalkeeper Request fills? The PRD names no
   notification for it.
