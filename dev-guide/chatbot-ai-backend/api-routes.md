# API Routes (`app/api/routes/`)

Every router is mounted under `API_PREFIX = "/api"` (`app/core/config.py`). Auth dependencies
(from `app/api/deps.py`):

- **`get_current_user`** — decodes the Bearer JWT access token, loads the `User` + `.role`. Any
  admin-panel route needing "logged in" uses this.
- **`require_roles(*allowed: UserRole)`** — `get_current_user` + role check.
- **`require_agent_access`** — `get_current_user` + Super Admin/Admin bypass, or Support Agent
  must have an `OperatorAssignment` row for the `agent_id` path param.
- **No auth at all** — every route under `widget.py` (public, rate-limited instead).

A few routes are registered directly on `app` in `app/main.py`, not under any router file:
`GET /api/health` (liveness check), `GET /widget.js` (serves the embeddable widget script from
`app/widget/widget.js`), and a static file mount at `/media` (serves everything
`storage_service.py` saves — branding logos/avatars, uploaded PDFs).

## `widget.py` — the public, unauthenticated widget API

**The most important router** — this is everything the actual customer-facing `widget.js` calls.
Explicit docstring warning at the top: "must never expose anything beyond what a visitor should
see — no admin fields, no other visitors' data, no internal IDs beyond the conversation/visitor
the caller's own `session_token` already grants them." Every route is rate-limited via
`app/core/rate_limit.py`'s `limiter` at `RATE_LIMIT_WIDGET_PER_MINUTE` (default 30/min).

| Method | Path | Purpose |
|---|---|---|
| GET | `/widget/config/{agent_id}` | Branding/config the widget needs before it even opens a session (colors, welcome message, position/size). |
| POST | `/widget/{agent_id}/session` | Creates or resumes a visitor + conversation. If `login_token` is given (dashboard-embedded widget), resolves it via `smsc_service.resolve_widget_login_token` first — if the reused conversation's existing `SmscSession` was authenticated as a *different* username than the token now resolves to (a stale `session_token` in localStorage from a previous login), the old conversation is closed and a fresh one started instead of silently answering with the wrong account's data — then binds identity via `authenticate_session_identity` and picks the greeting variant accordingly (support vs. named user vs. anonymous). Returns the full message history for an existing conversation, or just the fresh greeting for a new one. |
| POST | `/widget/{agent_id}/message` | **The main turn**: calls `conversation_service.handle_visitor_message` and returns whatever reply message(s) it produced. |
| POST | `/widget/{agent_id}/message/stream` | Server-sent-events twin of `/message`. Runs the *exact same* `handle_visitor_message` call — no duplicated routing/state machine — with a token sink installed via `llm.set_token_sink()` so services push prose through an `asyncio.Queue` as it streams, staying unaware anyone's listening. Emits `token` events as text arrives, then one `done` event with the identical payload the non-streaming endpoint returns (so a client that ignores `token` events still works), or an `error` event on failure (with a DB rollback). |
| GET | `/widget/{agent_id}/messages` | Polling fallback: messages since a given message id (`after`), for a widget instance not using SSE. |
| POST | `/widget/{agent_id}/visitor` | Updates name/email/phone (each independently validated via `visitor_validation.py`, 400 on invalid). |
| POST | `/widget/{agent_id}/lead` | Explicit lead creation (used by e.g. a "request a callback" widget action distinct from conversation-driven lead detection). |
| POST | `/widget/{agent_id}/handoff` | Resolves a `handoff_offer` yes/no click via `conversation_service.handle_handoff_choice`. |

`_detect_locale(request)` reads `Accept-Language` — `ar` if the primary tag is Arabic, `en`
otherwise. Every fixed widget string is bilingual based on this; AI-generated text is a separate
instruction to the model to reply in the visitor's language.

## `agents.py` (`/agents`) — auth: `require_agent_access` per-agent, `require_roles` for delete

| Method | Path | Purpose |
|---|---|---|
| GET | `/agents` | Paginated list (search + status filter), scoped to assigned agents for a Support Agent. |
| POST | `/agents` | Create (+ default branding row). |
| GET | `/agents/{agent_id}` | |
| PUT | `/agents/{agent_id}` | Partial update. |
| DELETE | `/agents/{agent_id}` | **Super Admin only.** |
| POST | `/agents/{agent_id}/duplicate` | Clones the agent + branding (not logo/avatar files). |
| POST | `/agents/{agent_id}/activate` / `/deactivate` | Status toggle. |
| GET | `/agents/{agent_id}/embed-code` | The `<script>` snippet a customer pastes onto their site. |

## `branding.py` (`/agents/{agent_id}/branding`) — auth: `require_agent_access`

GET/PUT the branding row, plus `POST`/`DELETE /logo` and `POST /avatar` (uploads go through
`storage_service.save_image`).

## `conversations.py` (`/conversations`) — auth: `get_current_user` + per-conversation agent-access check

| Method | Path | Purpose |
|---|---|---|
| GET | `/conversations` | Paginated list, scoped to the operator's assigned agents. Filterable by `agent_id`, `status`, `has_lead`; sortable (`newest`/`oldest`/`most_messages`). Response includes a `status_counts` breakdown (count per `ConversationStatus`) alongside the page of items. |
| GET | `/conversations/{conversation_id}` | Full detail incl. message history. |
| POST | `/conversations/{conversation_id}/messages` | An operator sending a message manually (during a human-handoff conversation). |
| POST | `/conversations/{conversation_id}/resolve` / `/close` | Status transitions. |
| POST | `/conversations/{conversation_id}/assign` | Assigns an operator. |

## `leads.py` (`/leads`) — auth: `get_current_user`

GET (paginated list, filterable), GET one, PUT (update status/notes/assignment).

## `live_agents.py` (`/live-agents`) — auth: `get_current_user`

GET (list), POST `/{request_id}/assign`, POST `/{request_id}/resolve` — the operator-side half of
`handoff_service`'s workflow.

## `knowledge.py` (`/knowledge-bases`) — auth: `get_current_user`

| Method | Path | Purpose |
|---|---|---|
| GET / POST | `/knowledge-bases` | List / create. |
| GET / PUT / DELETE | `/knowledge-bases/{kb_id}` | |
| POST | `/knowledge-bases/{kb_id}/pdf` | Upload → `storage_service.save_pdf` → `knowledge_service.create_document_record` → `task_dispatch.dispatch_document_processing` (async Celery). |
| GET | `/knowledge-bases/{kb_id}/documents` | |
| POST | `/knowledge-bases/{kb_id}/documents/{doc_id}/reprocess` | Re-dispatches processing. |
| DELETE | `/knowledge-bases/{kb_id}/documents/{doc_id}` | |
| POST | `/knowledge-bases/{kb_id}/scrape` | Create a `ScrapedSite` → `task_dispatch.dispatch_site_processing`. |
| GET | `/knowledge-bases/{kb_id}/scraped-sites` | |
| POST | `/knowledge-bases/{kb_id}/scraped-sites/{site_id}/rescrape` | |
| DELETE | `/knowledge-bases/{kb_id}/scraped-sites/{site_id}` | |

## `operators.py` (`/operators`) — auth: `_manage_roles` (Super Admin/Admin), delete is Super Admin only

Standard CRUD over admin-panel `User` accounts — mirrors `operator_service.py` 1:1.

## `settings.py` — two routers: `/settings/email` and `/settings/smsc`

| Method | Path | Purpose |
|---|---|---|
| GET | `/settings/email` | |
| PUT | `/settings/email` | **Super Admin only.** |
| POST | `/settings/email/test` | Sends a test email. |
| GET | `/settings/smsc` | |
| PUT | `/settings/smsc` | **Super Admin only.** Encrypts the API key before storing. |
| POST | `/settings/smsc/test` | Verifies the SMSC API is actually reachable with the configured credentials. |

## `dashboard.py` (`/dashboard`) — auth: `get_current_user`

GET `/stats`, GET `/charts` — thin wrappers around `dashboard_service`.

## `audit.py` (`/audit-logs`) — auth: Super Admin only

GET, paginated.

## `notifications.py` (`/notifications`) — auth: `get_current_user`

GET (list, scoped to the current user), POST `/{notification_id}/read`, POST `/read-all`.

## `auth.py` (`/auth`) — no auth required on login/refresh; `get_current_user` on the rest

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/login` | Email+password → `TokenPair`. Rate-limited to 5/minute per IP. |
| POST | `/auth/refresh` | Refresh token → new `TokenPair`. |
| POST | `/auth/logout` | |
| GET | `/auth/me` | Current user info. |

## `ws.py` — WebSocket, token passed as a query param

`GET /ws/notifications?token=...` (upgraded to `ws://`) — the live admin-panel notification
channel, backed by `app/websocket/manager.py`. `notification_service.notify()` pushes here.
