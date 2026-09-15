# Database Schema

> This system has **two separate databases**:
> 1. **`smsc_db`** (MySQL, this document) — the Laravel `webapp`: tenants, accounts, users,
>    messages, billing, SMSC provisioning (SMPP/HTTP API), routing, and the product catalog. This
>    is the "real business" database — the chatbot never touches it directly, only through
>    `webapp`'s internal API (see [`../webapp/routes.md`](../webapp/routes.md)).
> 2. **A Postgres database** owned by `chatbot-ai/backend` — agents, conversations, messages,
>    leads, knowledge base chunks, live-agent handoffs, notifications, dashboard users. See
>    [`../chatbot-ai-backend/models.md`](../chatbot-ai-backend/models.md) for its schema
>    (SQLAlchemy models, not raw SQL). Run via `chatbot-ai/docker-compose.yml`
>    (`pgvector/pgvector:pg16`) — reachable at `localhost:5432` when that stack is up.
>
> For the exact column-level `CREATE TABLE` of every `smsc_db` table, see the appendix:
> [`webapp-schema-raw.md`](./webapp-schema-raw.md). This file is the organized, grouped tour with
> relationships and known dead tables called out.
>
> **Local dev note**: `smsc_db` runs on WAMP's bundled **MariaDB 11.5** (service `wampmariadb64`,
> port **3307** — not the sibling MySQL 8 install on the default 3306), not the MySQL 8.0 server
> the original schema dump (`webapp-schema-raw.md`'s source) was captured from. The two engines
> agree on every table/column/constraint that matters here; the only visible differences are
> cosmetic `SHOW CREATE TABLE` formatting (e.g. `bigint(20)` vs `bigint`, per-column
> `CHARACTER SET` clauses shown explicitly under MySQL 8 but inherited silently under MariaDB).
> WAMP's `wampmariadb64`/`wampapache64` Windows services require admin rights to start via
> `net start`; run `mysqld.exe --defaults-file=<path-to-my.ini>` / `httpd.exe -f <httpd.conf>`
> directly instead if you hit "Access is denied".

## Why this schema looks the way it does

Almost none of `smsc_db`'s tables have a Laravel migration — only `webapp/database/migrations/`
files created *this session* (services, routes, routing_rules, sms_packages, the
`user_services`→`services` FK, `connection_status`) are tracked. Every other table (`users`,
`messages`, `accounts`, `customers`, `smpp_configurations`, etc.) was provisioned by an external
script/dump outside this repo before this session started. Treat `webapp-schema-raw.md` as the
source of truth for those tables' exact shape, not the migrations folder.

---

## 1. Tenancy & identity

```
customers ──< accounts ──< balances (1:1)
    │             │
    └──< users >──┘         (users.customer_id / users.account_id are denormalized
                              pointers, not a strict hierarchy — see note below)
```

| Table | Purpose |
|---|---|
| `customers` | The company/tenant. `account_type` (individual/business/reseller), `status`. |
| `accounts` | A billing account under a customer (`is_default` flags the primary one). Currency + `billing_type` (prepaid/postpaid) live here, not on `customers`. |
| `users` | A login. **`role` is either `support` or `user`** — this is the single most important column in the whole system for the chatbot's behavior (see `../../chatbot-ai/backend/app/services/smsc_ai_service.py`). A `support` user has `customer_id`/`account_id` both `NULL` — support staff have no SMSC account of their own, enforced both in seed data and in code (`smsc_service._ACCOUNT_SCOPED_TOOLS`). |
| `user_sessions`, `auth_tokens`, `user_invite_tokens` | Laravel-dashboard session/auth plumbing. Not read by the chatbot. |

**Note on `users.customer_id`/`users.account_id`**: both are marked "backward compatibility" /
"primary account ID" in column comments — a user can technically belong to one customer/account
directly (used throughout this codebase) even though `accounts.user_id` also points back the
other way. Don't assume a strict one-users-per-account rule beyond what the seed data actually
does (one owner-user per account, 1:1, in `DemoDataSeeder`).

## 2. Services catalog

```
services ──< user_services >── users
```

| Table | Purpose |
|---|---|
| `services` | The full product catalog (9 rows): `smpp`, `api`, `hlr` (category `messaging`, have a `default_tps`), plus `ams`, `easypaperless`, `excel_addon`, `survey`, `email_to_sms`, `landing_page` (category `tool`, no tps concept). Added this session — see `webapp/database/migrations/2026_09_09_100000_create_services_table.php`. |
| `user_services` | Per-user enable/disable + `tps` for one catalog entry. Used to be a hardcoded 3-value enum (`smpp`/`api`/`hlr`) directly on this table; now a proper `service_id` FK, so any catalog product can be assigned to any user. |

`App\Models\User::hasServiceEnabled($slug)` / `serviceTps($slug)` query this by `services.slug`.
`App\Http\Controllers\Api\SmscAccountController::serviceFor()`/`servicesFor()` do the same via raw
`DB::table()` joins — those two are what the chatbot's `get_smsc_smpp_status`/`http_api_status`/
`hlr_status` tools actually hit.

## 3. Messaging core

```
sender_ids ──< messages >── accounts / customers / users
   │              │
   └──< sender_id_countries    ├──< message_parts
                                ├──< message_status_history
                                └──< delivery_reports
```

| Table | Purpose |
|---|---|
| `messages` | Every SMS, in or out (`direction` MT/MO). `status` is one of `QUEUED/SUBMITTED/SENT/DELIVERED/FAILED/REJECTED/EXPIRED`. `is_sent` is `true` **only** for `SENT`/`DELIVERED` (see the `add_traffic_fields_to_messages` migration) — a `FAILED` message is *not* "sent" by this column's convention, even though it clearly left the system. `response`/`error_message` carry the human-readable reason; the SMSC-account API's `messageStatus()` endpoint reports `response ?? error_message` as "reason," so a status that wants its `error_message` to actually show must leave `response` null (a bug fixed in the seeder this session — see `DemoDataSeeder`). |
| `message_parts` | Multi-part (concatenated) SMS segments. |
| `message_status_history` | Audit trail of status transitions per message. Not currently written to by anything in this repo (no INSERT site found). |
| `delivery_reports` | DLR records, one row per delivery confirmation/failure. Denormalizes `customer_id` for fast queries. |
| `sender_ids` | Approved sender names/numbers per user. `sender_type`: alphanumeric/numeric/shortcode. |
| `sender_id_countries` | Which countries a sender id is approved to send to (`enabled` per pair). |
| `sender_id_requests` | Approval workflow for a *new* sender id (pending/approved/rejected) — separate from `sender_ids` itself, which only holds already-approved ones. |

`App\Models\Traffic` maps to the `messages` table under a demo-friendly name — it's the same
table, not a duplicate.

## 4. Connections & channels

| Table | Purpose |
|---|---|
| `smpp_configurations` | One SMPP bind config per user. `status` = provisioning state (active/inactive/suspended, admin-set). **`connection_status`** = the *live* bind state (disconnected/connecting/binding/bound/reconnecting/error) — added this session, exposed via `smppStatus()`/`connections()`, and explained to the chatbot's tool description so it doesn't confuse the two. |
| `smpp_allowed_ips` | IP whitelist per SMPP configuration. |
| `http_api_configurations` | One HTTP API config per user (callback URL, auth type). Optionally points at `api_credentials`. |
| `api_credentials` | API key/secret pairs (secret stored as SHA-256 hash only). Not populated by `DemoDataSeeder` — nothing in the chatbot path reads it, so no fake credentials were fabricated. |
| `user_api_usage` | Per-request API call log (endpoint, status, timing). Not written to by anything in this repo. |

`App\Models\SmppAccount` maps to `smpp_configurations` (demo-friendly name, same table).

## 5. Geography, pricing & routing

```
countries ──< operators ──< pricing (operator_id nullable = country default)
    │                   └──< routes (same nullable pattern, + priority for fallback)
    └──< routing_rules (1:1 per country — local/international classification)
```

| Table | Purpose |
|---|---|
| `countries` | ISO alpha-2, dialing code. 7 rows: US/GB/CA/FR/DE/AE/**SA**. SA was added this session — it's the real home market (the given package pricing is SAR), correcting an earlier guess that had assumed AE. |
| `operators` | Carrier per country (MCC/MNC), all labeled `(TEST)` — not real carrier data. |
| `pricing` | Per-country (optionally per-operator) price per message, by `service_type` (sms_mt/sms_mo/hlr), date-ranged (`effective_from`/`effective_to`). This is what the chatbot's `get_smsc_pricing` tool reads — **the only prices the AI is ever allowed to state**. |
| `routes` | Outbound carrier routing — which upstream carrier a message for a destination goes out through, with `priority` for fallback and `cost` (what *we* pay the carrier, distinct from `pricing`, what the *customer* is charged). Added this session; not yet wired into any chatbot tool. |
| `routing_rules` | One row per country classifying it `local` or `international` — configurable, not computed from a single hardcoded home country. Currently: **SA = local**, everything else international. Added this session; not yet wired into any chatbot tool. |

## 6. Billing

| Table | Purpose |
|---|---|
| `balances` | Current/reserved balance **per account** — this is the one `SmscAccountController::balance()` actually reads. |
| `transactions` | Ledger: credits/debits/sms_charge/refund/adjustment, with a `balance_after` snapshot. Not written to by anything in this repo (no automatic debiting on message send). |
| `sms_packages` | Public package tiers the sales chatbot recommends from, keyed by expected monthly volume bracket (`min_monthly_volume`/`max_monthly_volume`). Replaced with 5 real SAR-priced tiers this session (was 3 USD placeholder tiers with `price_amount = NULL`). |
| ⚠️ `sms_usage` | **Exists in the live DB with real columns** (`customer_id`, `account_id`, `usage_date`, `total_submitted/sent/delivered/failed/parts`, `total_cost`) but has **no migration and nothing in this repo writes to it**. The original `traffic()`/`deliveryStats()` controller methods queried this table; this session's fix redirected them to aggregate straight from `messages` instead (real per-message data, always populated) rather than depending on whatever process was meant to maintain `sms_usage`. If you find a job that populates `sms_usage` elsewhere, that's worth reconciling — right now it's effectively dead. |
| ⚠️ `user_balance` | A near-duplicate of `balances`, keyed by `user_id` instead of `account_id`. Nothing in this repo reads or writes it — `balances` is the live one. |

## 7. HLR & audit

| Table | Purpose |
|---|---|
| `hlr_lookups` | HLR (Home Location Register) lookup requests/results — network, roaming, porting info per number. |
| `audit_logs` | Generic action log (`action`, `resource_type`/`resource_id`, `metadata` JSON). Not written to by anything in this repo. |

---

## Seed data snapshot (as of the last `DemoDataSeeder` run)

4 real tenants + 1 support user — see
[`../../CHATBOT_TESTING_QUESTIONS.md`](../../CHATBOT_TESTING_QUESTIONS.md) for the full account
list, credentials, and expected values per account. Regenerate everything (destructive — wipes
and rebuilds every table listed above except `migrations`) with:
```
php artisan db:seed --class=DemoDataSeeder --force
```
