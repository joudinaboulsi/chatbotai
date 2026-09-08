# AI Chatbot Management System

A dedicated, multi-agent AI chatbot management platform: an admin panel for configuring AI Agents (each with its own branding, knowledge base, and behavior), a RAG pipeline over PDF/website content, an embeddable website chat widget, lead capture, and live-agent handoff.

This is **not** a SaaS platform — no billing, plans, or multi-tenant organizations. It supports multiple AI Agents internally, each independently configurable.

## Architecture

```
Admin Panel (React SPA)  ─┐
                          ├─► Nginx ─► FastAPI backend ─► PostgreSQL + pgvector
Embeddable Widget (JS)   ─┘              │        │         Redis (cache, rate limiting,
                                          │        │          Celery broker, WS revocation)
                                          │        └─► Celery worker (PDF/scrape processing)
                                          └─► OpenAI (chat completions + embeddings)
```

- **Backend**: FastAPI + SQLAlchemy (async) + PostgreSQL/pgvector + Redis + Celery. REST for CRUD, a WebSocket endpoint (`/api/ws/notifications`) for realtime admin-panel notifications.
- **Frontend**: React + TypeScript + Vite + Tailwind admin dashboard.
- **Widget**: dependency-free vanilla JS (`backend/widget/widget.js`), embeds via one `<script>` tag, runs in a closed Shadow DOM, talks only to this backend (never to OpenAI directly).
- **RAG**: `scraper_service`/`pdf_service` extract and chunk content → `embedding_service` embeds chunks into `knowledge_chunks` (pgvector) → `rag_service` retrieves the closest chunks for a visitor's question and asks OpenAI to answer *only* from that context, falling back to a human-handoff offer when it can't.

## 1. Implementation Summary

| Area | Status |
|---|---|
| Authentication (JWT, bcrypt, Redis-backed refresh revocation, rate limiting) | ✅ Implemented + tested |
| RBAC (Super Admin / Admin / Support Agent, per-agent scoping) | ✅ Implemented + tested |
| AI Agents CRUD (create/list/get/update/delete/duplicate/activate/deactivate) | ✅ Implemented + tested |
| Agent Branding (colors, fonts, widget position/size, welcome message, logo/avatar upload) | ✅ Implemented + tested |
| Knowledge Base — PDF pipeline (upload → extract → chunk → embed, background via Celery) | ✅ Implemented + tested |
| Knowledge Base — website scraping (single URL / crawl, background via Celery) | ✅ Implemented + tested |
| RAG (pgvector retrieval, prompt-injection-resistant prompt construction, no-answer fallback) | ✅ Implemented + tested |
| Chatbot conversation engine (visitor info collection, state machine) | ✅ Implemented + tested |
| Lead detection + management (keyword-based, duplicate-prevention) | ✅ Implemented + tested |
| Live agent handoff (offer/accept, live agent request queue, operator assignment) | ✅ Implemented + tested |
| Realtime notifications (WebSocket push, polling fallback) | ✅ Implemented + tested |
| Email notifications (encrypted SMTP settings, lead/handoff emails, test-email endpoint) | ✅ Implemented + tested |
| Embeddable widget (Shadow DOM, branding-driven, typing indicator, handoff buttons, message polling) | ✅ Implemented + verified (see Testing Results) |
| Conversations admin (list/detail/operator messaging/assign/resolve/close) | ✅ Implemented + tested |
| Operators (RBAC-scoped CRUD, privilege-escalation guard) | ✅ Implemented + tested |
| Dashboard (real SQL aggregates — no fake data) | ✅ Implemented + tested |
| Audit log (recorded + viewable) | ✅ Implemented + tested |
| React admin panel (Dashboard, Agents, Knowledge Base, Conversations, Leads, Live Agents, Operators, Settings) | ✅ Implemented, functional-MVP visual fidelity (see UI note below) |
| Docker Compose (dev + prod) | ✅ Implemented + verified end-to-end (see Testing Results) |

**UI fidelity note**: no reference screenshot was provided for this build, so the admin panel uses a clean functional layout (Tailwind, card/table/sidebar conventions) rather than a pixel-matched design. Every button performs a real action against the real API.

## 2. Database & Migrations

Postgres + pgvector, managed with Alembic. Single migration `backend/alembic/versions/0001_initial_schema.py` creates all 19 tables (agents, agent_branding, operator_assignments, knowledge_bases, knowledge_documents, scraped_sites, scraped_pages, knowledge_chunks, roles, users, visitors, conversations, messages, leads, live_agent_requests, notifications, audit_logs, email_settings, agent_knowledge_bases) plus the `vector` extension and an ivfflat cosine-similarity index.

```bash
cd backend
alembic upgrade head      # apply
alembic downgrade base    # roll back (verified clean in both directions)
```

Timestamps use `clock_timestamp()`, not `now()` — Postgres's `now()` is frozen for the whole transaction, which would give every row created in one request an identical `created_at` and break message ordering.

## 3. Environment Variables

See `backend/.env.example`. Never commit a real `.env`. Key ones:

- `JWT_SECRET` — generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`
- `CONFIG_ENCRYPTION_KEY` — generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` (encrypts the SMTP password at rest)
- `OPENAI_API_KEY` — required for RAG answers and embeddings
- `DATABASE_URL`, `REDIS_URL` — point at your Postgres/Redis
- `WIDGET_SCRIPT_BASE_URL` — the public URL your widget snippet should load `widget.js` from

The frontend needs no build-time env vars — it calls relative `/api`, `/media`, `/widget.js` paths, which the dev proxy (Vite) or the production reverse proxy (nginx) route to the backend.

## 4. API Documentation

Full interactive docs (endpoint, method, request/response schemas, validation rules) are auto-generated from the code and always in sync: **`GET /api/docs`** (Swagger UI) and **`/api/openapi.json`**.

Endpoint groups:

```
POST   /api/auth/login | refresh | logout          GET /api/auth/me
GET/POST/PUT/DELETE /api/agents[/{id}]              POST /api/agents/{id}/duplicate|activate|deactivate
GET/PUT /api/agents/{id}/branding                   POST/DELETE /api/agents/{id}/branding/logo|avatar
GET/POST/PUT/DELETE /api/knowledge-bases[/{id}]
POST /api/knowledge-bases/{id}/pdf                  GET /api/knowledge-bases/{id}/documents
POST /api/knowledge-bases/{id}/scrape               GET /api/knowledge-bases/{id}/scraped-sites
GET  /api/conversations[/{id}]                      POST /api/conversations/{id}/messages|assign|resolve|close
GET/PUT /api/leads[/{id}]
GET  /api/live-agents                               POST /api/live-agents/{id}/assign|resolve
GET/POST/PUT/DELETE /api/operators[/{id}]
GET  /api/notifications                             POST /api/notifications/{id}/read | read-all
GET/PUT /api/settings/email                         POST /api/settings/email/test
GET  /api/dashboard/stats | charts
GET  /api/audit-logs
WS   /api/ws/notifications?token=<access_token>

Public widget API (no auth, rate-limited, isolated from the above):
GET  /api/widget/config/{agent_id}
POST /api/widget/{agent_id}/session | message | visitor | lead | handoff
GET  /api/widget/{agent_id}/messages?session_token=...&after=<message_id>
```

Authentication: `Authorization: Bearer <access_token>` (JWT, 30 min expiry) on every `/api/*` route except `/api/auth/login|refresh` and everything under `/api/widget/*`.

## 5. Widget Installation

```html
<script src="https://YOUR-DOMAIN.com/widget.js" data-agent-id="AGENT_ID"></script>
```

Get the exact snippet (with your real agent ID) from the admin panel's agent Preview & Embed tab, or `GET /api/agents/{id}/embed-code`.

- **Static HTML / PHP**: paste the tag before `</body>`.
- **Laravel**: add it to your main Blade layout (e.g. `resources/views/layouts/app.blade.php`), before `</body>`.
- **WordPress**: paste into your theme's `footer.php` before `</body>`, or use a "custom scripts" / header-footer plugin.
- **React**: add the `<script>` tag to `public/index.html`'s `<body>`, or inject it once in a top-level layout component via a `useEffect` that appends a `<script>` element to `document.body` with the same `src`/`data-agent-id` attributes.
- **Vue**: same approach as React — add to `public/index.html`, or append it in `App.vue`'s `mounted()` hook.

No npm install, no build step, no framework dependency — it's a single vanilla-JS file that isolates its styles in a closed Shadow DOM.

## 6. Admin Setup

No password is ever hardcoded. Seed the fixed roles and (optionally) the first Super Admin:

```bash
docker compose exec backend python -m app.workers.seed
# or, outside Docker: ADMIN_EMAIL=you@company.com ADMIN_PASSWORD='...' python -m app.workers.seed
```

Omit `ADMIN_PASSWORD` and a random one is generated and printed once — change it immediately after first login. Re-running the script is safe (idempotent).

## 7. Knowledge Base Setup

1. Admin Panel → Knowledge Base → **New Knowledge Base**, assign it to one or more agents.
2. **PDF**: click Upload PDF. Processing (extract → chunk → embed) runs in the background (Celery); status moves Pending → Processing → Completed/Failed, with chunk counts and error messages visible in the table. Use **Re-process** to retry.
3. **Website**: click Scrape Website, choose Single URL or Crawl (with max pages/depth, subpages, excluded URL substrings). Same background pipeline; use **Re-scrape** to refresh.
4. A knowledge base can be assigned to multiple agents; an agent only answers from the knowledge bases assigned to it.

## 8. Email Setup

Settings → Email Configuration: SMTP host/port/username/password/encryption, from name/email, support email. The password is Fernet-encrypted before being stored and is never returned by any API response. Use **Test Email Configuration** to confirm delivery before relying on it for lead/handoff notifications.

## 9. Live Agent Setup

1. Operators → **Add Operator**, choose a role (Support Agent/Admin/Super Admin — only a Super Admin can grant Super Admin) and assign them to specific agents.
2. When a visitor accepts a handoff offer, a Live Agent Request is created (status `waiting`) and Admins/assigned Support Agents get a realtime notification + email.
3. Live Agents page → **Assign to me**, or Conversations → open the conversation → **Accept Conversation**. Either action assigns the operator, activates the request, and flips the conversation to `human_active`, unblocking the reply box.
4. **Mark Resolved** / **Close Conversation** when done.

## 10. Production Deployment

Stack: Docker Compose, Nginx, PostgreSQL+pgvector, Redis, Celery — no Node/Python runtime needed on the host beyond Docker.

```bash
cp backend/.env.example backend/.env   # fill in real secrets
export POSTGRES_PASSWORD=...           # used by docker-compose.prod.yml
docker compose -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.prod.yml exec backend python -m app.workers.seed
```

This is a standalone compose file (not layered on the dev one) that builds the frontend's static bundle behind Nginx and runs the backend as a **single process** — the WebSocket notification registry (`app/websocket/manager.py`) is in-memory per-process, so scaling to multiple backend replicas needs a shared pub/sub layer (e.g. Redis) in front of it first.

Nginx (`frontend/frontend.nginx.conf`) serves the built SPA and proxies `/api/*`, `/media/*`, and `/widget.js` to the backend, so the frontend and API share one public origin.

## 11. Security Checklist

- [x] Passwords hashed with bcrypt (never stored/logged in plaintext)
- [x] JWT access tokens (30 min) + refresh tokens with Redis-backed revocation on logout
- [x] RBAC enforced server-side on every mutating route; Support Agents scoped to assigned agents only
- [x] SMTP password encrypted at rest (Fernet); never returned by any API response
- [x] Rate limiting on login (5/min) and all public widget endpoints
- [x] File upload validation by real content-sniffing (not just extension/MIME header) for images and PDFs, with size limits
- [x] Generic "Invalid email or password" on login failure (no user enumeration)
- [x] Unhandled exceptions return a generic 500 to clients; full detail goes only to server logs
- [x] Security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, HSTS in production)
- [x] Public widget API fully separated from authenticated admin API; never exposes admin data, API keys, or DB/SMTP credentials
- [x] RAG prompt construction keeps system instructions, agent context, retrieved knowledge, and the visitor's message in separate, clearly-labeled blocks, with an explicit instruction not to treat retrieved/visitor content as commands (prompt-injection mitigation)
- [x] Audit log records login, agent/branding/KB/operator/settings/lead mutations with user, IP, and timestamp
- [ ] TLS termination — not configured in the provided Nginx config; terminate TLS at your load balancer/Nginx with a real certificate before exposing this publicly
- [ ] Secrets manager integration — `.env` file is adequate for a single-host deployment; use your cloud provider's secret manager for anything larger

## 12. Testing Results

Backend: **51/51 automated tests passing** (pytest, run against a real PostgreSQL+pgvector and Redis — not mocks/SQLite), covering:

- Auth: login success/failure/inactive-user/rate-limiting, refresh, logout/revocation, garbage tokens
- Agents: CRUD, RBAC, duplicate, activate/deactivate, per-agent access scoping for Support Agents
- Branding: config update, logo upload validation (real content-sniffing — accepts a real PNG, rejects a renamed `.txt`)
- Knowledge Base: PDF extraction/chunking/embedding against a real generated PDF, invalid-PDF failure handling, website scraping against a real HTML parse, unreachable-site failure handling, list/upload/reprocess/delete routes
- **Full chatbot conversation flow**: session creation → name/email/phone collection with real validation (including a rejected invalid email) → RAG-answered question → pricing-keyword lead creation → explicit handoff request → accept → live agent request created → session persistence across reconnects → inactive-agent 404 → no-knowledge fallback message
- Message polling endpoint (operator reply delivered to a polling widget client)
- Operators: creation, agent assignment, privilege-escalation guard, self-delete guard, duplicate-email conflict
- Conversations admin: list/detail, operator messaging state guard, resolve
- Dashboard: real aggregate stats and charts (including a window-function-based average-response-time query)
- Email settings: update/retrieve without ever leaking the password
- Audit log: Super-Admin-only access
- WebSocket: connection manager unit tests (multi-socket delivery, disconnect cleanup, broken-socket resilience) + a full integration test proving a real handoff request pushes a live notification over a real WebSocket connection

Two genuine bugs were caught and fixed by this testing (not just written and assumed correct):
1. `onupdate=func.now()` timestamp columns were left "expired" after an UPDATE under async SQLAlchemy without `eager_defaults`, causing serialization crashes.
2. Postgres's `now()` is transaction-stable — every row written within one request shared an identical `created_at`, breaking message-ordering/cursor logic. Fixed by switching to `clock_timestamp()`.
A third infrastructure bug was caught via a real Docker Compose run: the Celery worker never imported `app.workers.tasks`, so background jobs would have silently gone unprocessed in production; fixed via `include=["app.workers.tasks"]`.

**Widget** (`backend/widget/widget.js`): verified with a real JS engine (Node) + real DOM (jsdom) + real HTTP calls to a live backend — 17 behavioral checks passing (branding rendering, open/close, name/email/phone collection with a rejected invalid email, handoff button flow, localStorage session persistence). Also verified: real Postgres+pgvector+Redis end-to-end via a live Docker Compose stack, including a real PDF upload triggering the actual Celery pipeline through to a (correctly failing, since no real OpenAI key was available in this environment) embedding call and a resulting failure notification.

**Frontend (React admin panel)**: type-checks and builds cleanly (`tsc -b && vite build`); the production build was served and its assets verified to load. The WebSocket notification bell was verified end-to-end through the real Vite dev proxy against the live backend.

**Not verified in this environment**: interactive visual testing of the React admin panel and the widget in an actual graphical browser — the Chrome browser automation extension was not connected in this session. Both were instead verified via real (non-visual) DOM/JS execution and a live backend as described above. Before going live, do a manual click-through in a real browser.

## Project Layout

```
backend/    FastAPI app, Alembic migrations, pytest suite, Celery tasks, widget.js
frontend/   React + Vite + TypeScript admin panel
docker-compose.yml         Local dev stack (backend + Postgres + Redis + Celery)
docker-compose.prod.yml    Production stack (adds Nginx-fronted frontend, no dev bind-mounts)
```
