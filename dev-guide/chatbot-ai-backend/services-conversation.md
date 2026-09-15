# Services — Conversation, Sales & SMSC (the chatbot's core)

These modules are what actually talks to visitors. See [`services-admin.md`](./services-admin.md)
for the knowledge-base/notification/admin-panel-support services.

## `conversation_service.py` — the core state machine

The heart of the system. Docstring at the top of the file lays out the state machine:

```
AI_ACTIVE --(visitor asks for a human / AI can't help)--> WAITING_FOR_AGENT
WAITING_FOR_AGENT --(operator accepts)--> HUMAN_ACTIVE
HUMAN_ACTIVE --(operator resolves)--> RESOLVED
RESOLVED/AI_ACTIVE --(operator closes)--> CLOSED
```

Within `AI_ACTIVE`, an **anonymous prospect**'s turns are entirely owned by
`sales_flow_service` (name/business/use-case/volume collection through to a package
recommendation) once `handle_visitor_message` has ruled out an account-specific question. A
visitor identified via the dashboard's widget login token isn't a prospect — they keep an older
Sales/Support/Reporting quick-reply menu and lighter name/email/phone collection.

**There is no in-chat "type your username" authentication path.** The only way an `SmscSession`
becomes `AUTHENTICATED` is a real login on the website, which hands the widget a signed,
single-use `login_token` that `smsc_service.resolve_widget_login_token` /
`authenticate_session_identity` exchange for identity (see `app/api/routes/widget.py`'s
`create_session`). A guest with no such token who asks an account-specific question is just told
to log in (`smsc_ai_service.LOGIN_REQUIRED_MESSAGE`) — there's no "please type your username" step.

| Function | Purpose |
|---|---|
| `get_or_create_visitor(db, *, agent_id, session_token, ip_address, user_agent) -> (Visitor, str)` | Looks up a visitor by session token or creates one, returning `(visitor, token)`. |
| `get_or_create_conversation(db, *, agent, visitor) -> (Conversation, bool)` | Reuses an open conversation (status in `AI_ACTIVE`/`WAITING_FOR_AGENT`/`HUMAN_ACTIVE`) or creates a new one. `bool` = whether it's new. |
| `build_greeting_message(db, *, conversation, locale, name, is_support) -> Message` | The first message a visitor sees — greeting + root quick-reply menu **in one bubble**. A `support`-role login gets a plain greeting, no menu. A named (dashboard-identified) visitor gets the Sales/Support/Reporting/Human-Agent menu. An anonymous visitor (`name is None`) gets `sales_flow_service.greeting_text()` instead — no menu, since that flow asks for name inline. |
| `handle_visitor_message(db, *, agent, branding, conversation, visitor, text, quick_reply, locale) -> list[Message]` | **The main entry point**, called by `app/api/routes/widget.py` for every visitor turn. Routing order: (1) if conversation isn't `AI_ACTIVE`, stay silent (human is handling it); (2) `sf_`-prefixed quick replies go straight to `sales_flow_service.handle_sales_step`; (3) other quick replies are either canned sales/support/reporting/report-drill-down questions (expanded to their equivalent free-text question and fed through the normal pipeline, gated on name/email/phone collection first via `_next_collection_prompt` unless already SMSC-identified) or self-contained menu actions (`_handle_quick_reply`); (4) `_handle_smsc_message` gets first crack at free text (account-specific questions against an already-authenticated session, or the "please log in" deflection); (5) if unclaimed, `quick_reply is None`, and the visitor isn't already SMSC-identified, hand off to `sales_flow_service` (anonymous prospect); (6) otherwise: lead-source keyword detection, explicit-handoff-request detection, then fall through to `rag_service.generate_reply` (knowledge base). |
| `_build_sales_menu(db, conversation_id) -> list[dict]` | The Sales quick-reply menu is built from `webapp`'s real product catalog (`smsc_service.get_services_public`), not a hand-maintained list, so it never goes stale as products are added. Falls back to the static `_SALES_MENU` if the SMSC integration is disabled/unreachable. |
| `_resolve_sales_catalog_question(db, conversation_id, quick_reply)` | Expands a `sales_<slug>` click that isn't one of the hand-phrased `_SALES_QUESTIONS` (i.e. any catalog product beyond SMPP/HLR/HTTP-API/campaign) into a generic canned question, by matching the slug back against the same catalog. |
| `_handle_quick_reply(db, *, agent, conversation, visitor, quick_reply, locale) -> list[Message] \| None` | Routes `menu_sales` (dynamic catalog menu), `menu_support` (top-level category menu — see `_SUPPORT_MENU`/`_SUPPORT_SUBMENUS` two-level support navigation), `menu_reporting`, `menu_human` (show the Sales/Support/Billing/Account/Something-else reason-capture menu before creating a handoff), the 5 reason values (create the handoff with that reason attached), `continue_ai`, and `support_other` (asks the visitor to describe their issue in free text instead of immediately offering a handoff). Returns `None` if the value isn't recognized, so the caller falls back to free-text handling. |
| `_handle_smsc_message(db, *, agent, conversation, visitor, text, locale) -> list[Message] \| None` | Credential-request deflection first. Then: no session or not `AUTHENTICATED` yet → if the text looks account-specific (`smsc_ai_service.is_account_specific`), reply with `LOGIN_REQUIRED_MESSAGE` (no PENDING/username step); otherwise return `None`. `AUTHENTICATED` session → a switch-account request terminates the session; an explicit human-handoff request returns `None` so the caller's normal handoff-offer flow picks it up (an authenticated session has no "talk to a human" tool and would otherwise just answer conversationally); everything else goes through `smsc_ai_service.answer_account_question` with both RAG context and the account tools, and the reply gets `_with_report`'s chart/stats/peak/low/progress/breakdown metadata plus drill-down report-action buttons when applicable. Returns `None` if none of that applies (falls through to RAG/sales). |
| `_with_report(metadata, report, locale)` | Copies `smsc_ai_service.answer_account_question`'s structured `report` dict (`chart`/`stats`/`peak`/`low`/`progress`/`breakdown` — all computed server-side from real tool data) onto a reply's metadata, plus `report_actions` (Traffic Trend / Failure Analysis / By Country / By Sender ID drill-down buttons — see `_REPORT_ACTIONS`) when the report came from a top-level traffic/delivery-stats call. |
| `_recent_history(db, conversation_id, limit=12) -> list[tuple[str, str]]` | Last N messages as `(role, content)` pairs for LLM context, mapping `visitor`→`user`, `ai`/`operator`→`assistant`. |
| `handle_handoff_choice(db, *, agent, conversation, visitor, accepted, locale) -> Message` | Resolves a `handoff_offer` yes/no click — either creates the handoff or replies "no problem, how else can I help." |

**Support menu is two levels deep**: the top-level `_SUPPORT_MENU` lists categories
(Connection & Service Status, Sending & Delivery, Sender ID & Routing, Account & Billing,
Reporting & Lookups, Technical/Other) that branch into `_SUPPORT_SUBMENUS` leaves, each with a
"Back" option routing back to `menu_support`. Report replies (traffic/delivery-stats) can attach
`_REPORT_ACTIONS` drill-down buttons (`report_traffic_trend`/`report_failure_analysis`/
`report_by_country`/`report_by_sender_id`) that re-enter the exact same SMSC tool-calling pipeline
via `_REPORT_ACTION_QUESTIONS`, not a separate code path.

**Localization**: every fixed widget-shown string lives in the `_STR` dict, keyed by id, each with
`en`/`ar` values — `locale` is detected server-side from the `Accept-Language` header per request.
AI-generated content (RAG/SMSC answers) is not translated this way; the LLM is instructed to reply
in the visitor's language directly.

## `smsc_ai_service.py` — SMSC account tool-calling

Kept deliberately separate from `rag_service`: RAG answers "what is SMPP," this module answers
"what is *my* SMPP status." The model is never allowed to choose *whose* account it queries —
every tool call is dispatched with the `smsc_user_id` from the caller's already-authenticated
`SmscSession`; arguments the model supplies for identity are simply not part of any tool's schema.

| Function | Purpose |
|---|---|
| `is_credential_request(text) -> bool` | Fuzzy-matches password/API-key/secret-token keywords (typo-tolerant via `difflib.SequenceMatcher`, threshold 0.84). |
| `is_account_specific(text) -> bool` | Fuzzy-matches balance/traffic/delivery/connection/message-status phrasing. Deliberately excludes bare "pricing"/"sender id" — those are legitimate topics for an anonymous prospect talking to the public sales agent too, not just an authenticated account. |
| `is_switch_request(text) -> bool` | "switch account" / "log me out" style phrasing. |
| `_tools_for_role(role) -> list[dict]` | **`role == "support"` gets `_PLATFORM_TOOLS + _SUPPORT_TOOLS` only** — no account-scoped tools, since support staff have no SMSC account of their own. Any other role gets `_ACCOUNT_TOOLS + _PLATFORM_TOOLS`. |
| `_system_instructions_for_role(role) -> str` | Base instructions + today's date + the role-specific block (`_USER_ROLE_INSTRUCTIONS` or `_SUPPORT_ROLE_INSTRUCTIONS`). |
| `_build_chart(tool_name, result) -> dict \| None` | Builds `{type, title, labels, series}` line-chart data **straight from a tool's raw JSON result**, never from anything the model said — only for `get_smsc_traffic`/`get_smsc_delivery_stats` when the result has a `daily` array with ≥2 points. |
| `_build_stats(tool_name, result) -> list[dict] \| None` | Builds KPI stat tiles (label/value/tone) for `get_smsc_traffic`, `get_smsc_delivery_stats`, and `get_smsc_balance` from the tool's raw result — replaces the model reciting totals as prose. |
| `_build_report_extras(tool_name, result) -> dict \| None` | For `get_smsc_traffic`/`get_smsc_delivery_stats` only: computes `peak`/`low` activity highlights (contiguous low-traffic days collapsed into ranges, today called out as "partial"), a delivery-rate `progress` bar, and a `header` (title + period), plus `show_actions: True` so the reply gets the drill-down `_REPORT_ACTIONS` buttons. |
| `_build_breakdown_rows(tool_name, result) -> dict \| None` | Turns `get_smsc_traffic_breakdown` (by country/sender ID) or `get_smsc_failure_analysis` results into compact labeled rows for the widget. |
| `answer_account_question(db, *, session_row, conversation_id, visitor_message, history, rag_context_block) -> (str, dict \| None)` | The tool-calling loop: builds the system+history+message list, calls the LLM with `_tools_for_role(session_row.role)`, executes any tool calls via `smsc_service.call_tool`, feeds results back, gets the final text answer. Returns `(answer_text, report)` — `report` is a dict combining whichever of `chart`/`stats`/`peak`/`low`/`progress`/`header`/`breakdown`/`show_actions` apply (`get_smsc_traffic` wins the primary chart/stats/peak/low/progress slot over `get_smsc_delivery_stats` if both were called in one turn, since it has strictly more data), or `None` if nothing tool-derived is worth attaching. |

**Tool list** (`_ACCOUNT_TOOLS`): `get_smsc_balance`, `get_smsc_traffic`, `get_smsc_delivery_stats`,
`get_smsc_traffic_breakdown` (by country or sender ID), `get_smsc_failure_analysis`
(FAILED/EXPIRED/REJECTED breakdown by reason/country/sender ID),
`get_smsc_connections`, `get_smsc_sender_ids`, `get_smsc_account_status`, `get_smsc_smpp_status`,
`get_smsc_http_api_status`, `get_smsc_hlr_status`, `get_smsc_dlr_status`,
`get_smsc_own_message_status`. `_PLATFORM_TOOLS`: `get_smsc_pricing` (not account-scoped, same for
everyone). `_SUPPORT_TOOLS` (support role only): `get_smsc_message_status` (any user's message,
by id alone — vs. `get_smsc_own_message_status` which is filtered to the caller).

## `smsc_service.py` — the actual SMSC API calls

"The only place that turns a validated SMSC session into actual SMSC API calls." Three enforced
security invariants (per the module docstring): (1) the SMSC identity used for every call always
comes from the caller's `SmscSession` row, never from anything the visitor/LLM supplied that turn;
(2) any field name that looks like a credential is stripped from responses before they reach the
AI or audit log (`_strip_sensitive`, regex `pass(word)?|secret|token|api[_-]?key|private[_-]?key|
credential`); (3) failures never produce an invented answer — callers get a typed exception.

| Function | Purpose |
|---|---|
| `get_settings_row` / `get_or_create_settings_row` | The singleton `SMSCSettings` row. |
| `is_enabled(db) -> bool` | Whether the integration is turned on *and* configured. |
| `_build_config(db) -> SmscConfig` | Decrypts the API key, raises `SmscUnavailableError` if not configured. |
| `get_packages(db, *, conversation_id) -> list[dict] \| None` | Platform-wide SMS package tiers for the **public sales chatbot** — not gated behind an authenticated session, since anonymous prospects have none. Returns `None` on any failure (caller falls back gracefully, never surfaces a raw error). |
| `get_services_public(db, *, conversation_id) -> list[dict] \| None` | Platform-wide product/service catalog backing the widget's dynamic Sales menu (`conversation_service._build_sales_menu`) — same not-gated-behind-a-session pattern as `get_packages`. Returns `None` on any failure; caller falls back to a hardcoded menu. |
| `get_pricing_public(db, *, conversation_id, service_type="sms_mt") -> list[dict] \| None` | Same pattern, for pricing — also doubles as the "which countries do you cover" answer, since the country list in the response *is* the coverage list. |
| `_strip_sensitive(data)` | Recursively strips any dict key matching the credential regex. |
| `_log_call(...)` | Writes a `SmscApiLog` row (via `_strip_sensitive`) for every SMSC API call, success or failure. |
| `get_session(db, conversation_id) -> SmscSession \| None` | Also flips an expired `AUTHENTICATED` session to `EXPIRED` in-line (`expires_at` in the past). |
| `start_pending(db, *, conversation_id, visitor_id, pending_question) -> SmscSession` | Creates (or reuses/resets, if `EXPIRED`/`TERMINATED`) a `PENDING`-status session row. Only called internally now, from `authenticate_session_identity` — there is no visitor-facing "ask for username" flow that calls this directly anymore. |
| `resolve_widget_login_token(db, *, conversation_id, login_token) -> (smsc_user_id, username, role) \| None` | Exchanges the dashboard's short-lived, **single-use** `login_token` (via `smsc_client.exchange_widget_token`) for the identity it carries, **without** binding it to a conversation yet — split out so a caller (see `app/api/routes/widget.py`'s `create_session`) can learn *who* the token belongs to before deciding *which* conversation it should apply to (needed to detect a stale `session_token` now representing a different logged-in person). Returns `None` on any failure. |
| `authenticate_session_identity(db, *, conversation_id, visitor_id, smsc_user_id, username, role) -> SmscSession` | Binds an already-resolved identity to `conversation_id`'s `SmscSession` row: sets `status=AUTHENTICATED`, `smsc_user_id`/`username`/`role`/`authenticated_at`/`expires_at`, overwriting any prior identity. |
| `identify_from_widget_login_token(db, *, conversation_id, visitor_id, login_token) -> (username, role) \| None` | Convenience wrapper for the common case (a brand-new conversation, nothing to reconcile): resolves the login token and immediately binds it via `authenticate_session_identity`. Returns `None` on any failure — callers fall back to the normal flow without surfacing an error. |
| `terminate_session(db, session_row)` | Sets `TERMINATED`, clears identity fields. |
| `SmscToolError` | Exception type every tool-calling failure raises, carrying a `user_message` safe to show. |
| `call_tool(db, *, session_row, conversation_id, tool_name, arguments) -> dict` | Dispatches one of the `_TOOL_ENDPOINTS` to the actual `smsc_client` HTTP call. Enforces: session must be `AUTHENTICATED`; `required_role` per-tool check (e.g. `get_smsc_message_status` needs `role == "support"`); **`_ACCOUNT_SCOPED_TOOLS` check** — rejects any `{user}`-scoped tool for a support-role session outright, even though `smsc_user_id` is technically set (closes the gap where support could otherwise query their own nonexistent account). |

`_TOOL_ENDPOINTS` maps every tool name to `(endpoint_template, http_method, required_role)`,
including `get_smsc_traffic_breakdown` (`/users/{user}/traffic/breakdown`),
`get_smsc_failure_analysis` (`/users/{user}/failures`), and `get_smsc_sender_ids`
(`/users/{user}/sender-ids`). `_ACCOUNT_SCOPED_TOOLS` is **derived automatically** from which
endpoints contain `{user}` in their template — not a separately maintained list, so it can't drift
out of sync.

**Note**: `smsc_client.validate_user` (`POST /auth/validate-user`) still exists and is still
called — but only from `app/api/routes/settings.py`'s SMSC connection-test endpoint, as a
throwaway round trip to confirm the base URL/API key work. It is no longer part of the
visitor-facing authentication flow (see above).

## `sales_ai_service.py` ⚠️ Do not modify — powers the live web sales channel

**Documentation only — this file must not be edited.** It's what the public-facing sales chatbot
(anonymous prospects on the company website) runs on, in production, right now.

3620 lines, but structurally simple: ~85% of the file is one very long, heavily-structured system
prompt (`_BASE_SYSTEM_INSTRUCTIONS`) plus tool schema definitions — the remainder is helper
functions, most of them small pure country/name/email/phone-matching utilities.

| Symbol | Purpose |
|---|---|
| `_BASE_SYSTEM_INSTRUCTIONS` | The prompt. Casts the model as "a proactive, curious, friendly and persuasive SMSC Sales Agent," with an explicit **"ABSOLUTE RULE — CONVERSATION STATE PERSISTENCE"** section: once the visitor provides information, it stays known for the whole conversation unless they explicitly change it, and a tool call must never be treated as resetting that state or restarting discovery. |
| `_TOOLS` | 5 function-calling tools offered to the model: `get_packages` (real package tiers — **must** be called before naming a price/feature), `get_pricing` (real per-country rates — the *only* source of truth for coverage/pricing, **must** be called before stating either), `generate_quote` (deterministic cost estimate for a country + monthly volume), `request_sales_contact` (creates a real lead — requires name + email + phone + reason, triggers a human handoff), `save_contact_info` (records name/email/phone the moment the visitor gives any of them, even with no buying intent — does **not** trigger a handoff, unlike `request_sales_contact`; just makes the visitor show up as identified instead of "Anonymous" right away). |
| `_REASON_TO_LEAD_SOURCE` | Maps `request_sales_contact`'s `reason` argument (`quote_request`/`purchase_request`/`contact_sales_request`) to a `LeadSource` enum value. |
| `_normalize_country` / `_country_matches` / `_build_country_choices` / `_assistant_requested_country` / `_looks_like_country_answer` / `_extract_known_country` | Country-name matching/disambiguation helpers — free-text country names are matched against the real pricing table's country list, with choice-building for ambiguous matches. |
| `_message_contains_email` / `_message_contains_phone` / `_looks_like_name_answer` / `_looks_affirmative` / `_extract_confirmed_name` / `_assistant_requested_name` / `_assistant_requested_phone` / `_assistant_requested_email` | Deterministic (non-LLM) detectors used by `_capture_contact_from_reply` to recognize when the visitor's latest message actually answers a preceding assistant prompt for their name/email/phone. |
| `_capture_contact_from_reply(db, *, agent, conversation, visitor, previous_assistant_message, visitor_message)` | **Backstop for `save_contact_info`**: the prompt tells the model to call that tool the instant the visitor gives contact info, but tool-calling discipline isn't perfectly reliable, so this deterministically re-checks the previous-assistant-turn/visitor-reply pair and saves the value (+ `create_or_get_lead(..., source=LeadSource.VISITOR_IDENTIFIED)`) itself if the model didn't. Called from `answer_sales_message` before the LLM call runs. |
| `_needs_contact_nudge` / `_build_contact_reminder` / `_build_known_contact_reminder` | Build reminder blocks nudging the model to ask for missing contact info, or re-asserting contact info already known, so it doesn't re-ask. |
| `_build_conversation_state_reminder` | Builds a reminder block re-asserting what's already known (name, business, country, volume, etc.) so the model doesn't re-ask. |
| `_run_tool(db, *, tool_name, arguments, agent, conversation, visitor) -> dict` | Executes one of the 5 tools — `get_packages`/`get_pricing` call `smsc_service.get_packages`/`get_pricing_public` (the same real data, unauthenticated variants); `generate_quote` computes from real pricing; `request_sales_contact` calls `lead_service.create_or_get_lead` + `handoff_service`; `save_contact_info` validates and saves whichever fields were given and calls `create_or_get_lead(..., source=LeadSource.VISITOR_IDENTIFIED)` without a handoff. |
| `_deterministic_fallback` | A non-LLM fallback answer path (used when the model call fails). |
| `answer_sales_message(db, *, agent, branding, conversation, visitor, visitor_message, history, rag_context_block, locale) -> str` | The entry point, called from `sales_flow_service.handle_sales_step`. Runs `_capture_contact_from_reply` first (deterministic backstop, see above), then builds the message list (system prompt with `{language}` substituted, optional RAG context, history, the visitor's message) and runs the tool-calling loop. |

**Note**: `app/services/sales_ai_service - Copy.py` also exists alongside this file — an untracked
backup copy, not imported or referenced anywhere in the app. Not part of the running service;
ignore it.

## `sales_flow_service.py`

Thin entry point for anonymous-prospect conversations — the actual discovery/recommendation/
objection-handling/closing behavior all lives in `sales_ai_service` (an adaptive tool-calling
agent, not a fixed question sequence). This module owns only: the bilingual greeting text, one
explicit-handoff fast path worth bypassing the LLM for, and lightweight lead-source keyword
tagging.

| Function | Purpose |
|---|---|
| `greeting_text(locale) -> str` | The anonymous-visitor greeting (asks for name + business type inline). |
| `_recent_history(db, conversation_id, limit=10)` | Same pattern as `conversation_service._recent_history`. |
| `handle_sales_step(db, *, agent, branding, conversation, visitor, text, quick_reply, locale) -> list[Message]` | If the text is an explicit "talk to a human" request, handoff immediately without an LLM round trip. Otherwise: tag a lead source from keywords if present (idempotent per conversation — catches the first "pricing"/"demo" mention even before the model's own `request_sales_contact` tool call fires), then delegate to `sales_ai_service.answer_sales_message`. |

## `rag_service.py` — knowledge-base retrieval

Keeps four things strictly separate in the prompt — system instructions, agent branding context,
retrieved chunks, and the visitor's raw message — so a visitor's message (or content buried in
scraped/PDF text) can't override system behavior. Retrieved content is explicitly labeled
untrusted reference material, not instructions.

| Function | Purpose |
|---|---|
| `retrieve_relevant_chunks(db, agent_id, query, top_k=5) -> list[KnowledgeChunk]` | Embeds the query, does a `pgvector` cosine-distance search scoped to the agent's assigned knowledge bases, filtered to distance ≤ 0.6 (a weak match is treated as "not actually relevant" rather than forced into an answer). |
| `get_context_block(db, agent_id, query) -> str \| None` | Public helper for callers outside the normal chat flow (e.g. `smsc_ai_service` blending in general product knowledge alongside account data) that want RAG context without the full `generate_reply` completion. |
| `generate_reply(db, *, agent, branding, visitor_message, history) -> (str, list[KnowledgeChunk])` | Full RAG answer: retrieves chunks, returns the fixed `NO_ANSWER_FALLBACK` immediately (no LLM call) if nothing relevant was found, otherwise builds the prompt and calls the LLM. |

## `lead_detection.py`

Pure keyword matching, no LLM. `_KEYWORDS`: a list of `(LeadSource, [phrases])` pairs — pricing,
demo, quote, purchase, contact-sales, human-support, service-inquiry. `detect_lead_source(text)`
returns the first matching source or `None`. `is_explicit_handoff_request(text)` is just
`detect_lead_source(text) == LeadSource.HUMAN_SUPPORT_REQUEST`.

## `lead_service.py`

| Function | Purpose |
|---|---|
| `get_lead_for_conversation(db, conversation_id) -> Lead \| None` | |
| `create_or_get_lead(db, *, agent, visitor, conversation, source, notes=None) -> (Lead, bool)` | **Idempotent per conversation** (one lead per conversation, enforced by a DB unique constraint on `conversation_id`) — but backfills `name`/`email`/`phone`/`notes` onto an existing lead if they were null and the visitor has since supplied them (a lead is often created from an early keyword match before any contact info exists). Re-notifies staff if the backfill is specifically what makes the lead actionable for the first time (email arriving where it was previously null) — not on every subsequent backfill. |
| `_notify_new_lead` | Fires an in-app `notify()` + best-effort email to the agent's `notification_email` (or the global support email) — wrapped in its own SAVEPOINT (`db.begin_nested()`), not just try/except, since `create_or_get_lead` now runs on the hot path of nearly every conversation (see `LeadSource.VISITOR_IDENTIFIED`/`sales_ai_service.save_contact_info` above) and a plain try/except wouldn't stop a failed flush here from aborting the whole outer transaction. |

## `handoff_service.py`

| Function | Purpose |
|---|---|
| `get_active_request(db, conversation_id) -> LiveAgentRequest \| None` | Status in `WAITING`/`ASSIGNED`/`ACTIVE`. |
| `request_handoff(db, *, agent, visitor, conversation, reason=None) -> LiveAgentRequest` | Idempotent (returns the existing active request if one exists). Creates the request, flips the conversation to `WAITING_FOR_AGENT`, creates/backfills a lead, fires an in-app notification (title includes `reason` if given, so the reason-capture menu's choice shows up for the operator), and best-effort emails the agent/support address (body includes a `Reason:` line). |
| `assign_operator` / `activate` / `resolve` | State transitions an operator takes in the dashboard. |
