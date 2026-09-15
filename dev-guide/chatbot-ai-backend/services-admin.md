# Services — Knowledge Base, Notifications & Admin Support

See [`services-conversation.md`](./services-conversation.md) for the chatbot-facing services
(conversation state machine, SMSC tool-calling, sales agent, RAG).

## `notification_service.py`

| Function | Purpose |
|---|---|
| `_serialize(notification) -> dict` | JSON shape pushed over the websocket. |
| `_recipient_user_ids(db, agent_id) -> list[UUID \| None]` | Every Super Admin/Admin always gets notified; Support Agents only if assigned to the relevant agent (`OperatorAssignment`). `agent_id=None` → admins/super-admins only (system-wide errors). |
| `notify(db, *, type, title, body=None, agent_id=None, resource_type=None, resource_id=None, link=None) -> list[Notification]` | Creates one `Notification` row per recipient, then pushes each over the websocket via `app.websocket.manager.manager.send_to_user`. |

## `email_service.py`

| Function | Purpose |
|---|---|
| `get_settings_row` / `get_or_create_settings_row` | The singleton `EmailSettings` row. |
| `send_email(db, *, to_email, subject, body_text) -> bool` | Returns `False` (no exception) if SMTP simply isn't configured yet — that's an expected admin setup gap, not a failure. Raises on a genuine send failure so callers (`lead_service`, `handoff_service`) can record an `EMAIL_FAILED` notification. Decrypts the SMTP password via `app.core.crypto` just-in-time. |

## `knowledge_service.py`

Backs the KB admin UI and the two Celery-dispatched processing jobs.

| Function | Purpose |
|---|---|
| `create_knowledge_base` / `list_knowledge_bases` / `get_knowledge_base` / `set_knowledge_base_agents` | CRUD + the many-to-many agent assignment. |
| `create_document_record(db, *, kb_id, file_name, file_path, file_size_bytes) -> KnowledgeDocument` | Row created (status `PENDING`) synchronously on upload; processing happens async. |
| `process_document(db, document)` | Extract text (`pdf_service`) → clean → chunk → embed+store (`_embed_and_store_chunks`) → mark `COMPLETED`. Any step failing marks the doc `FAILED` with the error message and fires a `KB_PROCESSING_FAILED` notification, instead of leaving it stuck in `PROCESSING`. Called by the Celery task `process_document_task`. |
| `create_scraped_site` / `get_scraped_site` | Same CRUD pattern for website sources. |
| `process_scraped_site(db, site)` | Crawl (`scraper_service.crawl`) → for each discovered URL, fetch+extract+chunk+embed, tracking per-page success/failure independently (`site.pages_processed` incremented per success; a single page failing doesn't abort the whole site) → `COMPLETED` unless **zero** pages succeeded, in which case the whole site is marked `FAILED`. Called by `process_scraped_site_task`. |
| `_embed_and_store_chunks(db, *, knowledge_base_id, document_id, scraped_page_id, source_type, texts)` | Batches texts 100 at a time (`_EMBED_BATCH_SIZE`) through `embedding_service.embed_texts`, stores one `KnowledgeChunk` row per text with its vector. |

## `embedding_service.py`

| Function | Purpose |
|---|---|
| `embed_texts(texts) -> list[list[float]]` | Batch embedding call via the configured OpenAI model/dimensions. Tests monkeypatch this to avoid real API calls. |
| `embed_query(text) -> list[float]` | Single-text convenience wrapper. |

## `pdf_service.py`

Pure functions, no I/O beyond reading the given file path.

| Function | Purpose |
|---|---|
| `extract_text(file_path) -> str` | Raises `PdfExtractionError` for an unreadable, password-protected (attempts an empty-password decrypt first), or text-empty (scanned/image-only) PDF. |
| `clean_text(text) -> str` | Collapses repeated whitespace/blank lines. |
| `chunk_text(text, chunk_size=1000, overlap=150) -> list[str]` | Word-based sliding-window chunking — word counts, not exact LLM tokens; simple and dependency-light, "good enough for retrieval granularity." |
| `estimate_token_count(text) -> int` | Rough `len(text) // 4` heuristic — display purposes only, not billing-accurate. |

## `scraper_service.py`

| Function | Purpose |
|---|---|
| `fetch_html(url) -> str` | Raises `ScrapeError` on a non-2xx response, a network error, or a non-HTML content type. |
| `extract_text(html) -> (title, cleaned_text)` | Strips script/style/nav/footer/header/noscript/svg/form tags, prefers `<main>`/`<article>`/`<body>` in that order. |
| `discover_links(html, base_url, exclude_patterns) -> list[str]` | Same-domain links only, `mailto:`/`tel:`/`javascript:`/fragment-only hrefs skipped, exclude-pattern substring filtering. |
| `crawl(base_url, *, single_url_only, max_pages, max_depth, include_subpages, exclude_patterns) -> list[str]` | Breadth-first crawl. Returns just `[base_url]` immediately if `single_url_only` or `not include_subpages`. |

## `agent_service.py`

CRUD for `Agent` + its 1:1 `AgentBranding`.

| Function | Purpose |
|---|---|
| `create_agent(db, data, created_by) -> Agent` | Also creates a default `AgentBranding` row immediately, so branding/widget endpoints never have to special-case "not yet configured" — there's always exactly one branding row per agent. |
| `get_agent` / `list_agents` | `list_agents` scopes to assigned agents only for a `SUPPORT_AGENT`-role user, supports search + status filter + pagination. |
| `update_agent(db, agent, data)` | `model_dump(exclude_unset=True)` partial update. |
| `set_status(db, agent, status)` | |
| `duplicate_agent(db, agent, created_by) -> Agent` | Copies the agent + its branding (colors, fonts, widget config, welcome text) but **not** logo/avatar files — the new agent gets its own upload rather than sharing a file reference whose lifecycle is tied to the original. |
| `delete_agent` / `get_branding` | |

## `audit_service.py`

One function: `log_action(db, *, user_id, action, resource_type=None, resource_id=None, ip_address=None, details=None)` — writes one `AuditLog` row.

## `auth_service.py`

| Function | Purpose |
|---|---|
| `AuthError` | Raised for any login failure. The route layer maps this to a generic 401 — callers must never learn whether the email or the password was the wrong part, to avoid user enumeration. |
| `get_user_by_email` / `get_user_by_id` | Eager-loads `.role`. |
| `authenticate(db, email, password) -> User` | Verifies password + `status == ACTIVE`, updates `last_login_at`. |
| `issue_tokens(user) -> TokenPair` | Access + refresh JWTs via `app.core.security`. |
| `to_user_out(user) -> UserOut` | Response-shape conversion. |

## `dashboard_service.py`

Powers the admin dashboard's stats/charts.

| Function | Purpose |
|---|---|
| `get_stats(db, agent_id=None) -> DashboardStats` | Total/active/resolved conversation counts, new/today/this-week/this-month lead counts, waiting live-agent-request count, and average first-response time. All optionally filtered to one agent. |
| `_average_response_time_seconds(db, agent_id)` | Uses a SQL window function (`LEAD(...) OVER (PARTITION BY conversation_id ORDER BY created_at)`) to pair each visitor message with the next message in the same conversation, then averages the time gap for pairs where that next message is AI/operator — i.e. genuine first-response latency, computed in one query rather than per-conversation in Python. |
| `get_charts(db, agent_id=None, days=30) -> DashboardCharts` | Conversations-per-day and leads-per-day time series, an AI-vs-human conversation split (human = currently `HUMAN_ACTIVE` *or* has an assigned operator), and a status breakdown. |

## `operator_service.py`

CRUD for admin-panel `User` accounts (the people who log into the React dashboard).

| Function | Purpose |
|---|---|
| `_role_by_name(db, role) -> Role` | Gets-or-creates the `Role` row for a `UserRole` enum value. |
| `list_operators` / `get_operator` | Eager-loads `.role` and `.agent_assignments`. |
| `create_operator(db, *, name, email, password, role, assigned_agent_ids) -> User` | Hashes the password, creates the user + one `OperatorAssignment` row per assigned agent. |
| `update_operator(db, user, *, name, role, status, assigned_agent_ids)` | Partial update; if `assigned_agent_ids` is given (not `None`), replaces the assignment set entirely (delete-all-then-recreate). |
| `delete_operator` | |

## `storage_service.py`

Local-filesystem storage behind a small interface, "so swapping in S3/MinIO later only requires
changing this module, not every caller."

| Function | Purpose |
|---|---|
| `_read_and_validate(file, max_size_mb) -> bytes` | Size + non-empty checks. |
| `save_image(file, subdir) -> (abs_path, public_url)` | Sniffs the real MIME type via `python-magic` (never trusts the client-supplied content-type) against an allow-list (PNG/JPEG/WEBP/SVG). SVG gets a second check — must contain `<svg` in the first 1000 bytes, since libmagic reports SVGs inconsistently as `text/xml`/`text/plain` across platforms. |
| `save_pdf(file, subdir) -> (abs_path, filename, size_bytes)` | Same MIME-sniffing pattern, PDF-only. |
| `delete_file(abs_path)` | No-op if the path doesn't exist. |

## `task_dispatch.py`

Thin indirection between API routes and Celery, "so tests can swap in a synchronous
implementation without needing a running worker/broker." Two functions:
`dispatch_document_processing(document_id)` and `dispatch_site_processing(site_id)` — both just
call `.delay(...)` on the corresponding Celery task from `app.workers.tasks`.

## `visitor_validation.py`

Pure regex/library validation, no I/O.

| Function | Purpose |
|---|---|
| `validate_name(text) -> str \| None` | 1–255 chars, must contain at least one Latin or Arabic letter. |
| `validate_email_address(text) -> str \| None` | Via `email_validator`, `check_deliverability=False` (format only, no DNS lookup — appropriate for a chat widget, not a signup form). |
| `validate_phone(text) -> str \| None` | 7–15 digits after stripping non-digits, plus a loose format regex. |
