# Running the stack locally (dev)

Quick-start for getting all pieces up on this Windows/WAMP + Docker Desktop box. For the deep
technical reference (schemas, services, routes), see [`dev-guide/README.md`](./dev-guide/README.md).

## The pieces

| Piece | URL | How it runs |
|---|---|---|
| **webapp** (Laravel — the real SMSC platform) | http://127.0.0.1:8001 | `php artisan serve`, native PHP |
| **chatbot-ai backend** (FastAPI) | http://localhost:8010 | Docker Compose (`alembic upgrade head` + `uvicorn --reload`) |
| **chatbot-ai frontend** (React/Vite admin dashboard) | http://localhost:5173 | `npm run dev`, native Node, outside Docker for fast HMR |
| Postgres (chatbot-ai's own DB) | localhost:5433 → container 5432 | started by the same Docker Compose |
| Redis | localhost:6379 | started by the same Docker Compose |
| Celery worker | — (no HTTP port) | started by the same Docker Compose |
| MySQL (`smsc_db`, webapp's DB) | localhost:3307 | Docker container `smsc-mysql` |

The widget (`chatbot-ai/backend/widget/widget.js`) is served by the FastAPI backend itself at
`/widget.js` — nothing extra to start. Preview it via
`chatbot-ai/backend/widget/test-embed.html`.

## Prerequisites (already on this box)

- PHP 8.2 + Composer (`webapp/vendor` already installed)
- Node 22 + npm (`chatbot-ai/frontend/node_modules` already installed)
- Docker Desktop running
- `webapp/.env` and `chatbot-ai/backend/.env` already exist — no setup needed on this machine.
  Starting fresh elsewhere: copy `.env.example` → `.env` in each and fill in secrets (see
  `chatbot-ai/backend/.env.example` for `JWT_SECRET` / `CONFIG_ENCRYPTION_KEY` generation
  commands).

## Start everything

Run these three in separate terminals (or background them) — order doesn't matter except that the
webapp needs `smsc-mysql` up first.

**1. webapp's database** (Docker container, likely already running — check with
`docker ps --filter name=smsc-mysql`):
```
docker start smsc-mysql
```

**2. webapp (Laravel)**:
```
cd webapp
php artisan serve --port=8001
```
→ http://127.0.0.1:8001

**3. chatbot-ai backend + Postgres + Redis + Celery** (one Compose stack):
```
cd chatbot-ai
docker compose up -d --build
```
→ backend http://localhost:8010 (health check: `/api/health`, interactive docs: `/api/docs`)

**4. chatbot-ai frontend (admin dashboard)**:
```
cd chatbot-ai/frontend
npm run dev
```
→ http://localhost:5173

## Verify it's all up

```
curl http://127.0.0.1:8001              # webapp — expect 200, HTML
curl http://localhost:8010/api/health   # chatbot-ai backend — expect {"status":"ok"}
curl http://localhost:5173              # chatbot-ai frontend — expect 200, HTML
docker ps --filter "name=chatbot-ai"    # postgres + redis should show (healthy)
```

## Known gotchas on this box

- **Postgres port 5433, not 5432.** `chatbot-ai/docker-compose.yml` publishes Postgres on host
  port **5433** (mapped to the container's 5432) because an unrelated project's Postgres
  container already holds 5432 on this machine. If you need direct `psql`/DBeaver access from
  Windows, connect to `localhost:5433`. Nothing inside the Compose network is affected — the
  backend still talks to `postgres:5432` internally.
- **Backend container watcher crash.** `docker-compose.override.yml` sets
  `WATCHFILES_FORCE_POLLING=true` on the backend service. Without it, uvicorn's `--reload` file
  watcher can throw `WatchfilesRustInternalError: ... Input/output error (os error 5)` and crash
  the container — a known Docker-Desktop-on-Windows bind-mount issue. Don't remove this override.
- **webapp's DB is Docker MySQL, not WAMP MariaDB**, despite what older notes may say — `.env`
  points at `127.0.0.1:3307`, which is the `smsc-mysql` container (`mysql:8.0`), not
  `wampmariadb64`. WAMP's Apache/MariaDB services aren't required to run the webapp via
  `artisan serve`.
- **First-run only** (already done on this box, but if setting up fresh): a brand-new `smsc_db`
  has neither the database nor the `smsc_app` user, and the checked-in Laravel migrations assume
  a pre-existing base schema — restore
  `webapp/storage/app/backups/pre_full_reset_backup.sql` (or equivalent) first, then run
  migrations on top. The chatbot-ai admin account (`python -m app.workers.seed` inside the backend
  container) has no recoverable password unless `ADMIN_PASSWORD` was passed explicitly.
- Stray Docker containers from old `docker compose run` sessions may show up with random names
  (e.g. `chatbot-ai-backend:latest` image, no published port) — harmless, but safe to
  `docker rm -f` if you want a clean `docker ps`.

## Stopping everything

```
# Ctrl+C the artisan serve and npm run dev terminals, then:
cd chatbot-ai
docker compose down          # add -v to also drop the postgres/redis volumes (loses local data)
```

## Manual testing

[`webapp/CHATBOT_TESTING_QUESTIONS.md`](./webapp/CHATBOT_TESTING_QUESTIONS.md) is a live,
seed-data-accurate question bank for exercising both chatbot roles (`support` vs `user`) end to
end.

## Deeper reference

- [`dev-guide/README.md`](./dev-guide/README.md) — architecture, how the three pieces talk to
  each other, database schema, every service/route/model documented.
- [`deploy.md`](./deploy.md) — what changes to run this without Docker on a bare-metal/VPS
  production host.
