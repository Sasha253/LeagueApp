# League App

Social football league management for venue operators: team sign-up, fixture confirmation at
T-36h and T-6h, cancellations, replacements and friendlies, payments proven at the gate with a
Payment Barcode, field bookings, player sourcing and a phase 1 finance tracker.
Product spec: docs/PRD.md (transcribed from docs/League_Management_App_PRD.pdf, which wins if
they differ). Decisions and open questions: docs/DECISIONS.md.
Design: the League App design system in design/src/ds/ (README.md, Screens.md, tokens) and the
screen designs in design/ (open design/key-moments-draft.html).

## Stack
- backend/: Django + Django REST Framework, Python 3.12+, PostgreSQL (psycopg 3), drf-spectacular
- frontend/: React + TypeScript + Vite; API client generated from the OpenAPI schema
- Same stack and layout as ~/VSCodeProjects/Swingbok

## Rules
- API first: every feature is a /api/v1/ endpoint documented in OpenAPI. The React app only
  calls the API and renders; cutoffs, fees, minimums, payment totals and cancellation outcomes
  are decided in the backend, never in the frontend.
- Money is Decimal, never float, in rand. Show it as "R 350" (space after R, comma thousands:
  "R 18,550").
- Store times in UTC, show South African time (Africa/Johannesburg), 24-hour ("19:40"), dates
  as "Tue 27 Oct".
- Every club-configurable value (minimum players per Division, fees, cutoffs, payment window,
  cancellation thresholds) is data, never a constant in code (FR-42, NFR Configurability).
- Ledger entries are append-only: credits, refunds and corrections are new entries with a
  reason; never edit or delete one (FR-50).
- Payment Barcodes are unique, tied to one Team or Booking, and cannot be reused or forged.
- Card data never touches the app: it goes to a PCI-compliant payment gateway.
- Notification targeting follows the PRD exactly: Players only for the Nights they opted into;
  Player Requests only to outfield Players, Goalkeeper Requests only to Goalkeepers; a
  reschedule notifies only that Night's Admin and that pitch's Referee (FR-8).
- UI uses only the design system's tokens, type styles and `la-` components
  (frontend/src/styles/). Something the system lacks is built from its tokens and listed in
  docs/DECISIONS.md as a proposed component.
- Secrets only from environment variables. Never commit .env.

## Working style
- If the PRD is unclear, ask rather than guess, and note the decision in docs/DECISIONS.md.
- Plan before coding; keep each change to the chunk asked for.
- Write tests with the code. Run the backend and frontend tests before saying a task is done.
- After changing an API endpoint, run `npm run gen:api` so the frontend types match.

## Commands
- make install / make up / make migrate / make run / make test / make lint (backend)
- npm run dev / npm test / npm run build / npm run gen:api (frontend, in frontend/)
- node design/src/build.mjs draft (rebuilds the design canvas)
