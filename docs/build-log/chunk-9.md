# Chunk 9: Notifications (backend and push sending)

Unattended run, 2026-10-23. PRD: "Notifications", "Targeting rules", NFR Timeliness.
Backend only; the app side is chunk 10.

## Plan

New app `backend/notifications/`.

Models:
- `Notification`: Club, recipient, kind (the seven PRD types: confirmation, reminder,
  general, update, player_request, goalkeeper_request, booking), title, body, related
  Fixture (optional), created at, read at, answer (confirm, decline, accept) and answered
  at, `answer_by` (after it, no answer; set by later chunks, e.g. T-6h for FR-3) and
  `closed_at` (a request that filled or a match that was cancelled). Push delivery state:
  push status (pending, sent, failed, no device), pushed at, push error.
  Action buttons come from the kind (`ACTIONS`): Confirm / Decline, Accept / Decline, the
  General "Find a match" link, or none.
- `DeviceToken`: user, FCM token (unique), platform (ios, android, web), created and last
  seen.

Services:
- `notifications/targeting.py`: the one place recipients are picked. Night opt-ins,
  Players of a Fixture's Teams, Players outside both Teams (any position, outfield for
  Player Requests, goalkeepers for Goalkeeper Requests), the Night's Admins, the pitch's
  Referee, reschedule recipients (Players of both Teams, the Night's Admins and the
  affected pitch's Referee only), Admins and Referees of a Fixture, Booking recipients.
- `notifications/services.py`: `notify()` creates one Notification per recipient and
  pushes after the transaction commits; `answer()`, `mark_read()`, `close()`; content
  builders for Confirmation and Reminder (team names, "Tue 27 Oct", "19:40", pitch).
  A `notification_answered` signal lets later chunks act on an answer.
- `notifications/push.py`: `PushSender` interface; `FirebaseSender` (firebase-admin,
  credentials from env), `LogSender` (local default), `FakeSender` (tests). Dead tokens
  are removed. Every push result is recorded on the Notification.

Endpoints (`/api/v1/`):
- `POST devices/` register (or move) a token; `DELETE devices/{id}/` remove it.
- `GET inbox/` (filters: all, needs_reply, updates; unanswered pinned on top),
  `GET inbox/summary/` (unread, needs reply), `GET inbox/{id}/`,
  `POST inbox/{id}/read/`, `POST inbox/{id}/answer/`.
Everyone sees only their own notifications and devices.

Delivery failure fallback: proposed in docs/OPEN_QUESTIONS.md, not built (the prompt asks
first). Built now: the inbox keeps every notification, push results are recorded, dead
tokens are removed.

Tests: pytest for every targeting rule, notify and push recording, the Firebase sender's
mapping (firebase-admin mocked), devices, inbox and answers, isolation.

Later (not in this chunk): the app side (chunk 10); sending from Celery with retries
(chunk 11); what an answer does (chunks 12 onwards); who is notified when a request fills
(open question 2); the delivery fallback itself once agreed.

## Result

Built:
- Backend app `backend/notifications/` (migration 0001): `Notification` (seven kinds,
  title, body, Fixture, read, answer, `answer_by`, `closed_at`, push status) and
  `DeviceToken`.
- `targeting.py`: Night opt-ins, Players of a Fixture or Team, Players outside both Teams
  by position (Player and Goalkeeper Requests), the Night's Admins, the pitch's Referee,
  Confirmation, Reminder, reschedule (FR-7, FR-8), officials (FR-12, FR-16, FR-17) and
  Booking recipients.
- `services.py`: `notify()` (one per recipient, pushed after commit), `push()` (records
  sent, failed or no device; removes dead tokens), `answer()` (changeable while open,
  `notification_answered` signal), `mark_read()`, `close()`, Confirmation and Reminder
  content in South African time.
- `push.py`: `PushSender` with `FirebaseSender` (firebase-admin, credentials from env),
  `LogSender` (local default) and `FakeSender` (autouse in every test via the root
  conftest). Setting `PUSH_SENDER`; production defaults to Firebase.
- Endpoints: `GET inbox/` (all, needs_reply, updates; unanswered on top),
  `GET inbox/summary/`, `GET inbox/{id}/`, `POST inbox/{id}/read/`,
  `POST inbox/{id}/answer/`, `POST devices/`, `DELETE devices/{id}/`. Others' records are
  404. Django admin is read-only. `npm run gen:api` run.
- Tests: `backend/notifications/tests/` (44): every targeting rule, push recording, the
  Firebase sender's mapping, answers, inbox, devices and isolation.

Not built: the delivery fallback beyond the inbox and recorded push results (proposal in
docs/OPEN_QUESTIONS.md, waiting for an answer); the Later list above. No screens, so no
new Vitest files.

By hand: create a Firebase project and a service account key; set
`PUSH_SENDER=notifications.push.FirebaseSender` and `FIREBASE_CREDENTIALS_FILE` (or
`FIREBASE_CREDENTIALS_JSON`) on the server; run `make install` to get firebase-admin.
Answer the Chunk 9 open questions, especially Night opt-ins for a Player's own Team and
the delivery fallback proposal.

Checks: make test 403 passed; make lint clean; npm test 126 passed (26 files);
npm run build ok.
