# Deploying without Docker — reference

This repo runs locally via WAMP (MariaDB/Apache) + Docker Compose (Postgres/Redis/backend/Celery)
+ Vite dev server. This doc lists what changes to run the same three pieces on a bare-metal /
VPS production host with no Docker involved.

## 1. chatbot-ai backend (FastAPI)

`chatbot-ai/docker-compose.yml` currently gives you Postgres+pgvector, Redis, the app, and Celery
for free. Without Docker you provision and run each yourself:

- **Install natively on the server**: PostgreSQL 16 + the `pgvector` extension
  (`CREATE EXTENSION vector;`), Redis, Python 3.x, and the app in a venv
  (`pip install -r requirements.txt`).
- **`.env` changes**: `DATABASE_URL` and `REDIS_URL` currently point at the Docker service names
  `postgres`/`redis` (see the compose file's env overrides) — change both to wherever
  Postgres/Redis actually run (`localhost` if same box, or a managed DB host).
- **Run as services, not `--reload`**: the compose `command` is
  `alembic upgrade head && uvicorn --reload`. In prod: run `alembic upgrade head` once per
  deploy, then run `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4` (no `--reload`)
  under **systemd** (or supervisor) so it restarts on crash/boot — that's what the container
  restart policy was giving you for free.
- **Celery worker** needs its own systemd unit too
  (`celery -A app.core.celery_app.celery_app worker`), same reasoning.
- **Regenerate secrets for prod** — don't ship the dev `JWT_SECRET` / `CONFIG_ENCRYPTION_KEY`
  values. Generate fresh ones (commands are already in `.env.example`).
- **`ENVIRONMENT=production`**.
- **Domain-facing URLs**: `CORS_ORIGINS`, `FRONTEND_BASE_URL`, `WIDGET_SCRIPT_BASE_URL` all
  currently say `localhost` — point them at real domains. `WIDGET_ALLOWED_ORIGINS=["*"]` should
  probably become a real allowlist of customer domains in prod instead of wildcard.
- **Storage**: `STORAGE_BACKEND=local` writes to `/data/storage` — pick a real, backed-up path
  (or switch to S3-compatible storage if available).
- **Bind Postgres/Redis to localhost only** and firewall everything except 80/443 (nginx) + SSH.

## 2. Admin panel — chatbot-ai frontend (React/Vite)

This is the operator dashboard (agents, conversations, leads, knowledge base, live agents,
settings) at `chatbot-ai/frontend`. `src/api/client.ts` already uses a relative
`baseURL: '/api'`, not a hardcoded `localhost:8010`, and `vite.config.ts`'s `server.proxy` block
is dev-server-only (Vite's own dev proxy) — neither needs a source change. No build-time
`VITE_*` env vars are used anywhere in `src/`, so the build is identical for every environment.

**Steps to deploy it standalone (no Docker):**

1. On the build machine (or as a CI step): `cd chatbot-ai/frontend && npm ci && npm run build`.
   This produces static files in `dist/`.
2. Copy `dist/` to the server, e.g. `/var/www/admin-panel`.
3. Point nginx at it, reverse-proxying the API paths to wherever uvicorn is now running
   (`127.0.0.1:8000` if the backend is on the same box). `frontend.nginx.conf` already has the
   exact rule set needed — reuse it, just repointing `backend:8000` → `127.0.0.1:8000`:

   ```nginx
   server {
       listen 443 ssl;
       server_name dashboard.yourdomain.com;

       ssl_certificate     /etc/letsencrypt/live/dashboard.yourdomain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/dashboard.yourdomain.com/privkey.pem;

       root /var/www/admin-panel;
       index index.html;

       # SPA client-side routing
       location / {
           try_files $uri $uri/ /index.html;
       }

       location /api/ws/ {
           proxy_pass http://127.0.0.1:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_read_timeout 3600s;
       }

       location /api/ {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           client_max_body_size 25M;
       }

       location /media/ {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
       }

       location /widget.js {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           add_header Cache-Control "public, max-age=300";
       }
   }

   server {
       listen 80;
       server_name dashboard.yourdomain.com;
       return 301 https://$host$request_uri;
   }
   ```

4. `certbot --nginx -d dashboard.yourdomain.com` for TLS (or your CA of choice).
5. Set the backend's `CORS_ORIGINS` and `FRONTEND_BASE_URL` (see §1) to
   `https://dashboard.yourdomain.com` — the panel and the API proxy share an origin through
   nginx, but the backend still validates the `Origin` header for non-proxied calls (e.g. the
   websocket upgrade) and for generating links in emails/notifications.
6. No systemd unit needed for the panel itself — it's static files served by nginx, not a
   running process. Only the backend (§1) needs process supervision.
7. **First admin login**: the backend has no admin account until you seed one — run
   `ADMIN_PASSWORD='<a real password>' python -m app.workers.seed` once, on the server, against
   the production database (`app/workers/seed.py`). Set `ADMIN_PASSWORD` explicitly; if it's
   omitted the script generates a random password and prints it *once* — if that output is lost
   (e.g. scrollback, CI log not retained) the only recovery path is updating `password_hash`
   directly in the `users` table. This is exactly what happened in local dev: the seed had been
   run without saving the generated password, so the panel was unreachable until the hash was
   reset by hand. Re-running the script afterward is safe — it only creates rows that don't
   already exist, it won't overwrite a password you've since changed via the panel.

## 3. widget.js (the embeddable customer-facing script)

No code change, but every embed snippet's `data-api-base-url` (and the backend's
`WIDGET_SCRIPT_BASE_URL`) must point to the real HTTPS backend domain — customer sites will be
HTTPS, and browsers block mixed-content `http://` widget calls.

## 4. webapp (Laravel)

This one's normally deployed without Docker anyway — standard PHP hosting:

- `.env`: `APP_ENV=production`, `APP_DEBUG=false`, `APP_URL=https://yourdomain`, generate a
  **new** `APP_KEY` for prod.
- `DB_HOST`/`DB_PORT`/`DB_DATABASE`/`DB_USERNAME`/`DB_PASSWORD` → real production MySQL/MariaDB,
  not the local WAMP instance and not the dev credentials used in local testing.
- `SESSION_SECURE_COOKIE=true`, set a real `SESSION_DOMAIN`.
- Real `MAIL_MAILER` (currently `log`).
- Rotate `SMSC_INTERNAL_API_KEY` (currently the placeholder
  `dev-smsc-internal-key-change-me`) — this must match whatever the chatbot-ai backend's
  `SMSC_API_KEY` is configured to (that one's admin-editable via the dashboard, per the
  dev-guide, not just `.env`).
- Deploy steps: `composer install --no-dev --optimize-autoloader`, `npm run build` (webapp's own
  Vite assets), `php artisan config:cache route:cache view:cache`, correct file permissions on
  `storage/` and `bootstrap/cache/`.
- Serve via nginx/Apache + php-fpm, not `artisan serve` (that's dev-only).
- `QUEUE_CONNECTION=sync` and no scheduled commands currently defined — fine as-is, nothing to
  add unless queued jobs are introduced later.

## 5. Cross-cutting

- **Reverse proxy + TLS**: one nginx in front of everything — Laravel on the main domain, static
  React build + API proxy on a subdomain (e.g. `dashboard.yourdomain`), Let's Encrypt certs.
- **Don't copy demo/seed data** into prod — the accounts and `Demo@12345` passwords used for
  local testing are dev-only. Prod should start from migrations only, with real credentials.
- **Process supervision**: systemd units replace what Docker's restart policies did — uvicorn,
  celery worker, and the two DB engines (or use managed DB services instead of self-hosting
  them).

## Open follow-up

Systemd unit files and a production nginx config haven't been written yet — draft these next
when ready to act on this checklist.
