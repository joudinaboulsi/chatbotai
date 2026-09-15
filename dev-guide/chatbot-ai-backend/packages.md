# Python Packages (`requirements.txt`)

One flat file — no separate dev-requirements file; a `# testing` comment marks where the
test-only packages start.

## Runtime

| Package | Version | Used for |
|---|---|---|
| `fastapi` | 0.115.0 | The web framework — every route in `app/api/routes/`. |
| `uvicorn[standard]` | 0.32.0 | ASGI server that actually runs the FastAPI app. |
| `pydantic` | 2.9.2 | Request/response validation — every file in `app/schemas/`. |
| `pydantic-settings` | 2.5.2 | `app/core/config.py`'s `Settings` class (env-var driven config). |
| `sqlalchemy` | 2.0.35 | Async ORM for every model in `app/models/`. |
| `alembic` | 1.13.3 | DB migrations (`alembic.ini`, `alembic/versions/`). |
| `asyncpg` | 0.30.0 | The actual async Postgres driver SQLAlchemy uses at runtime. |
| `psycopg2-binary` | 2.9.12 | Sync Postgres driver — used by Alembic (migrations run sync) and anywhere else sync DB access is needed. |
| `pgvector` | 0.3.5 | The `Vector` column type on `KnowledgeChunk.embedding`, and similarity-search operators used in `rag_service.py`. |
| `redis` | 5.1.1 | `app/core/redis_client.py` — caching, rate limiting, widget login tokens (`Cache::put('widget_login_token:...')`-style short-lived tokens). |
| `celery` | 5.4.0 | `app/core/celery_app.py` + `app/workers/tasks.py` — background jobs (PDF processing, site scraping, embedding generation, email sending). |
| `httpx` | 0.27.2 | Async HTTP client — `app/core/smsc_client.py`'s calls to `webapp`, and the OpenAI SDK's transport. |
| `beautifulsoup4` | 4.12.3 | HTML parsing in `scraper_service.py`. |
| `lxml` | 5.3.0 | Fast parser backend for BeautifulSoup. |
| `pypdf` | 5.0.1 | PDF text extraction in `pdf_service.py`. |
| `openai` | 1.51.2 | The LLM client — `app/core/llm.py` wraps this for every chat completion and embedding call. |
| `pyjwt` | 2.9.0 | Admin-panel session tokens — `app/core/security.py`. |
| `bcrypt` | 4.2.0 | Password hashing for `User.password_hash`. |
| `python-multipart` | 0.0.12 | Required by FastAPI for `multipart/form-data` (file uploads — PDF knowledge base docs). |
| `websockets` | 13.1 | The admin-panel live-update channel — `app/websocket/manager.py`, `app/api/routes/ws.py`. |
| `tenacity` | 9.0.0 | Listed but currently unused — no `tenacity` import anywhere in `app/`. `llm.py` and `smsc_client.py` handle retries/timeouts manually instead (see `core-infrastructure.md`). |
| `structlog` | 24.4.0 | Listed but currently unused — every module logs via the stdlib `logging` module (`logging.getLogger(...)`), not `structlog`. |
| `slowapi` | 0.1.9 | Rate limiting — `app/core/rate_limit.py`, applied to the public widget endpoints. |
| `email-validator` | 2.2.0 | Pydantic email field validation (visitor email collection, admin accounts). |
| `aiosmtplib` | 3.0.2 | Async SMTP client — `email_service.py`. |
| `cryptography` | 43.0.1 | `Fernet` symmetric encryption — `app/core/crypto.py`, used for `SMSCSettings.api_key_encrypted` and `EmailSettings.smtp_password_encrypted`. |
| `python-magic-bin` (Windows) / `python-magic` (other) | 0.4.14 / 0.4.27 | File-type sniffing for upload validation — `storage_service.py`. |

## Testing (`# testing` section)

| Package | Version | Used for |
|---|---|---|
| `pytest` | 8.3.3 | Test runner. |
| `pytest-asyncio` | 0.24.0 | Async test support (every test here is `async def`). |
| `pytest-cov` | 5.0.0 | Coverage reporting. |
| `greenlet` | 3.1.1 | Required by SQLAlchemy's async ORM under the hood. |
| `fpdf2` | 2.8.1 | Generates throwaway PDF fixtures for `pdf_service.py` tests. |
