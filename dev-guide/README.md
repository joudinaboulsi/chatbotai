# Developer Guide — SMSC AI Chatbot Platform

Full technical reference for this monorepo: three deployable pieces sharing one product story —
an SMSC (SMS gateway) platform with an AI chatbot layered on top for sales, support, and account
self-service.

## The three pieces

| Piece | Path | Stack | What it is |
|---|---|---|---|
| **chatbot-ai backend** | `chatbot-ai/backend` | Python, FastAPI, SQLAlchemy (async), Postgres, Celery, Redis | The AI brain: conversation orchestration, RAG knowledge base, SMSC tool-calling, sales flow, live-agent handoff, operator dashboard API. |
| **chatbot-ai frontend** | `chatbot-ai/frontend` | React, TypeScript, Vite | The operator dashboard — agents, conversations, leads, knowledge base, live agents, settings. |
| **widget** | `chatbot-ai/backend/widget/widget.js` | Vanilla JS, no build step | The embeddable chat widget end customers actually talk to. Single self-contained file, no framework/bundler. |
| **webapp** | `webapp` | PHP, Laravel | The actual SMSC platform: tenants, accounts, users, messages, billing, SMPP/HTTP API provisioning, pricing, routing. The chatbot never touches its database directly — only through its internal API (`SmscAccountController`). |

## How they talk to each other

```
End customer                Support staff / admins
     │                              │
     ▼                              ▼
 widget.js  ────HTTP────►  chatbot-ai backend (FastAPI)  ◄────HTTP (dashboard)──── chatbot-ai frontend (React)
                                    │
                                    │ internal API, API-key auth (SmscApiAuth middleware)
                                    ▼
                              webapp (Laravel) ──► MySQL (smsc_db): the real SMSC data
                                    │
                          chatbot-ai backend's own
                          Postgres DB: conversations,
                          agents, leads, KB, etc.
```

The chatbot backend calls `webapp`'s `/api/...` routes (see `app/core/smsc_client.py` on the
Python side, `routes/api.php` + `SmscAccountController` on the Laravel side) to look up a real
customer's balance, traffic, SMPP status, etc. — it never invents account data; every number the
AI states came from a real tool call to `webapp`.

## Sections

- **[`database/schema.md`](./database/schema.md)** — full database documentation: every table,
  grouped by domain, with relationships explained and known-dead tables flagged. Raw
  `CREATE TABLE` appendix at [`database/webapp-schema-raw.md`](./database/webapp-schema-raw.md).
- **`chatbot-ai-backend/`** — [`README.md`](./chatbot-ai-backend/README.md) (overview),
  [`packages.md`](./chatbot-ai-backend/packages.md),
  [`models.md`](./chatbot-ai-backend/models.md) (all SQLAlchemy models + enums — this doubles as
  the schema doc for chatbot-ai's own Postgres DB),
  [`services-conversation.md`](./chatbot-ai-backend/services-conversation.md) (the chatbot's core:
  conversation routing, SMSC tool-calling, sales, RAG, handoff),
  [`services-admin.md`](./chatbot-ai-backend/services-admin.md) (knowledge base, notifications,
  email, dashboard, and the rest), [`api-routes.md`](./chatbot-ai-backend/api-routes.md) (every
  FastAPI route), [`core-infrastructure.md`](./chatbot-ai-backend/core-infrastructure.md) (LLM
  client, SMSC HTTP client, security, websockets, Celery).
- **`chatbot-ai-frontend/`** — [`README.md`](./chatbot-ai-frontend/README.md),
  [`packages.md`](./chatbot-ai-frontend/packages.md),
  [`api-client.md`](./chatbot-ai-frontend/api-client.md),
  [`pages-and-routing.md`](./chatbot-ai-frontend/pages-and-routing.md),
  [`components.md`](./chatbot-ai-frontend/components.md).
- **`webapp/`** — [`README.md`](./webapp/README.md), [`packages.md`](./webapp/packages.md),
  [`models.md`](./webapp/models.md) (all 14 Eloquent models),
  [`controllers.md`](./webapp/controllers.md) (every `SmscAccountController` method — the entire
  chatbot-facing surface), [`routes.md`](./webapp/routes.md).
- **[`widget.md`](./widget.md)** — the standalone customer-facing widget, method by method:
  bootstrap, SSE streaming, quick-replies, handoff, the inline-SVG chart renderer.

## Where things actually run (dev)

See [`../RUNNING.md`](../RUNNING.md) for step-by-step start/stop commands. Summary of the current
setup on this box:

- **webapp** (Laravel, `php artisan serve`): `http://127.0.0.1:8001` — DB is `smsc_db` on a
  **Docker MySQL 8.0** container (`smsc-mysql`) published at `127.0.0.1:3307` (see `webapp/.env`
  for creds), not WAMP's MariaDB — WAMP's `wampmariadb64`/`wampapache64` services aren't required
  to run the webapp this way.
- **chatbot-ai backend** (FastAPI) + **Postgres** + **Redis** + **Celery worker**: brought up
  together via `docker compose up -d --build` in `chatbot-ai/` (see `docker-compose.yml` +
  `docker-compose.override.yml`). Backend is exposed on `http://localhost:8010`; health check at
  `/api/health`, interactive docs at `/api/docs` (both under FastAPI's `settings`-driven prefix,
  not the bare `/docs` FastAPI default). Redis is published at `6379`; Postgres is published at
  **`5433`** (not the default 5432 — an unrelated project's Postgres container already holds 5432
  on this box; internal traffic still uses `postgres:5432` inside the Compose network). The
  backend's `--reload` file watcher needs `WATCHFILES_FORCE_POLLING=true` (set in the override
  file) to avoid crashing on Docker Desktop's Windows bind-mount watcher bug.
- **chatbot-ai frontend** (React/Vite dev server, `npm run dev`, outside Docker for fast HMR):
  `http://localhost:5173`.
- **phpMyAdmin** (bundled with WAMP, needs `wampapache64`/Apache running): `http://localhost/phpmyadmin/`
  — note the server dropdown has two entries, "MySQL" (port 3306, usually **not** running in this
  setup) and "MariaDB" (port 3307, where `smsc_db` actually lives) — pick MariaDB, or go directly
  to `http://localhost/phpmyadmin/index.php?server=2`.
- The **widget** (`chatbot-ai/backend/widget/widget.js`) is served by the FastAPI backend itself
  at `/widget.js` (see `chatbot-ai/backend/app/main.py`), not by Docker/nginx in dev. Preview it
  via `chatbot-ai/backend/widget/test-embed.html`.

**First-run gotchas** (hit and fixed once already in this environment, documented here so they
aren't rediscovered from scratch): a fresh MariaDB instance has neither the `smsc_db` database
nor the `smsc_app` user until you create them; the checked-in Laravel migrations assume a
pre-existing base schema (there's no `create_users_table` migration), so a truly empty database
needs `webapp/storage/app/backups/pre_full_reset_backup.sql` (or an equivalent dump) restored
first, migrations applied on top; and the chatbot-ai admin account created by
`python -m app.workers.seed` has no recoverable password unless `ADMIN_PASSWORD` was set
explicitly at seed time (see `chatbot-ai-backend/README.md`).

## Manual testing

[`CHATBOT_TESTING_QUESTIONS.md`](../CHATBOT_TESTING_QUESTIONS.md) (repo root of `webapp/`) is a
live, seed-data-accurate question bank for exercising both chatbot roles (`support` vs `user`)
end to end, including real message ids, real balances, and the exact wording the widget shows at
each step.
