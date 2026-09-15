# webapp — Routes

## `routes/api.php` — SMSC integration API

Entire file wrapped in `Route::middleware('smsc.auth')` (→ `App\Http\Middleware\SmscApiAuth`, see
`controllers.md`) — every route below requires a valid bearer token. This is the surface the
chatbot backend calls; see `chatbot-ai/backend/app/core/smsc_client.py`
(`../chatbot-ai-backend/core-infrastructure.md`) for the caller side.

| Method | Path | Controller@method | Purpose |
|---|---|---|---|
| POST | `/auth/validate-user` | `SmscAccountController@validateUser` | Look up a user by username. |
| POST | `/auth/exchange-widget-token` | `SmscAccountController@exchangeWidgetToken` | Redeem a dashboard-minted single-use token for a user identity. |
| GET | `/users/{id}/balance` | `@balance` | Account balance. |
| GET | `/users/{id}/traffic` | `@traffic` | Message volume, day-by-day. |
| GET | `/users/{id}/delivery-stats` | `@deliveryStats` | Delivery rate, day-by-day. |
| GET | `/users/{id}/traffic/breakdown` | `@trafficBreakdown` | Message volume grouped by country or sender ID (`by` query param). |
| GET | `/users/{id}/failures` | `@failureAnalysis` | Consolidated failure breakdown by reason/country/sender ID. |
| GET | `/users/{id}/connections` | `@connections` | All configured connection types. |
| GET | `/users/{id}/sender-ids` | `@senderIds` | This user's Sender IDs + per-country approval. |
| GET | `/users/{id}/status` | `@status` | Overall account status snapshot. |
| GET | `/users/{id}/smpp-status` | `@smppStatus` | SMPP provisioning + live connection state. |
| GET | `/users/{id}/http-api-status` | `@httpApiStatus` | HTTP API provisioning state. |
| GET | `/users/{id}/hlr-status` | `@hlrStatus` | HLR service enable/tps. |
| GET | `/users/{id}/dlr-status` | `@dlrStatus` | Delivery-report flag. |
| GET | `/users/{id}/messages/{message}` | `@ownMessageStatus` | One of *this* user's own messages, by uuid or id. |
| GET | `/messages/{message}` | `@messageStatus` | **Support-only**: any user's message, by uuid or id — not scoped by a `{id}` prefix at all. |
| GET | `/pricing` | `@pricing` | Platform-wide per-country pricing. |
| GET | `/packages` | `@packages` | Platform-wide SMS package tiers. |
| GET | `/services` | `@services` | Platform-wide product/service catalog. |

All method-level details (params, response shape) are in `controllers.md`.

## `routes/web.php` — dashboard

| Method | Path | Handler | Middleware | Purpose |
|---|---|---|---|---|
| GET | `/` | closure → `welcome` view | — | Marketing/landing page. Queries `services` (ordered messaging-category first, then alphabetically) and passes `name`/`description` for each into the view, so the landing page's product list is driven by the real catalog rather than hardcoded markup. |
| GET | `/dashboard` | closure → `dashboard` view | `auth`, `verified` | The logged-in dashboard home. `verified` is effectively a no-op here — `User` doesn't implement `MustVerifyEmail`, so Laravel's verification check is skipped entirely regardless of any `email_verified_at` state. |
| GET | `/profile` | `ProfileController@edit` | `auth` | Profile edit form. |
| PATCH | `/profile` | `ProfileController@update` | `auth` | Save profile changes. |
| DELETE | `/profile` | `ProfileController@destroy` | `auth` | Delete own account (password-confirmed). |

Then `require __DIR__.'/auth.php'` pulls in the auth routes below.

## `routes/auth.php` — authentication

| Method | Path | Handler | Middleware | Purpose |
|---|---|---|---|---|
| GET | `login` | `AuthenticatedSessionController@create` | `guest` | Login form. |
| POST | `login` | `AuthenticatedSessionController@store` | `guest` | Handle login. |
| GET | `forgot-password` | `PasswordResetLinkController@create` | `guest` | Request-reset form. |
| POST | `forgot-password` | `PasswordResetLinkController@store` | `guest` | Send reset email. |
| GET | `reset-password/{token}` | `NewPasswordController@create` | `guest` | Reset form. |
| POST | `reset-password` | `NewPasswordController@store` | `guest` | Set new password. |
| GET | `verify-email` | `EmailVerificationPromptController` | `auth` | Verification prompt page. |
| GET | `verify-email/{id}/{hash}` | `VerifyEmailController` | `auth`, `signed`, `throttle:6,1` | Verify link handler. |
| POST | `email/verification-notification` | `EmailVerificationNotificationController@store` | `auth`, `throttle:6,1` | Resend verification email. |
| GET | `confirm-password` | `ConfirmablePasswordController@show` | `auth` | Re-confirm-password form. |
| POST | `confirm-password` | `ConfirmablePasswordController@store` | `auth` | Handle re-confirmation. |
| PUT | `password` | `PasswordController@update` | `auth` | Change password while logged in. |
| POST | `logout` | `AuthenticatedSessionController@destroy` | `auth` | Log out. |

**No registration route exists** — `guest`'s route group has an explicit comment explaining why:
this app's `users` table has a domain-specific schema (`uuid`/`username`/`password_hash`) that the
stock Breeze `RegisteredUserController` (still present in the codebase, just unrouted) doesn't
target. Login-only; new users are provisioned directly in the database (see
`database/seeders/DemoDataSeeder.php`), not through a self-service signup form.
