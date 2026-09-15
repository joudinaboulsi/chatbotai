# SQLAlchemy Models (`app/models/`)

This **is** the schema documentation for the chatbot-ai backend's Postgres database — there is no
live instance in this dev environment to dump `CREATE TABLE` from (Alembic migrations define the
actual DDL; these models are the ORM-side source of truth that generates them).

All models inherit two mixins from `app/models/base.py`:

- **`UUIDPKMixin`** — `id: UUID` primary key, `default=uuid.uuid4` (client-generated, not
  server `gen_random_uuid()`).
- **`TimestampMixin`** — `created_at`/`updated_at`, both `server_default=func.clock_timestamp()`,
  `updated_at` also `onupdate=func.clock_timestamp()`. Sets `__mapper_args__ = {"eager_defaults":
  True}` so Postgres's computed timestamp comes back via `RETURNING` on the same `INSERT`/`UPDATE`
  — without this, the next attribute access would trigger a lazy `SELECT` reload, which breaks
  under async SQLAlchemy (it isn't wrapped in `greenlet_spawn`).

`pg_enum(enum_cls, name)` (also in `base.py`) builds a Postgres `ENUM` column whose type name and
stored labels match hand-written Alembic migrations exactly — SQLAlchemy's bare `Mapped[SomeEnum]`
would otherwise derive the type name from the Python class name and store enum *member names*
instead of `.value` strings, silently mismatching the migration.

## Enums (`app/models/enums.py`)

| Enum | Values | Used by |
|---|---|---|
| `UserRole` | `super_admin`, `admin`, `support_agent` | Referenced conceptually; actual role storage is the `roles` table (see `Role` below), not this enum directly. |
| `UserStatus` | `active`, `inactive` | `User.status` |
| `AgentStatus` | `active`, `inactive` | `Agent.status` |
| `WidgetPosition` | `bottom_right`, `bottom_left` | `AgentBranding.widget_position` |
| `WidgetSize` | `standard`, `compact`, `large` | `AgentBranding.widget_size` |
| `KnowledgeSourceType` | `pdf`, `website` | `KnowledgeBase.source_type`, `KnowledgeChunk.source_type` |
| `ProcessingStatus` | `pending`, `processing`, `completed`, `failed` | `KnowledgeDocument.status`, `ScrapedSite.status`, `ScrapedPage.status` |
| `ScrapeMode` | `single_url`, `crawl` | `ScrapedSite.mode` |
| `ConversationStatus` | `ai_active`, `waiting_for_agent`, `human_active`, `resolved`, `closed` | `Conversation.status` — the state machine driven by `conversation_service.py` / `handoff_service.py` |
| `MessageSender` | `visitor`, `ai`, `operator`, `system` | `Message.sender_type` |
| `LeadStatus` | `new`, `contacted`, `qualified`, `converted`, `closed` | `Lead.status` |
| `LeadSource` | `pricing_request`, `demo_request`, `quote_request`, `purchase_request`, `service_inquiry`, `contact_sales_request`, `human_support_request`, `visitor_identified`, `manual` | `Lead.source`, set by `lead_detection.py` keyword matching or `sales_ai_service`'s tools. `visitor_identified` is used when a visitor's name/email/phone is captured (`save_contact_info`) with no buying intent yet — see `services-conversation.md`. |
| `LiveAgentRequestStatus` | `waiting`, `assigned`, `active`, `resolved`, `closed` | `LiveAgentRequest.status` |
| `NotificationType` | `new_lead`, `visitor_identified`, `live_agent_request`, `new_conversation`, `kb_processing_failed`, `email_failed`, `system_error` | `Notification.type` |
| `SmtpEncryption` | `none`, `ssl`, `tls` | `EmailSettings.encryption` |
| `SmscAuthScheme` | `api_key`, `bearer` | `SMSCSettings.auth_scheme` |
| `SmscSessionStatus` | `pending`, `authenticated`, `expired`, `terminated` | `SmscSession.status` — `pending` = "asked something account-specific, waiting for a username" |

## `agent.py`

### `Agent` (table: `agents`)
One configured chatbot instance (a customer of *this* platform, i.e. a business running the
widget on their site — not to be confused with `webapp`'s SMSC `users`/`customers`).

| Column | Type | Notes |
|---|---|---|
| `name`, `company_name` | `String(255)` | required |
| `industry`, `description`, `remarks` | nullable | |
| `languages` | `ARRAY(String)` | |
| `status` | `AgentStatus` enum | default `active` |
| `notification_email` | nullable | where lead/handoff notifications email to, if set |
| `created_by` | `UUID` FK → `users.id` | nullable |

Relationships: `branding` (1:1, `AgentBranding`, cascade delete), `operator_assignments` (1:many,
cascade delete).

### `AgentBranding` (table: `agent_branding`)
Widget appearance/copy, one row per agent (`agent_id` unique FK, `ondelete="CASCADE"`). Colors
(`primary_color`, `secondary_color`, `background_color`, `text_color`, `button_color` — hex
strings), `font_family`/`font_size`, `widget_position`/`widget_size` enums, `welcome_message`,
`placeholder_text`, `display_company_name`/`display_agent_name` (override names shown in the
widget UI vs. the agent's internal name).

### `OperatorAssignment` (table: `operator_assignments`)
Join table: which admin-panel `User`s may access which `Agent`s. Unique on
`(user_id, agent_id)`. Docstring note: Super Admins bypass this check in the authorization layer
but still get rows here for consistent auditing/listing.

## `audit.py`

### `AuditLog` (table: `audit_logs`)
Generic action log for the admin panel. `user_id` (nullable, `SET NULL` on delete), `action`
(indexed string, e.g. `"agent.created"`), `resource_type`/`resource_id`, `ip_address`, `details`
(`JSONB`, default `{}`).

## `conversation.py`

### `Visitor` (table: `visitors`)
A website visitor talking to one agent's widget. **Never authenticated, never admin access** —
identified only by an opaque `session_token` (unique, indexed). `name`/`email`/`phone` collected
progressively during the sales/support flow. `sales_profile` is a `MutableDict`-wrapped `JSONB`
blob (business type, use case, monthly volume, destination countries, etc.) — wrapped in
`MutableDict` specifically because a plain `JSONB` column only notices whole-attribute
reassignment; an in-place `profile["x"] = y` mutation wouldn't be tracked for the `UPDATE`
otherwise. See `sales_flow_service.py`.

### `Conversation` (table: `conversations`)
One chat thread. `status` drives the whole handoff state machine (see enum table above).
`assigned_operator_id` (nullable FK to `users.id`). Has-many `messages`, ordered by `created_at`,
cascade-delete.

### `Message` (table: `messages`)
One chat bubble. `sender_type` (visitor/ai/operator/system), `sender_user_id` (nullable, only set
for operator-sent messages), `content` (text), `message_metadata` (`JSONB` — this is where quick-
reply button definitions, `handoff_offer` markers, and chart payloads live; see
`../chatbot-ai-backend/services.md#conversation_servicepy` and `../widget.md`).

## `knowledge.py`

RAG knowledge base hierarchy: `KnowledgeBase` (many-to-many with `Agent` via the
`agent_knowledge_bases` association table) → either `KnowledgeDocument` (PDF) or `ScrapedSite`
(website) → for a scraped site, `ScrapedPage` per crawled URL → all funnel into `KnowledgeChunk`,
the actual embedded/retrievable unit.

- **`KnowledgeBase`**: `source_type` (pdf/website) is fixed at creation and enforced server-side —
  a KB is exclusively one or the other, never mixed, so the admin UI never has to guess which
  section to render.
- **`KnowledgeDocument`**: `file_name`, `file_path`, `file_size_bytes`, `status`
  (`ProcessingStatus`), `chunk_count`, `error_message`, `processed_at`.
- **`ScrapedSite`**: `base_url`, `mode` (single_url/crawl), `max_pages`, `max_depth`,
  `include_subpages`, `exclude_urls` (array), plus the same processing-status/error fields as
  `KnowledgeDocument`, plus `pages_discovered`/`pages_processed` counters.
- **`ScrapedPage`**: one row per crawled URL under a `ScrapedSite`. `content_hash` (dedup/change
  detection).
- **`KnowledgeChunk`**: belongs to exactly one of `document_id`/`scraped_page_id` (both nullable
  FKs). `embedding: Vector(settings.OPENAI_EMBEDDING_DIMENSIONS)` — a `pgvector` column, dimension
  driven by config (default 1536, matching `text-embedding-3-small`). `chunk_metadata` (`JSONB`).

## `lead.py`

### `Lead` (table: `leads`)
One lead **per conversation** — enforced by a unique constraint on `conversation_id`, which is
what lets lead creation always be an upsert instead of risking duplicate rows. `source`
(`LeadSource` enum, set by keyword detection in `lead_detection.py`), `status` (`LeadStatus`,
sales-pipeline stage), `name`/`email`/`phone`/`company` (nullable — filled in as the visitor
provides them), `assigned_operator_id`, `notes`.

## `live_agent.py`

### `LiveAgentRequest` (table: `live_agent_requests`)
A human-handoff request. `status` (`LiveAgentRequestStatus`), `assigned_operator_id`,
`requested_at`/`assigned_at`/`resolved_at` timestamps. Created by
`handoff_service.request_handoff()`.

## `notification.py`

### `Notification` (table: `notifications`)
Admin-panel bell notifications. `user_id` nullable — a `NULL` means "broadcast to any operator
with access to this agent," fanned out to per-user reads client-side by role/assignment rather
than duplicated per-user in the table. `type` (`NotificationType`), `title`, `body`,
`resource_type`/`resource_id`/`link` (deep-link target), `is_read`.

## `role.py`

### `Role` (table: `roles`)
Fixed set of roles (`super_admin`, `admin`, `support_agent`) kept as a **table**, not a bare enum
column — so role metadata (`description`) is editable without a migration. `name` unique.
Has-many `users`.

## `settings.py`

Both models below are **singleton rows** — enforced in the service layer, not the schema (no
unique constraint forcing exactly one row; the service layer is responsible for upsert-not-insert
semantics).

### `EmailSettings` (table: `email_settings`)
Global SMTP config. `smtp_password_encrypted` is a Fernet ciphertext (see `app/core/crypto.py`) —
never returned in any API response, decrypted only server-side at send time. `encryption`
(`SmtpEncryption`), `from_name`/`from_email`, `support_email`, `is_configured`.

### `SMSCSettings` (table: `smsc_settings`)
The SMSC API integration config — **the only address the chatbot backend knows for reaching
`webapp`**; it never talks to `webapp`'s MySQL database directly. `api_key_encrypted` (Fernet
ciphertext, same handling as above), `auth_scheme` (`SmscAuthScheme`), `timeout_seconds`,
`session_expire_minutes`, `is_configured`.

## `smsc.py`

### `SmscSession` (table: `smsc_sessions`)
Links one `Conversation` to a validated SMSC account. Unique on `conversation_id`. **The only way
a session becomes `AUTHENTICATED` is a real login on the website**, which hands the widget a
signed, single-use `login_token` that `smsc_service.resolve_widget_login_token` /
`authenticate_session_identity` exchange for identity — there is no "type your username in chat"
flow anymore. **Security-critical column**: `role` ("support" or "user", from the SMSC API's
identity response) — drives which tools `smsc_ai_service.py` offers this session, and is *never*
set from anything the visitor types. Every AI turn resolves the caller's SMSC identity from this
row, never from the current message — a crafted message can't switch the effective account
mid-session. Also: `smsc_user_id`, `authenticated_at`, `expires_at`. `pending_question` and
`failed_attempts` are **vestigial** — leftover columns from a removed in-chat "type your username"
flow; nothing writes a real value into either anymore (`pending_question` is only ever set to `""`
and immediately cleared).

### `SmscApiLog` (table: `smsc_api_logs`)
Audit trail for every call made to the SMSC API. **Never stores request bodies, API keys, or any
field value that could be a credential** — see `smsc_service._strip_sensitive`. `endpoint`,
`request_type`, `response_status`, `success`, `error_message`.

## `user.py`

### `User` (table: `users`)
An admin-panel login: Super Admin, Admin, or Support Agent. Doubles as "operator" elsewhere in
this codebase — one login table for every human who accesses the admin panel, scoped to specific
agents via `OperatorAssignment`. `email` unique+indexed, `password_hash`, `role_id` (FK →
`roles.id`), `status` (`UserStatus`), `last_login_at`.

> Do not confuse this `User` (chatbot-ai admin-panel login) with `webapp`'s `users` table (SMSC
> tenant/support accounts) — same name, completely different database and purpose.
