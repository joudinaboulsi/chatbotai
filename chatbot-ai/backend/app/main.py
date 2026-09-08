import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes.agents import router as agents_router
from app.api.routes.audit import router as audit_router
from app.api.routes.auth import router as auth_router
from app.api.routes.branding import router as branding_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.leads import router as leads_router
from app.api.routes.live_agents import router as live_agents_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.operators import router as operators_router
from app.api.routes.settings import router as settings_router
from app.api.routes.settings import smsc_router as smsc_settings_router
from app.api.routes.widget import router as widget_router
from app.api.routes.ws import router as ws_router
from app.core.config import settings
from app.core.rate_limit import limiter

logger = logging.getLogger("app")

app = FastAPI(title=settings.APP_NAME, docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Full detail goes to the server log only — never to the client, to
    # avoid leaking stack traces, file paths, or internal infrastructure.
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "Too many requests. Please try again later."})


class ScopedCORSMiddleware:
    """Applies WIDGET_ALLOWED_ORIGINS to the public widget API (which must be
    embeddable from arbitrary customer sites, hence typically "*") and
    CORS_ORIGINS to everything else (the authenticated admin API, which
    should only ever be called from the admin panel's own origin)."""

    def __init__(self, app: object) -> None:
        self._widget_cors = CORSMiddleware(
            app,
            allow_origins=settings.WIDGET_ALLOWED_ORIGINS,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self._admin_cors = CORSMiddleware(
            app,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http" and scope["path"].startswith(f"{settings.API_PREFIX}/widget"):
            await self._widget_cors(scope, receive, send)
        else:
            await self._admin_cors(scope, receive, send)


app.add_middleware(ScopedCORSMiddleware)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


os.makedirs(settings.STORAGE_LOCAL_PATH, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.STORAGE_LOCAL_PATH), name="media")

_WIDGET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "widget")


@app.get("/widget.js")
async def serve_widget_script() -> FileResponse:
    return FileResponse(os.path.join(_WIDGET_DIR, "widget.js"), media_type="application/javascript")

app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(agents_router, prefix=settings.API_PREFIX)
app.include_router(branding_router, prefix=settings.API_PREFIX)
app.include_router(knowledge_router, prefix=settings.API_PREFIX)
app.include_router(widget_router, prefix=settings.API_PREFIX)
app.include_router(conversations_router, prefix=settings.API_PREFIX)
app.include_router(leads_router, prefix=settings.API_PREFIX)
app.include_router(live_agents_router, prefix=settings.API_PREFIX)
app.include_router(notifications_router, prefix=settings.API_PREFIX)
app.include_router(operators_router, prefix=settings.API_PREFIX)
app.include_router(settings_router, prefix=settings.API_PREFIX)
app.include_router(smsc_settings_router, prefix=settings.API_PREFIX)
app.include_router(dashboard_router, prefix=settings.API_PREFIX)
app.include_router(audit_router, prefix=settings.API_PREFIX)
app.include_router(ws_router, prefix=settings.API_PREFIX)
