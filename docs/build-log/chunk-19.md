# Chunk 19: Payments (UI)

Unattended run, 2026-10-23. PRD: FR-19 to FR-22, FR-52 (credit). Screens.md Player 3
"Pay my share" (amount defaulting to the per-player share, credit applied first, Pay R 70,
cash to the club also accepted), Captain 1 "My team" (`PaymentProgress` with per-player
rows) and Admin 5/6 (which Teams have paid, Mark cash paid). Builds on the chunk 18 API.

## Plan

Backend (small additions, so the app only draws what the backend decides):
- `ledger.services.paid_by_payer(team)`: what each Player (and the whole Team) has paid
  towards the Team, net of refunds and reversals, the same sums as `team_balance`.
- `GET /api/v1/teams/{id}/payments/summary/` (FR-21): for the Team's Captain and the
  Admins of its Club (404 for anyone else): due, paid, outstanding, is_paid, what each
  current Player has paid (and anyone who paid and has since left), what was paid for the
  whole Team, and Team credit (Captain only).
- Payment options gain `suggested_amount`: the per-player share (due over the current
  Players, rounded up to the cent) less what this Player has paid, capped at what is owed.
  Pay my share starts from it.
- `npm run gen:api`.

Frontend:
- `frontend/src/native/browser.ts`: `openCheckout(url)`. In the installed app it opens
  PayFast with @capacitor/browser and resolves when the Player closes it; in the browser
  it goes to PayFast in the same tab (PayFast returns to `PAYMENT_RETURN_URL`).
- Player: `/teams/:teamId/pay` (Pay my share): due and still owed, amount (starts at the
  suggested share, with "My share" and "All that's owed" shortcuts from the API), credit
  choice (none, my credit, Team credit for the Captain; only when there is some), Pay R x.
  Cash-only club: says so, and only credit can be used. After paying: the result screen.
- `/payments/done` and `/payments/cancelled` (?payment=<reference>, the chunk 18 return
  URLs): the Payment's status from `GET /api/v1/payments/{reference}/`, checking again
  while it is pending, with "Pay by card" again for a pending card part.
- Team screen: "Pay my share" for Players in the Team; for the Captain, `PaymentProgress`
  with who has paid (per-player rows), and Team credit.
- Admin: `/clubs/:clubId/payments` (which Teams have paid, unpaid first) and
  `/clubs/:clubId/payments/:teamId` (PaymentProgress, who has paid, Record cash: amount,
  for the Team or one Player, reason). Linked from Profile ("Payments").
- PaymentProgress built from the design system (`la-progress`, design/src/ui.mjs
  `payProgress`).

Tests: pytest for the summary (sums, refunds and reversals, leavers, Team payments, who
sees it, club isolation, Team credit Captain only) and the suggested amount; Vitest for
every screen and the browser wrapper.

Later (not in this chunk):
- Payment Barcodes after a Team is paid (chunk 20); friendly fees (chunk 22).
- Universal links / app links so PayFast's return page reopens the app by itself.
- "Remind unpaid" (Screens.md Captain 1), the Finances view and Team ledger (Admin 5/6).
- Saved cards.

## Result

Built:
- Backend: `ledger.services.paid_by_payer(team)`; `GET /api/v1/teams/{id}/payments/summary/`
  (Captain and the club's Admins; 404 otherwise; Team credit for the Captain only);
  `suggested_amount` on the payment options (`payments.services.suggested_amount`).
  schema.d.ts regenerated. 9 new pytest tests (`payments/tests/test_summary.py`) and the
  options test updated.
- `frontend/src/native/browser.ts` `openCheckout(url)` with @capacitor/browser (installed,
  `npx cap sync` run: Package.swift and the Android Gradle files list the plugin) and the
  browser fallback; tested both ways.
- Screens (`frontend/src/pages/payments/`): Pay my share (`/teams/:teamId/pay`), the
  payment result (`/payments/done`, `/payments/cancelled`, re-checks a pending payment by
  itself up to 10 times, "Pay by card" again, "Check again"), Team payments on the Team
  screen (Pay my share; for the Captain PaymentProgress with who has paid and Team credit),
  Admin Payments (`/clubs/:clubId/payments`) and a Team's payments with Record cash
  (`/clubs/:clubId/payments/:teamId`), linked from Profile. PaymentProgress built from the
  design system's `la-progress` (no new proposed components).
- Vitest: 21 new tests (browser wrapper, Pay, result, Team payments, Admin list and cash,
  Profile link).

Not built: the Later list above.

By hand:
- Try a sandbox payment end to end: set `PAYFAST_NOTIFY_URL` to a public tunnel (ngrok)
  to the backend, open a Team, Pay my share, and pay with PayFast's sandbox card.
- For the installed app, set `PAYMENT_RETURN_URL` and `PAYMENT_CANCEL_URL` to a web host
  serving the app (the in-app browser loads them); then close the in-app browser to return.
  Optional later: universal links / app links so the return reopens the app by itself.
- Rebuild the native apps (Xcode, Android Studio) to include @capacitor/browser.
- Review the provisional answers in docs/OPEN_QUESTIONS.md "Chunk 19".

Checks: make test (705 passed), make lint (passed), npm test (239 passed), npm run build
(passed).
