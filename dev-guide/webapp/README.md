# webapp — Developer Guide

Laravel 12 application that **is** the SMSC (SMS gateway) platform: tenants (`customers`), billing
accounts, users, messages, SMPP/HTTP API provisioning, pricing, and routing. It exposes an
internal, bearer-token-guarded API (`routes/api.php`) that the separate chatbot-ai backend calls
to answer real account questions — this app never talks to the chatbot's own Postgres database or
vice versa; the only integration point is that API.

## Running it

- Dev server: `php artisan serve` (this environment's `.env` has `APP_URL=http://127.0.0.1:8001`).
- `composer dev` runs the app server, queue listener, log tailer (`pail`), and the Vite dev server
  together.
- Database: MySQL, `smsc_db`, `127.0.0.1:3307` in this dev environment (see `.env`). See
  `../database/schema.md` for the full schema.
- **Known test-suite limitation**: `php artisan test` currently fails almost immediately — the
  2026-09-07 migration `simplify_users_roles_for_demo.php` runs raw MySQL-only SQL
  (`ALTER TABLE ... MODIFY`) that the test suite's SQLite in-memory database can't parse. This is
  pre-existing and unrelated to any of this session's changes; it blocks the whole suite, not just
  new tests.

## Folder map

- **`app/Models`** — Eloquent models. See `models.md`. A few map to a pre-existing table under a
  more domain-appropriate name (`Traffic` → `messages`, `HlrRequest` → `hlr_lookups`,
  `SmppAccount` → `smpp_configurations`) rather than duplicating tables.
- **`app/Http/Controllers/Api/SmscAccountController`** — the one controller that matters for the
  chatbot integration; every method the AI's tools ultimately call goes through here. See
  `controllers.md`.
- **`app/Http/Controllers/Auth/*`, `ProfileController`** — stock Laravel Breeze dashboard
  auth/profile scaffolding, largely untouched. See `controllers.md` for the couple of places it
  doesn't quite fit this app's custom `users` schema (registration is disabled entirely because of
  this — see `routes.md`).
- **`app/Http/Middleware/SmscApiAuth`** — bearer-token guard for the internal API.
- **`routes/api.php`** / **`routes/web.php`** / **`routes/auth.php`** — see `routes.md`.
- **`database/migrations`** — only tracks schema changes made *this session* (the `services` /
  `routes` / `routing_rules` / `sms_packages` real-pricing / `connection_status` work). Almost
  every other table in `smsc_db` predates any migration for it — see the note at the top of
  `../database/schema.md`.
- **`database/seeders/DemoDataSeeder.php`** — the full demo-data reset. Truncates essentially
  every data table (tenancy, services, messages, billing, SMPP/API configs, sender ids, pricing,
  routing — everything except `migrations`) and rebuilds a consistent, realistic dataset: real
  countries/operators/pricing (including Saudi Arabia, the platform's actual home market per its
  SAR pricing), the full services catalog, 4 demo tenant companies each with a believable mix of
  enabled services and ~21 days of generated message history (with a real, non-100% delivery
  rate), plus one `support`-role user with deliberately *no* account. **Destructive** — re-running
  it wipes and regenerates everything:
  ```
  php artisan db:seed --class=DemoDataSeeder --force
  ```
  See `../../CHATBOT_TESTING_QUESTIONS.md` for the exact accounts/credentials/values it produces.

## See also

- `packages.md` — every Composer dependency.
- `models.md` — every Eloquent model.
- `controllers.md` — every controller method + the auth middleware.
- `routes.md` — every route.
- `../database/schema.md` — the database this app owns, from the table/relationship side.
- `../chatbot-ai-backend/` — the service that calls this app's API.
