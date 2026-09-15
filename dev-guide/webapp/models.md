# webapp — Eloquent Models

Table-level schema (columns, indexes, FKs) lives in
[`../database/schema.md`](../database/schema.md) and
[`../database/webapp-schema-raw.md`](../database/webapp-schema-raw.md) — this file covers the
PHP code layer only: what each model exposes, its relationships, and any non-obvious behavior.

Several models intentionally map to a table under a different, more domain-appropriate name
rather than duplicating a table that already covers the need — flagged individually below.

---

## User

`app/Models/User.php` — table `users`. Extends Laravel's `Authenticatable`.

- **Constants**: `ROLE_SUPPORT = 'support'`, `ROLE_USER = 'user'`.
- **`$fillable`**: `uuid, username, email, password_hash, role, status, sms_enabled`.
- **`$hidden`**: `password_hash`.
- **`$casts`**: `sms_enabled`, `dlr_enabled` → boolean.
- Auto-generates a `uuid` on create.
- **`name()`** — an `Attribute` accessor that returns `username`, purely so Breeze/Blade views
  that expect `->name` don't break (the schema has no `name` column).
- **`getAuthPassword()`** — returns `password_hash` instead of the default `password` column, so
  Laravel's standard `Auth::attempt()` machinery works unmodified against this schema's actual
  column name.
- **`getRememberTokenName()`** — returns `''` (empty): this table has no `remember_token` column,
  so "remember me" is effectively disabled rather than erroring.
- **Relationships**: `senderIds()` hasMany `SenderId`; `apiCredentials()` hasMany `ApiCredential`;
  `smppAccount()` hasOne `SmppAccount`; `hlrRequests()` hasMany `HlrRequest`; `traffic()` hasMany
  `Traffic`; `services()` hasMany `UserService`.
- **`isSupport()`** / **`isActive()`** — simple role/status checks.
- **`hasServiceEnabled(string $service)`** / **`serviceTps(string $service)`** — look up a
  `UserService` row by the related `Service.slug` (not a raw string column — `user_services` no
  longer stores the service name directly, see `Service`/`UserService` below). `$service` is any
  catalog slug (`smpp`, `api`, `hlr`, or one of the tool products), not just the three original
  messaging services.
- **`ensureBillingIdentity()`** — if the user has no `customer_id`/`account_id` yet, transactionally
  creates a minimal `customers` + `accounts` + zero-balance `balances` row and attaches them. Exists
  so new demo users don't need to understand the customer/account concept up front. **Not currently
  called from anywhere in this codebase** (no call site found in `app/` or `routes/`) — provisioning
  in the current seed data is done directly by `database/seeders/DemoDataSeeder.php` instead.

⚠️ **Registration is effectively broken**: `Auth/RegisteredUserController::store()` (stock Breeze
scaffolding, untouched) calls `User::create(['name' => ..., 'password' => ...])`, but neither
`name` nor `password` is in `$fillable` (mass assignment silently drops them) — this would leave
`username`/`password_hash` unset and fail the table's `NOT NULL` constraints. Login (`Auth::attempt`)
works fine because it goes through `getAuthPassword()`, not the `password` column directly, so
existing seeded users can still log in — it's specifically the *registration* path that's unusable
as-is.

---

## Service

`app/Models/Service.php` — table `services`. The full product catalog (SMPP/HTTP API/HLR plus the
standalone tools — see `../database/schema.md` §2).

- **`$fillable`**: `slug, name, category, description, default_tps`.
- **`$casts`**: `default_tps` → integer.
- **Relationship**: `userServices()` hasMany `UserService`.
- `slug` is the stable identifier everything else matches on (`User::hasServiceEnabled()`,
  `SmscAccountController::serviceFor()`).

## UserService

`app/Models/UserService.php` — table `user_services`. Per-user enable/disable + tps for one
catalog `Service`.

- **`$fillable`**: `user_id, service_id, enabled, tps`.
- **`$casts`**: `enabled` → boolean, `tps` → integer.
- **Relationships**: `user()` belongsTo `User`; `service()` belongsTo `Service`.
- No custom methods — this is a plain enable/tps join row. (Previously had a hardcoded `service`
  string column limited to `smpp`/`api`/`hlr`; migrated to a real `service_id` FK this session so
  any catalog product can be assigned.)

---

## SmppAccount

`app/Models/SmppAccount.php` — **maps to table `smpp_configurations`** (kept under its
pre-existing table name since the chatbot-ai integration reads it by that name directly;
`SmppAccount` is just the demo-facing model name for the same rows).

- **`$fillable`**: `uuid, user_id, host, port, system_id, password_hash, bind_type, source_ton,
  source_npi, destination_ton, destination_npi, tls_enabled, status`. Note **`connection_status`
  is deliberately excluded** — it's live SMPP bind state meant to be written only by a
  heartbeat/worker process, never by a request handler's mass assignment.
- **`$hidden`**: `password_hash`.
- **`$casts`**: `tls_enabled` → boolean.
- Auto-generates `uuid` on create.
- **Relationships**: `user()` belongsTo `User`; `allowedIps()` hasMany `SmppAllowedIp` (via
  `smpp_configuration_id`).
- **`isEnabled()`** — `status === 'active'` (provisioning state, not live connection state).
- **`isIpAllowed(string $ip)`** — checks the IP exists and is enabled in `allowedIps()`.
- **`verifyPassword(string $plain)`** — constant-time compare against the stored SHA-256 hash.
- **`regeneratePassword()`** — generates a new random 20-char password, persists only its hash,
  returns the plaintext once (caller must show it immediately — it's never retrievable again).

## SmppAllowedIp

`app/Models/SmppAllowedIp.php` — table `smpp_allowed_ips`.

- **`$fillable`**: `smpp_configuration_id, ip_address, enabled, created_by`.
- **`$casts`**: `enabled` → boolean.
- **Relationships**: `smppAccount()` belongsTo `SmppAccount` (via `smpp_configuration_id`);
  `creator()` belongsTo `User` (via `created_by`).

---

## ApiCredential

`app/Models/ApiCredential.php` — table `api_credentials`. `$timestamps = false` (the table only
has `created_at`, no `updated_at`).

- **`$fillable`**: `uuid, customer_id, user_id, api_key_id, api_secret_hash, status, scopes,
  last_used_at, expires_at, revoked_at`.
- **`$hidden`**: `api_secret_hash`.
- **`$casts`**: `last_used_at`, `expires_at`, `revoked_at`, `created_at` → datetime.
- Auto-generates `uuid` and `created_at` on create.
- **`user()`** belongsTo `User`.
- **`isActive()`** — `status === 'active'`.
- **`verifySecret(string $plain)`** — constant-time hash compare, same pattern as
  `SmppAccount::verifyPassword()`.
- **`generateFor(User $user)`** (static) — creates a new `ak_...`-prefixed key id + random secret,
  persists only the secret's SHA-256 hash, returns `[$credential, $plaintextSecret]` — same
  show-once pattern as `SmppAccount::regeneratePassword()`.

---

## Traffic

`app/Models/Traffic.php` — **maps to table `messages`** (reused directly under a spec-matching
name rather than duplicating a second table — see the model's own docblock).

- **`$fillable`**: `message_uuid, client_message_id, customer_id, user_id, account_id, direction,
  service, sender_id_ref, sender_id_value, destination_number, destination_country_code,
  message_content, status, is_sent, error_code, error_message, response, submitted_at, sent_at,
  delivered_at`.
- **`$casts`**: `is_sent` → boolean; `submitted_at`/`sent_at`/`delivered_at` → datetime.
- **`STATUS_DISPLAY_MAP`** (const array) — collapses the raw 7-value status enum
  (`QUEUED/SUBMITTED/SENT/DELIVERED/FAILED/REJECTED/EXPIRED`) down to 5 display values
  (`Pending/Sent/Delivered/Failed/Rejected`) without rewriting historical rows.
- Auto-generates `message_uuid` and defaults `submitted_at` to now() on create.
- **Relationships**: `user()` belongsTo `User`; `senderId()` belongsTo `SenderId` (via
  `sender_id_ref`).
- **`getDisplayStatusAttribute()`** — accessor backing `->display_status`, looks up
  `STATUS_DISPLAY_MAP`.

## SenderId

`app/Models/SenderId.php` — table `sender_ids`.

- **`$fillable`**: `uuid, user_id, customer_id, sender_id, sender_type, status, approved_at`.
- Auto-generates `uuid` on create.
- **Relationships**: `user()` belongsTo `User`; `countries()` hasMany `SenderIdCountry`.
- **`isEnabled()`** — `status === 'enabled'`.
- **`isEnabledForCountry(?int $countryId)`** — checks a matching, enabled `SenderIdCountry` row
  exists; returns `false` immediately for a null country id.
- **`scopeEnabled($query)`** — `where('status', 'enabled')`.

## SenderIdCountry

`app/Models/SenderIdCountry.php` — table `sender_id_countries`. Plain pivot-style model: which
countries a sender id is approved for.

- **`$fillable`**: `sender_id_id, country_id, enabled`.
- **`$casts`**: `enabled` → boolean.
- **Relationships**: `senderId()` belongsTo `SenderId`; `country()` belongsTo `Country`.

## HlrRequest

`app/Models/HlrRequest.php` — **maps to table `hlr_lookups`** (same reuse pattern as `Traffic`).

- **`$fillable`**: `uuid, user_id, destination_number, destination_country_code, status,
  hlr_result, imsi, msisdn, original_network, original_country, ported_network, ported_country,
  roaming_network, roaming_country, number_status, error_code, error_message, requested_at,
  completed_at`.
- **`$casts`**: `hlr_result` → array (JSON column); `requested_at`/`completed_at` → datetime.
- Auto-generates `uuid` and defaults `requested_at` to now() on create.
- **`user()`** belongsTo `User`.

---

## Country

`app/Models/Country.php` — table `countries`. `$timestamps = true` (explicit, though it's
Eloquent's default).

- **`$fillable`**: `iso_code, country_name, dialing_code, status`.
- **Relationships**: `senderIdCountries()` hasMany `SenderIdCountry`; `operators()` hasMany
  `Operator`; `routes()` hasMany `Route`; `routingRule()` hasOne `RoutingRule`.
- **`scopeActive($query)`** — `where('status', 'active')`.

## Operator

`app/Models/Operator.php` — table `operators`. A carrier within a country (MCC/MNC).

- **`$fillable`**: `country_id, operator_name, mcc, mnc, status`.
- **Relationships**: `country()` belongsTo `Country`; `routes()` hasMany `Route`.
- **`scopeActive($query)`** — same pattern as `Country`.

## Route

`app/Models/Route.php` — table `routes`. Outbound SMS carrier routing: which upstream carrier a
message for a destination goes out through.

- **`$fillable`**: `uuid, country_id, operator_id, carrier_name, route_identifier, priority, cost,
  currency, status`.
- **`$casts`**: `cost` → `decimal:4`.
- Auto-generates `uuid` on create.
- **Relationships**: `country()` belongsTo `Country`; `operator()` belongsTo `Operator`
  (`operator_id` null = the row is the country-wide default route).
- **`scopeActive($query)`**.
- **`scopeForDestination($query, int $countryId, ?int $operatorId = null)`** — every route
  matching a destination, operator-specific rows before the country-wide default, cheapest
  (lowest `priority` number) first. This is the lookup a routing decision would actually use, but
  nothing in this codebase currently calls it outside documentation/tests.

## RoutingRule

`app/Models/RoutingRule.php` — table `routing_rules`. One row per country, classifying it `local`
or `international`.

- **`$fillable`**: `uuid, country_id, classification, status`.
- Auto-generates `uuid` on create.
- **`country()`** belongsTo `Country`.
- **`scopeActive($query)`**.
- **`isLocal()`** — `classification === 'local'`.
- **`classify(int $countryId)`** (static) — returns `'local'`/`'international'`/**`null`** (not a
  default) if no active rule exists for that country. Deliberately *not* computed from one
  hardcoded home country — see the model's docblock and `create_routing_rules_table` migration —
  so more than one country can be marked local if the business actually operates that way.
