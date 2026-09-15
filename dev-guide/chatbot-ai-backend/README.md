# chatbot-ai backend

A FastAPI service: async SQLAlchemy on Postgres (with `pgvector` for RAG embeddings), Redis for
caching/rate-limiting/short-lived tokens, and Celery for background work (PDF processing, site
scraping, embedding generation, email). It is the "brain" of the platform — it owns conversation
orchestration, the RAG knowledge base, SMSC account tool-calling, the public sales flow, live-agent
handoff, and the admin-panel API the React dashboard (`../chatbot-ai-frontend/`) talks to.

## Running it (dev)

See `../../chatbot-ai/docker-compose.yml`: a `postgres` (pgvector image) + `redis` + `backend`
(the FastAPI app, `alembic upgrade head` then `uvicorn --reload`) + `celery_worker` stack. Copy
`.env.example` to `.env` first — it documents every required setting, including how to generate
`JWT_SECRET` and `CONFIG_ENCRYPTION_KEY`. The frontend runs separately via `npm run dev` (Vite),
not in this compose file, for fast HMR.

**Note on `python -m pytest`**: `tests/conftest.py` has a session-scoped `apply_migrations`
fixture that runs Alembic against `settings.DATABASE_URL` — it needs a live Postgres instance
reachable at that URL. Bring up `docker compose up -d` (or point `DATABASE_URL` at any reachable
Postgres+pgvector instance) before running the suite; there's no environment-specific workaround
needed once that's up.

**First admin login**: the backend ships with no admin account until you seed one —
`python -m app.workers.seed` creates the fixed roles and, optionally, the first Super Admin.
Pass `ADMIN_PASSWORD=<a real password>` explicitly; if omitted, a random password is generated
and printed *once* to stdout — if that output isn't captured, the only recovery path is updating
`password_hash` directly on the `users` row (bcrypt via `app.core.security.hash_password`).
Re-running the script is safe — it only creates rows that don't already exist, so it won't
clobber a password changed since via the admin panel.

## Layout

```
app/
├── api/routes/    FastAPI routers — one file per resource (agents, conversations, widget, ...)
├── core/          Infrastructure: db session/engine, LLM client, SMSC HTTP client, security,
│                  crypto, rate limiting, redis, celery, config
├── models/        SQLAlchemy ORM models (the Postgres schema — see models.md)
├── schemas/       Pydantic request/response models, one file per resource, mirrors api/routes/
├── services/      All business logic — routes are thin, services do the work (see services.md)
├── websocket/     Admin-panel live-update connection manager
└── workers/       Celery task definitions + a one-off seed script
```

The dependency direction is strictly `api/routes` → `services` → `models`/`core`. Routes validate
input via `schemas`, call one or more `services` functions, and return a `schemas` response model.
Business logic — including every DB query — lives in `services`, not in route handlers.

## See also

- [`packages.md`](./packages.md) — every dependency and what it's used for here.
- [`models.md`](./models.md) — every table (this doubles as the Postgres schema doc — described
  from the SQLAlchemy models, not a raw dump).
- [`services-conversation.md`](./services-conversation.md) — the chatbot-facing services: conversation state machine, SMSC tool-calling, sales agent, RAG.
- [`services-admin.md`](./services-admin.md) — knowledge base, notifications, email, dashboard stats, admin-panel CRUD.
- [`leads-vs-conversations.md`](./leads-vs-conversations.md) — what each entity tracks, how a
  Conversation becomes a Lead (every trigger, with source), and why they're archived separately.
- [`api-routes.md`](./api-routes.md) — every HTTP endpoint.
- [`core-infrastructure.md`](./core-infrastructure.md) — the LLM client, SMSC HTTP client,
  security/crypto, background jobs, websockets.
