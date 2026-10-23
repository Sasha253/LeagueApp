# Chunk 11: Celery Beat and the timed checkpoints

Unattended run, 2026-10-23. PRD: FR-1, FR-2, FR-4, NFR Timeliness and Scheduling. Builds
on the chunk 7 lifecycle (`fixtures/lifecycle.py`), the chunk 3 club settings
(`confirmation_hours_before`, `confirmation_resend_after_hours`, `readiness_hours_before`)
and the chunk 9 notification engine (`notifications/services.py`, `targeting.py`).

## Plan

Infrastructure:
- `celery[redis]` 5.6 in backend/requirements/base.txt, `time-machine` in dev.txt.
- Redis in docker-compose.yml on 127.0.0.1:6380 (6379 is Swingbok's), started by `make up`.
- `backend/config/celery.py` (the Celery app, settings under `CELERY_`), loaded from
  `config/__init__.py`. Beat schedule in settings: `fixtures.run_checkpoints` every 60
  seconds (`CHECKPOINT_INTERVAL_SECONDS`), expiring if not started within the interval so
  a backlog never piles up.
- `make worker` and `make beat`; CLAUDE.md Commands, README and .env.example updated.

Model (fixtures app):
- `FixtureCheckpoint`: Fixture, kind (confirmation, resend, reminder), the kick-off it ran
  for, when it ran, how many were notified. Unique on (Fixture, kind, kick-off), so each
  checkpoint runs exactly once per Fixture and kick-off; a reschedule to a new kick-off
  (FR-9, chunk 16) gets fresh checkpoints. Append-only like FixtureTransition; read-only
  inline in the Django admin.

Service (`backend/fixtures/checkpoints.py`), `run_due(now)` called by the task:
- Each club's hours come from its ClubSettings at run time.
- T-36h Confirmation (FR-1): Fixtures still `scheduled`, kick-off within
  `confirmation_hours_before` and still after the T-6h cutoff. Moves the Fixture to
  `confirming` (cause: timed checkpoint) and sends a Confirmation to every Player of both
  Teams (targeting.confirmation_recipients) with `answer_by` = the T-6h cutoff (FR-3).
- Resend (FR-2): Fixtures `confirming` whose Confirmation checkpoint ran at least
  `confirmation_resend_after_hours` ago and whose T-6h cutoff is still to come. Re-pushes
  the same Notification (no second inbox entry), only to Players who have not answered,
  still in a Team of the match and opted in. Once.
- T-6h Reminder (FR-4): Fixtures `scheduled`, `confirming` or `ready` with kick-off within
  `readiness_hours_before` and still to come. Players and Captains of both Teams, the
  Night's Admins and the pitch's Referee (targeting.reminder_recipients).
- Late runs catch up: a checkpoint missed while Beat was down runs on the next tick, as
  long as it is still useful (a Confirmation only before the T-6h cutoff, a Reminder only
  before kick-off). Twice-running is safe: each Fixture is locked, its checkpoint row is
  claimed in the same transaction, and the unique constraint refuses a second claim.
- One Fixture failing is logged and never stops the others.

Notifications: `services.resend()` re-pushes a Notification (unread again, push status
pending, `resent_at` set; new field). Push still goes out in-process after commit.

Tests (pytest, frozen clock with time-machine): each checkpoint fires at its time and not
before; runs exactly once when run twice or late; late Confirmation skipped after the
cutoff; resend only to non-responders, once, only after the delay, not after the cutoff;
Reminder recipients; club settings are used; cancelled Fixtures are skipped; another
club's settings don't leak; the Celery task and Beat schedule are wired; a reschedule's
new kick-off gets new checkpoints.

No API change and no screens (`npm run gen:api` still run).

Later (not in this chunk):
- T-6h readiness check (FR-5, FR-6) and the Admin queue: chunk 13. It belongs in the same
  T-6h pass and should run before the Reminder so a Team that is out isn't reminded.
- What a Confirmation answer does: chunk 12.
- FR-9 immediate Confirmations on a reschedule: chunk 16.
- Booking payment cutoff job: chunk 24.
- Push retries and the email fallback (chunk 9 proposal): waiting for an answer.
- A Player who joins a Team after T-36h gets no Confirmation (decide with chunk 12).

## Result

Built:
- Celery 5.6 with Redis: `backend/config/celery.py`, settings under `CELERY_` in
  `config/settings/base.py`, Redis in docker-compose.yml (127.0.0.1:6380), `make worker`
  (thread pool, see below) and `make beat`; CLAUDE.md, README and .env.example updated.
  Beat starts `fixtures.run_checkpoints` every 60 seconds; checked end to end locally
  (Beat sent it, the worker ran it).
- `FixtureCheckpoint` (append-only, unique per Fixture, kind and kick-off), shown read-only
  in the Django admin under each Fixture. `Notification.resent_at`.
- `backend/fixtures/checkpoints.py`: T-36h Confirmations (Fixture to `confirming`, answer
  by T-6h), the one resend to non-responders (same inbox entry pushed again, unread), T-6h
  Reminders. Exactly once under repeated or concurrent runs; late runs catch up while
  still useful; one failing Fixture never stops the rest. `notifications.services.resend()`.
- 20 new pytest tests on a frozen clock (time-machine): each checkpoint's timing, run twice,
  claimed by another worker, late and too-late runs, statuses skipped, each club's own
  hours, reschedule, failure isolation, resend recipients and once-only, Reminder
  recipients, the Celery task and Beat schedule.

Not built: the Later list above (readiness check, answers, FR-9, booking cutoff, push
retries and email fallback). No API change (`npm run gen:api`: schema unchanged), no
screens.

By hand:
- Run `make install` (new packages: celery[redis], time-machine) and `make up` (starts
  Redis), then `make migrate`.
- For the checkpoints to fire locally, run `make worker` and `make beat` in their own
  terminals.
- Production: run one Celery worker and exactly one Celery Beat beside the web app, with
  `CELERY_BROKER_URL` pointing at a Redis instance.
- `make worker` uses `--pool=threads` because Celery's default process pool fails every
  task on this Mac with Python 3.14; on Linux the default pool can be used.

Checks: make test (424 passed), make lint (passed), npm test (163 passed), npm run build
(passed).
