# webapp — Controllers & Middleware

## `App\Http\Middleware\SmscApiAuth`

Guards every route in `App\Http\Controllers\Api\SmscAccountController` (registered on the
`smsc.auth` middleware alias — see `bootstrap/app.php` — applied to the whole group in
`routes/api.php`; see `routes.md`).

Reads `Authorization: Bearer <key>` from the request. If `config('services.smsc_internal.api_key')`
is set, the token must match it exactly (`hash_equals`) → `403` otherwise. If that config value is
empty, **any non-empty bearer token is accepted** — an explicit dev-only fallback so the chatbot
and this app can be wired together before a shared secret is agreed on. Missing token entirely →
`401`.

---

## `App\Http\Controllers\Api\SmscAccountController`

The entire surface the chatbot calls through (see
`chatbot-ai/backend/app/core/smsc_client.py` for the Python-side caller, documented in
`../chatbot-ai-backend/core-infrastructure.md`). Never exposed to the public widget directly —
only this app's own internal API, called server-to-server. Every method except
`validateUser`/`exchangeWidgetToken`/`pricing`/`packages`/`services`/`messageStatus` takes a `$id`
that's a **`users.id`**, not a customer or account id.

### Identity

| Method | Purpose | Response shape |
|---|---|---|
| `validateUser(Request)` | Look up an active user by `username` (POST body). Used when a chat visitor types their SMSC username to authenticate. | `{success, user: {id, username, role}}` or `{success: false}` |
| `exchangeWidgetToken(Request)` | Redeems a short-lived, single-use token (minted by the dashboard for its logged-in user, pulled from `Cache` with `Cache::pull` so it can never be replayed) for that user's identity — lets the widget silently identify an already-logged-in dashboard visitor. | Same shape as `validateUser`. |

### Account data (all take `int $id` = `users.id`, all call `activeUserOrFail($id)` first → `404` if the user doesn't exist or isn't `status = active`)

| Method | Purpose | Queries | Response shape |
|---|---|---|---|
| `balance(int $id)` | Real balance for the user's account. | `accounts` → `balances` | `{balance, reserved_balance, available_balance, currency, low_balance_threshold, account_number, account_name, billing_type}`. `404` with `{error}` if no account/balance row exists. |
| `status(int $id)` | Overall account status snapshot. | `users`, `accounts`, `servicesFor()` | `{username, email, role, status, account_number, account_name, billing_type, sms_enabled, smpp_enabled, http_api_enabled, hlr_enabled, dlr_enabled, last_login_at}` |
| `smppStatus(int $id)` | SMPP provisioning + live connection state. | `serviceFor($id, 'smpp')`, `smpp_configurations`, `allowedIpsFor()` | `{enabled, tps, configured, status, connection_status, host, port, system_id, bind_type, tls_enabled, allowed_ips}` — `connection_status` is the *live* bind state (disconnected/connecting/binding/bound/reconnecting/error), distinct from `status` (provisioning: active/inactive/suspended). If no `smpp_configurations` row exists, returns just `{enabled, tps, configured: false}`. |
| `httpApiStatus(int $id)` | HTTP API provisioning state. | `serviceFor($id, 'api')`, `http_api_configurations` | `{enabled, tps, configured, status, callback_url, authentication_type}` (or `{enabled, tps, configured: false}`). |
| `hlrStatus(int $id)` | HLR service enable/tps. | `serviceFor($id, 'hlr')` | `{enabled, tps}` |
| `dlrStatus(int $id)` | Delivery-report flag. | `users.dlr_enabled` | `{enabled}` |
| `connections(int $id)` | All configured connection types at once. | `smpp_configurations`, `http_api_configurations` | `{connections: [...]}`, one entry per configured type (`type: 'smpp'` includes `connection_status`; `type: 'http_api'` doesn't have one). |
| `traffic(int $id, Request)` | Message volume over a date range, with a day-by-day breakdown for charting. | `messages`, grouped by `DATE(submitted_at)` | `{date_from, date_to, total_submitted, total_sent, total_delivered, total_failed, daily: [{date, submitted, sent, delivered, failed}, ...]}`. Every calendar day in range appears in `daily` even with zero messages (see `dailyDateRange()` below) — a chart built from this should never show a gap that looks like traffic stopped. |
| `deliveryStats(int $id, Request)` | Delivery rate over a date range, same day-by-day shape. | `messages` | `{date_from, date_to, sent, delivered, failed, delivery_rate_percent, daily: [{date, sent, delivered, failed, delivery_rate_percent}, ...]}` |
| `trafficBreakdown(int $id, Request)` | Same message data as `traffic()`, grouped by destination country or by sender ID instead of by day — backs the chatbot's "By Country"/"By Sender ID" drill-down buttons. `by` query param (`country`\|`sender_id`, default `country`); `422` if it's anything else. | `messages`, grouped by `destination_country_code` or `sender_id_value` | `{by, date_from, date_to, groups: [{label, submitted, delivered, failed, delivery_rate_percent}, ...]}`, ordered by `submitted` descending. |
| `failureAnalysis(int $id, Request)` | Consolidated failure breakdown for the "Failure Analysis" button — the same failed messages `traffic()`/`deliveryStats()` count, grouped three ways (reason, country, sender ID) in one call instead of three round trips. | `messages` where `status IN (FAILED, EXPIRED, REJECTED)` | `{date_from, date_to, total_failed, top_reason, by_reason: [{label, count}, ...], by_country: [...], by_sender_id: [...]}` — each `by_*` array capped at the top 5; `top_reason` is computed server-side (`COALESCE(error_message, status)` of the single most common row), never left for the model to guess. |
| `senderIds(int $id)` | This user's Sender IDs and which countries each is approved for — backs "was my sender ID approved"/"which countries is it enabled for" questions. | `sender_ids`, `sender_id_countries` → `countries` | `{sender_ids: [{sender_id, sender_type, status, approved_at, countries: [{country, iso_code, enabled}, ...]}, ...]}` |
| `messageStatus(string $message)` | **Support-only** diagnostic lookup — any user's message, by uuid or numeric id, no `$id` scoping at all. Not gated by role in this controller itself (only `SmscApiAuth`'s bearer token) — the chatbot only *offers* this as a tool to `role=support` sessions; enforcement of who gets asked is entirely on the Python side. | `messages` → `users.username` for the owner | `{message_id, username, service, sender_id, destination, country, status, is_sent, reason, submitted_at, sent_at, delivered_at}`. `reason` is `response ?? error_message` — for `FAILED`/`REJECTED` messages, `response` must be left `null` at write time or the real `error_message` never surfaces (see `../database/schema.md` §3 and `webapp/database/seeders/DemoDataSeeder.php`). `404` if nothing matches. |
| `ownMessageStatus(int $id, string $message)` | User-scoped counterpart — same lookup but filtered by `user_id = $id` too, so a message belonging to someone else 404s exactly like a nonexistent one (no leak of "it exists but isn't yours"). | `messages` (filtered by `user_id`) | Same shape as `messageStatus()` minus `username`. |

### Platform-wide (not scoped to any one user)

| Method | Purpose | Response shape |
|---|---|---|
| `pricing(Request)` | Per-country price per message for a `service_type` (`sms_mt`/`sms_mo`/`hlr`, query param, default `sms_mt`). Only returns operator-independent rows (`whereNull('pricing.operator_id')`) that are currently effective by date. This is the only source of truth the AI is allowed to state a price from. | `{service_type, rates: [{country, iso_code, price_per_message, currency}, ...]}` |
| `packages()` | Active `sms_packages` tiers, ordered by `display_order`. The public sales chatbot recommends from this list by matching a prospect's stated volume against `min_monthly_volume`/`max_monthly_volume`. | `{packages: [{slug, name, min_monthly_volume, max_monthly_volume, price_amount, currency, billing_period, coverage_notes, features}, ...]}` — `price_amount` can be `null` if a tier is genuinely unpriced (the chatbot must never invent one). |
| `services()` | Full product/service catalog (messaging + tool categories), messaging rows first then alphabetical by name. Backs the chatbot's Sales menu so it always offers every real product instead of a hand-maintained subset. | `{services: [{slug, name, category, description}, ...]}` |

### Private helpers

- **`activeUserOrFail(int $id)`** — the auth gate every user-scoped method opens with; `404`s
  (not `401`/`403`) if the user doesn't exist or isn't active, so a bad id looks identical to a
  nonexistent one from the caller's perspective.
- **`serviceFor(int $userId, string $service)`** / **`servicesFor(int $userId)`** — join
  `user_services` → `services` and filter/key by `services.slug`, returning the same shape as
  when `user_services.service` was a plain string column (pre this session's migration to a real
  FK) — so `status()`/`smppStatus()`/`httpApiStatus()`/`hlrStatus()` needed no changes when that
  migration landed.
- **`allowedIpsFor(int $smppConfigurationId)`** — `smpp_allowed_ips` rows for one SMPP config,
  ordered by IP.
- **`resolveDateRange(Request)`** — `date_from`/`date_to` query params, defaulting to the last 30
  days if omitted.
- **`dailyDateRange(string $dateFrom, string $dateTo)`** — every calendar date in an inclusive
  range as a string array, used to zero-fill `traffic()`/`deliveryStats()`'s `daily` output.

---

## Auth controllers (`App\Http\Controllers\Auth\*`)

Stock Laravel Breeze scaffolding, essentially unmodified — standard session-based dashboard
login, not custom to this project's SMSC domain.

| Controller | Purpose |
|---|---|
| `AuthenticatedSessionController` | Login (`create` shows the form, `store` calls `LoginRequest::authenticate()` + regenerates the session) and logout (`destroy`). Works against this app's custom schema because `User::getAuthPassword()` returns `password_hash` — `Auth::attempt()` doesn't care that the column isn't literally named `password`. |
| `RegisteredUserController` | Registration form + handler — **deliberately not routed** (see `routes/auth.php`'s comment: "Registration is disabled for this demo: smsc_db.users has a domain-specific schema... that the stock Breeze RegisteredUserController does not target. Login only."). The controller itself is still present but unreachable; if it ever were wired up it would mass-assign `name`/`password`, neither of which is in `User::$fillable` (`username`/`password_hash` are). |
| `ConfirmablePasswordController` | "Confirm your password" prompt before a sensitive action (Breeze default). |
| `EmailVerificationNotificationController` / `EmailVerificationPromptController` / `VerifyEmailController` | Email-verification flow. ⚠️ Same latent issue as registration — the `users` table has no `email_verified_at` column, so `hasVerifiedEmail()`/marking verified would fail if actually exercised. |
| `NewPasswordController` / `PasswordResetLinkController` | "Forgot password" email + reset-form flow. |
| `PasswordController` | Change-password-while-logged-in form handler. |

## `App\Http\Controllers\ProfileController`

Also stock Breeze. `edit()`/`update()` show and save the dashboard profile form; `update()` sets
`email_verified_at = null` when the email changes — ⚠️ same schema mismatch as above (no such
column). `destroy()` deletes the account after re-confirming the current password. None of this
is wired into the chatbot path — it's dashboard-only, standard Laravel behavior.
