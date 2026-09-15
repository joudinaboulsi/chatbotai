# Core Infrastructure (`app/core/`, `app/websocket/`, `app/workers/`)

## `llm.py` — the LLM client wrapper

Every OpenAI call in the codebase goes through this module — nothing calls `AsyncOpenAI` directly
elsewhere.

- **`client() -> AsyncOpenAI`** — `@lru_cache`'d singleton. Built once, not per-call, so its httpx
  connection pool is actually reused across turns. Explicit `timeout=OPENAI_REQUEST_TIMEOUT`
  (default 60s) and `max_retries=0` override the SDK's default 600s/2-retries, which could
  otherwise pin a visitor's turn for half an hour on a hung upstream.
- **`chat_model()`** / **`tool_model()`** — separate model config for plain-prose paths
  (RAG, sales flow narration) vs. tool-calling paths (SMSC account questions, sales tools).
  `tool_model()` falls back to `chat_model()` if unset — kept separate because "dropping a tool
  call is a wrong answer, not a slow one," and the fastest/cheapest models are the least reliable
  at reliably emitting every tool call a question needs.
- **`PLAIN_TEXT_RULE`** — a system-prompt fragment every conversational service includes: no
  markdown, since the widget renders replies via `textContent` and markdown would show up as
  literal asterisks/hashes.
- **Streaming**: `set_token_sink(sink)` installs an async callback (via a `ContextVar`, so it's
  visible to everything the current async task awaits, including nested service calls) for the
  duration of one SSE turn (see `api-routes.md`'s `/message/stream`). `complete_text()` and
  `complete_with_tools()` both check for an active sink and stream through it when present,
  otherwise make a normal blocking call — **the calling service code is identical either way**,
  it never knows whether it's being streamed.
- **`complete_with_tools()`** reassembles streamed tool-call deltas by index (`pending: dict[int,
  dict]`) since a tool call's name/arguments can arrive across multiple chunks — a half-built
  function name/arguments string is never forwarded to the sink, only finished prose is.

## `smsc_client.py` — the HTTP client to `webapp`

"This is the only module in the codebase allowed to know the SMSC API's base URL/key" — every
other caller goes through `smsc_service.py` instead. **The chatbot never connects to `webapp`'s
MySQL database directly**, only this documented HTTPS API. Full endpoint contract in the module
docstring:

```
POST /auth/validate-user            {"username"} -> {user}
POST /auth/exchange-widget-token    {"token"} -> {user}
GET  /users/{user}/balance
GET  /users/{user}/traffic          ?date_from=&date_to=
GET  /users/{user}/delivery-stats   ?date_from=&date_to=
GET  /users/{user}/traffic/breakdown ?by=country|sender_id&date_from=&date_to=
GET  /users/{user}/failures         ?date_from=&date_to= — FAILED/EXPIRED/REJECTED breakdown
GET  /users/{user}/connections
GET  /users/{user}/sender-ids
GET  /users/{user}/status
GET  /users/{user}/smpp-status
GET  /users/{user}/http-api-status
GET  /users/{user}/hlr-status
GET  /users/{user}/dlr-status
GET  /users/{user}/messages/{message_id}   user-scoped: only that user's own messages
GET  /messages/{message_id}        support-only diagnostic lookup, not user-scoped
GET  /pricing                      ?service_type=sms_mt|sms_mo|hlr — platform-wide
GET  /packages                     platform-wide SMS package tiers
GET  /services                     platform-wide product/service catalog, backs the widget's Sales menu
```

Every function is a thin 2-line wrapper around `_request()`, which maps HTTP status codes to typed
exceptions: `SmscUnavailableError` (network error/timeout/5xx), `SmscAuthError` (401/403),
`SmscNotFoundError` (404), base `SmscApiError` for anything else 4xx. `get_message_status` (any
user's message, support-only — gated in `smsc_service.call_tool`, not here) vs.
`get_own_message_status` (scoped to `smsc_user_id` — the actual webapp API 404s for a mismatched
owner, so this is safe to offer a regular customer directly). `validate_user` is no longer used to
authenticate a chat session (see `services-conversation.md` — that's now `login_token`-only via
`exchange_widget_token`); it's still called once, from `app/api/routes/settings.py`'s SMSC
connection-test endpoint, as a throwaway reachability check.

## `db.py`

`create_async_engine(DATABASE_URL, pool_pre_ping=True)` + `async_sessionmaker(expire_on_commit=
False)`. `get_db()` is the FastAPI dependency every route/service chain ultimately receives its
`AsyncSession` from. `Base(DeclarativeBase)` is what every model in `app/models/` inherits from
(via `app.core.db.Base`).

## `config.py`

Single `pydantic-settings` `Settings` class, env-file driven (`.env`). Categories: app identity
(`ENVIRONMENT`, `APP_NAME`, `API_PREFIX`), `DATABASE_URL`, `REDIS_URL`, JWT (`JWT_SECRET`,
`JWT_ALGORITHM`, token expiry minutes/days), `CONFIG_ENCRYPTION_KEY` (Fernet key for encrypting
secrets at rest), OpenAI (API key/base URL/chat+tool+embedding models/timeouts/history-turn
count), CORS + widget-allowed-origins, storage backend/path/upload-size-limit, widget rate limit,
frontend/widget base URLs, and SMSC integration defaults (these only *seed* the `smsc_settings` DB
row on first run — the admin panel is the actual source of truth after that, changeable without a
redeploy). `get_settings()` is `@lru_cache`'d; `settings` is the module-level singleton everything
imports.

## `security.py`

Password hashing (`bcrypt`, with an explicit 72-byte cap since bcrypt silently truncates beyond
that rather than erroring — enforced here instead of allowing a collision) and JWT
issuance/decoding (`create_access_token`, `create_refresh_token`, `decode_token`, via `PyJWT`).

## `crypto.py`

`Fernet` symmetric encryption for at-rest secrets (`SMSCSettings.api_key_encrypted`,
`EmailSettings.smtp_password_encrypted`). `_fernet()` raises immediately with a copy-pasteable
key-generation command if `CONFIG_ENCRYPTION_KEY` isn't set, rather than failing opaquely later.

## `rate_limit.py`

One line: a `slowapi.Limiter` keyed by remote IP, backed by Redis (`storage_uri=REDIS_URL`) so
limits are shared across worker processes. Applied via `@limiter.limit(...)` decorators on every
`widget.py` route.

## `redis_client.py`

`get_redis() -> redis.Redis`, `@lru_cache`'d singleton, `decode_responses=True`.

## `celery_app.py`

`Celery("chatbot", broker=REDIS_URL, backend=REDIS_URL, include=["app.workers.tasks"])` — JSON
serialization only, `task_track_started=True`, retries the broker connection on startup (so the
worker doesn't crash-loop if Redis isn't up yet at boot).

## `app/websocket/manager.py`

An **in-memory, per-process** `ConnectionManager`: `dict[user_id, set[WebSocket]]`. Explicitly
documented as not safe for a multi-worker deployment as-is — that would need a shared pub/sub
layer (e.g. Redis) instead. `send_to_user()` silently disconnects and drops any socket that fails
to send (assumes it's gone) rather than raising. This is what `notification_service.notify()`
pushes through, and what `app/api/routes/ws.py`'s `/ws/notifications` endpoint registers/
deregisters against.

## `app/workers/tasks.py` — Celery task definitions

Two tasks, both following the same pattern: **each task owns its own DB session and asyncio event
loop** (`asyncio.run(...)`) since Celery workers are separate sync processes and can't share the
FastAPI process's loop. Both `engine.dispose()` in a `finally` block — the connection pool is a
module-level singleton, and pooled `asyncpg` connections are bound to the event loop that created
them; without disposing, the *next* task's fresh loop would try to reuse a connection tied to a
now-dead loop and blow up.

- `process_document_task(document_id)` → `knowledge_service.process_document`
- `process_scraped_site_task(site_id)` → `knowledge_service.process_scraped_site`

Both are the async-work half of what `task_dispatch.py` (`services-admin.md`) dispatches from the
knowledge-base upload/scrape routes.

## `app/workers/seed.py`

A one-off script (`python -m app.workers.seed`), not a Celery task. Idempotent (only creates rows
that don't already exist): seeds the three fixed `Role` rows (`super_admin`/`admin`/
`support_agent`) and, optionally, the first Super Admin account. The admin password is never
hardcoded — pass `ADMIN_PASSWORD` env var, or a random one is generated and printed once (not
recoverable afterward; reset via the admin panel if lost).
