# Chunk 18: PayFast payments (backend)

Unattended run, 2026-10-23. PRD: FR-19 to FR-22, FR-52 (credit), the "Payment gateway"
section (PayFast now, Peach and Yoco later, behind one interface), NFR Security (card data
only at a PCI-compliant gateway). Builds on the chunk 8 ledger (`ledger/services.py`) and
the chunk 3 settings (`payment_mode`, `payment_provider`).

Open question 5 of docs/DECISIONS.md (does each club take card payments into its own
PayFast merchant account?) could not be asked. Chosen so either answer is configuration
only: one default merchant account from the environment, with an optional per-club
override (also from the environment); each Payment records the merchant it was made with.
See docs/OPEN_QUESTIONS.md "Chunk 18".

## Plan

New app `payments`:
- `gateways.py`: `PaymentGateway` interface (`checkout(payment)`, `verify_notification(...)`)
  and a registry keyed by `ClubSettings.payment_provider`. Credentials per Club resolved
  from settings (env), never from the database.
- `payfast.py`: `PayFastGateway`. Checkout: the PayFast hosted page (process URL and the
  signed form fields, also as a GET link), so card details go only to PayFast. ITN
  checks, in order: source IP in PayFast's networks (from env), MD5 signature with the
  passphrase, merchant id is the Payment's, amount equals the card amount, then
  server-side validation by posting back to PayFast's `query/validate` ("VALID").
  Sandbox or live hosts and credentials from env (`PAYFAST_*`).
- Models: `Payment` (reference UUID, Club, Team, Player, amount = credit + card, credit
  used and whose, provider, merchant id, status pending/complete/failed/cancelled, the
  gateway's payment id, the card ledger entry and the credit ledger entry, times). Never
  deleted; read-only in the Django admin. `GatewayNotification`: every ITN received (raw
  fields, source IP, outcome, detail), append-only.
- `services.py`:
  - `start_payment(team, player, amount, credit)`: Player in an active Team, the club in
    gateway mode with a merchant account, amount up to what the Team still owes. Credit
    first if asked (`player` or, for the Captain, `team`), spent at once through
    `ledger.services.spend_credit`; the rest goes to the card. Fully covered by credit:
    complete straight away, no checkout.
  - `handle_notification(provider, fields, source_ip)`: verify, then under a lock on the
    Payment apply once: COMPLETE writes one card ledger entry (`record_payment`, method
    card, the gateway id in the reason); a repeat ITN writes nothing; FAILED/CANCELLED
    only mark a pending Payment.
  - `record_cash(team, admin, amount, player, reason)` (FR-22): cash ledger entry, up to
    what the Team owes.
  - Team paid (FR-20): when a payment (card, cash or credit) takes the Team's outstanding
    from above zero to zero or below, send `team_paid` (chunk 20 issues the Barcode).
    `paid` is also shown on the balance.
- Endpoints (all /api/v1/):
  - `GET teams/{id}/payments/options/`: for a Player in the Team: due, outstanding,
    whether card is on, the card minimum, my credit, Team credit (Captain only).
  - `POST teams/{id}/payments/`: start a contribution; returns the Payment and checkout.
  - `GET me/payments/`, `GET payments/{reference}/` (the payer only).
  - `POST teams/{id}/cash-payments/` (Admin of the Team's Club).
  - `POST payments/payfast/notify/` (the ITN webhook; no auth, form-encoded, 200 on
    accepted or repeat, 400 on rejected).
  - Team balance gains `paid`.
- Settings/env: `PAYFAST_SANDBOX`, `PAYFAST_MERCHANT_ID`, `PAYFAST_MERCHANT_KEY`,
  `PAYFAST_PASSPHRASE`, `PAYFAST_CLUB_ACCOUNTS` (JSON per club id), `PAYFAST_NOTIFY_URL`,
  `PAYMENT_RETURN_URL`, `PAYMENT_CANCEL_URL`, `PAYFAST_ITN_NETWORKS`,
  `PAYFAST_TRUSTED_PROXIES`, `PAYFAST_VALIDATE_SERVER`. Documented in .env.example.

Tests (pytest): signature against a known PayFast example, checkout fields, every ITN
check (source, signature, merchant, amount, server validation), idempotent repeats,
failed/cancelled, credit first (Player and Team), refusals (not in Team, inactive Team,
cash-only club, no merchant account, more than owed, below minimum), Team paid signal,
cash by Admin and club isolation, who sees what.

Later (not in this chunk):
- Payment screens (chunk 19), Payment Barcodes on `team_paid` (chunk 20), friendly fees
  (chunk 22), booking payments (chunk 24).
- A Captain paying for the whole Team as a Team payment (Team credit source).
- Expiring abandoned pending payments; card refunds (club cancels a booking).
- Peach and Yoco gateways.

## Result

Built:
- New `payments` app (migration `payments/0001_initial`): `Payment` (never deleted) and
  `GatewayNotification` (every ITN, never changed or deleted), read-only in the Django
  admin. Enum names pinned (`PaymentStatusEnum`, `PaymentCreditEnum`,
  `PaymentProviderEnum`).
- `payments/gateways.py`: the `PaymentGateway` interface, `gateway_for(provider)`, network
  and client-IP helpers. `payments/payfast.py`: `PayFastGateway` (signed hosted-page
  checkout as a link and as a form; ITN checks: source networks, MD5 signature with the
  passphrase, merchant, amount, server-side validation against `/eng/query/validate`).
  Default merchant account plus optional per-club accounts, all from the environment.
- `payments/services.py`: `start_payment` (credit first, then card; every amount checked
  in the backend), `handle_notification` (verify, then apply once under a row lock;
  repeats record nothing), `record_cash` (FR-22), `team_paid` signal when a payment
  settles what a Team owes (FR-20).
- `ledger`: `record_payment(..., money_taken=True)` for confirmed card payments,
  `team_balances()` (many Teams in one query), `is_paid` on `TeamBalance` and on
  `GET /api/v1/teams/{id}/balance/`.
- Endpoints: `GET /api/v1/teams/{id}/payments/options/`, `POST /api/v1/teams/{id}/payments/`,
  `GET /api/v1/me/payments/`, `GET /api/v1/payments/{reference}/`,
  `POST /api/v1/teams/{id}/cash-payments/`, `GET /api/v1/clubs/{club_id}/team-payments/`,
  `POST /api/v1/payments/payfast/notify/` (ITN webhook). schema.d.ts regenerated.
- Settings and `.env.example`: `PAYFAST_SANDBOX` (live by default in production),
  `PAYFAST_MERCHANT_ID`, `PAYFAST_MERCHANT_KEY`, `PAYFAST_PASSPHRASE`,
  `PAYFAST_CLUB_ACCOUNTS`, `PAYFAST_NOTIFY_URL`, `PAYMENT_RETURN_URL`,
  `PAYMENT_CANCEL_URL`, `PAYFAST_ITN_NETWORKS`, `PAYFAST_TRUSTED_PROXIES`.
- Tests: 71 new pytest tests (`payments/tests/`: signatures, checkout, accounts, sources,
  every ITN check, repeats, failed/cancelled, credit first, refusals, cash, permissions
  and club isolation, a concurrent repeat ITN) and one ledger test for `team_balances`.

Not built: the Later list above. No frontend screens (chunk 19).

By hand:
- `make migrate` (one new migration).
- PayFast: a sandbox merchant account (or PayFast's public sandbox 10000100) and a public
  HTTPS URL for `PAYFAST_NOTIFY_URL` (e.g. an ngrok tunnel) to try a real sandbox ITN;
  live merchant keys and passphrase per club before release, set `PAYFAST_SANDBOX=false`.
- Check `PAYFAST_ITN_NETWORKS` against PayFast's current published list, and set
  `PAYFAST_TRUSTED_PROXIES` to the number of reverse proxies in production.
- Review the provisional answers in docs/OPEN_QUESTIONS.md "Chunk 18" (open question 5).

Checks: make test (694 passed), make lint (passed), npm test (215 passed), npm run build
(passed).
