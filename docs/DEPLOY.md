# Deploy to VM

Every push to `main` runs the **Deploy to VM** workflow (`.github/workflows/deploy.yml`):

1. Backend tests (ruff, pytest against PostgreSQL) and frontend tests (vitest, build).
2. If both pass: the commit is copied to the VM over SSH and unpacked into `<VM_APP_DIR>/src`,
   then `deploy/deploy.sh` builds the images, applies migrations and starts the stack in
   `docker-compose.prod.yml`.
3. `https://<SITE_DOMAIN>/api/v1/health/` must answer 200.

It can also be run by hand: Actions → Deploy to VM → Run workflow.

## What runs on the VM

| Service    | What it is                                                                          |
|------------|-------------------------------------------------------------------------------------|
| `caddy`    | HTTPS on 80/443 (certificate from Let's Encrypt), the built web app, proxy to `web` |
| `web`      | Django on gunicorn (`backend/Dockerfile`)                                           |
| `worker`   | Celery worker, runs the timed checkpoints                                           |
| `beat`     | Celery Beat, starts them on schedule (exactly one)                                  |
| `postgres` | PostgreSQL 16, data in the `postgres-data` volume                                   |
| `redis`    | Redis 7, the Celery broker                                                          |

Only Caddy publishes ports. Caddy sends `/api/*`, `/admin/*`, `/static/*` and `/privacy/` to
Django; everything else is the web app (unknown paths fall back to `index.html`).

## One-time VM setup

1. A Linux VM with Docker Engine and the compose plugin (`docker compose version`), ports 22,
   80 and 443 open, and DNS for your domain pointing at it.
2. A deploy user who can run Docker (`sudo usermod -aG docker <user>`).
3. An SSH key just for deploys. On your machine:
   `ssh-keygen -t ed25519 -f leagueapp-deploy -N ""`, then add `leagueapp-deploy.pub` to the
   deploy user's `~/.ssh/authorized_keys` on the VM.
4. The production settings: copy `deploy/production.env.example` to `~/leagueapp/.env`
   on the VM (or `<VM_APP_DIR>/.env`) and fill it in. Generate secrets with
   `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`; for `POSTGRES_PASSWORD`
   use `secrets.token_hex(24)` (it goes into a URL). `chmod 600` the file.

## GitHub settings

In the repo: Settings → Environments → **production** (the deploy job uses it; add required
reviewers there if you want to approve each deploy).

Secrets:

| Secret                | Value                                                     |
|-----------------------|-----------------------------------------------------------|
| `VM_HOST`             | The VM's address                                          |
| `VM_USER`             | The deploy user                                           |
| `VM_SSH_KEY`          | The private key (`leagueapp-deploy`), whole file          |
| `VM_SSH_KNOWN_HOSTS`  | Output of `ssh-keyscan -H <VM_HOST>` (check it's the VM)  |

Variables:

| Variable       | Value                                                  |
|----------------|--------------------------------------------------------|
| `SITE_DOMAIN`  | Same as in the VM's `.env`, e.g. `league.example.com`  |
| `VM_APP_DIR`   | Optional; default `leagueapp` (in the user's home)     |
| `VM_SSH_PORT`  | Optional; default `22`                                 |

## On the VM

From `<VM_APP_DIR>/src`:

- Logs: `docker compose -f docker-compose.prod.yml logs -f web worker beat`
- Django shell / admin user:
  `docker compose -f docker-compose.prod.yml run --rm web python manage.py createsuperuser`
- Backups: the database lives in the `leagueapp-prod_postgres-data` volume, e.g.
  `docker compose -f docker-compose.prod.yml exec postgres pg_dump -U leagueapp leagueapp > backup.sql`

Rolling back: re-run the workflow on an older commit (Actions → Deploy to VM → Run workflow,
pick the branch or tag), or revert on `main`. Migrations are not reversed automatically.

The installed apps (App Store, Google Play) are built separately (docs/STORE_RELEASE.md) with
`VITE_API_BASE_URL=https://<SITE_DOMAIN>`.
