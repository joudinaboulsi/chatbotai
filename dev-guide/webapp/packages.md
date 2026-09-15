# webapp — Packages

Source: `webapp/composer.json`. This is a near-stock Laravel 12 skeleton — almost no third-party
packages beyond the framework itself, since this app's actual value (SMSC domain logic) is
first-party code in `app/Models` and `app/Http/Controllers/Api`.

## Runtime (`require`)

| Package | Version | Used for |
|---|---|---|
| `php` | ^8.2 | Language runtime requirement. |
| `laravel/framework` | ^12.0 | The framework itself — routing, Eloquent ORM, migrations, queues, everything this app is built on. |
| `laravel/tinker` | ^2.10.1 | REPL (`php artisan tinker`) — used extensively during this project's development to inspect/seed the live database directly (see `database/seeders/DemoDataSeeder.php` and the many one-off `tinker --execute` snippets referenced in `../CHATBOT_TESTING_QUESTIONS.md`). |

## Dev/test (`require-dev`)

| Package | Version | Used for |
|---|---|---|
| `fakerphp/faker` | ^1.23 | Fake data generation for factories (`database/factories/UserFactory.php`). |
| `laravel/breeze` | ^2.4 | Scaffolds the auth system — every controller under `app/Http/Controllers/Auth/*` (login, registration, password reset, email verification) is Breeze-generated, not custom to this project. |
| `laravel/pail` | ^1.2.2 | Tails Laravel logs in the terminal (`php artisan pail`) — wired into the `composer dev` script alongside the app server, queue worker, and Vite dev server. |
| `laravel/pint` | ^1.24 | PHP code style fixer (Laravel's opinionated wrapper around PHP-CS-Fixer). |
| `laravel/sail` | ^1.41 | Docker-based local dev environment tooling (not necessarily what's actually running in this dev sandbox — see `docker-compose.yml` at the repo root for the real setup). |
| `mockery/mockery` | ^1.6 | Mocking library for PHPUnit tests. |
| `nunomaduro/collision` | ^8.6 | Pretty CLI error/exception rendering for `artisan` commands and test output. |
| `phpunit/phpunit` | ^11.5.50 | Test runner. **Known issue**: the suite currently fails early — see `README.md` in this folder. |

## Autoloading

PSR-4: `App\` → `app/`, `Database\Factories\` → `database/factories/`, `Database\Seeders\` →
`database/seeders/` (this last one is where `DemoDataSeeder.php` lives).

## Composer scripts worth knowing

- `composer dev` — runs the app server, queue listener, log tailer, and Vite dev server together
  (via `concurrently`).
- `composer test` — clears config cache, then runs `artisan test`.
