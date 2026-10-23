# League App

Web app for running a social football league: confirmations, payments, gate scanning, field
bookings and finances. React frontend, Django REST API.

- Product spec: [docs/PRD.md](docs/PRD.md)
- Decisions and open questions: [docs/DECISIONS.md](docs/DECISIONS.md)
- Design system and screen designs: [design/](design/)

## Requirements

- Python 3.12 or later
- Node 20 or later
- Docker (for PostgreSQL and Redis)

## First run

```sh
cp .env.example .env          # then set DJANGO_SECRET_KEY and the Postgres password
make install                  # backend/.venv with the dev requirements
make up                       # PostgreSQL on 127.0.0.1:5433, Redis on 127.0.0.1:6380
make migrate
cd frontend && npm install
```

## Day to day

Run the API and the web app in two terminals:

```sh
make run                      # Django on http://127.0.0.1:8000
cd frontend && npm run dev    # React on http://localhost:5173, proxies /api to Django
```

The timed checkpoints (T-36h Confirmations, their resend, T-6h Reminders) need a Celery
worker and Celery Beat, each in its own terminal:

```sh
make worker                   # runs the jobs
make beat                     # starts them every minute (run only one Beat)
```

- API docs: http://127.0.0.1:8000/api/v1/docs/
- Health check: http://localhost:5173/api/v1/health/

## Tests and checks

```sh
make test                     # backend (pytest)
make lint                     # backend (ruff)
cd frontend && npm test       # frontend (vitest)
cd frontend && npm run build  # typecheck and production build
```

After changing an API endpoint, regenerate the frontend types with
`cd frontend && npm run gen:api`.

## Layout

| Path | What |
| --- | --- |
| `backend/config/` | Django settings (`base`, `local`, `production`) and URLs |
| `backend/core/` | Project-level endpoints (health) |
| `frontend/src/` | React app; `styles/` holds the design system's tokens and components |
| `design/` | Design system source (`src/ds/`) and the canvas generator |
| `docs/` | PRD and decisions |
