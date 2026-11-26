"""FastAPI entrypoint. Business logic lives in app/domain, app/ml, app/optimizer, app/services."""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import inventory, meta, ops, risk, transfers
from app.config import get_settings
from app.domain.errors import DomainError


class JsonFormatter(logging.Formatter):
    """Structured logs that Cloud Logging parses (severity + message); no PII is ever logged."""

    def format(self, record: logging.LogRecord) -> str:
        out = {"severity": record.levelname, "message": record.getMessage(), "logger": record.name}
        if record.exc_info:
            out["exception"] = self.formatException(record.exc_info)
        for k in ("request_id", "path", "status", "ms"):
            if hasattr(record, k):
                out[k] = getattr(record, k)
        return json.dumps(out)


def _setup_logging() -> None:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [h]
    root.setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)


_setup_logging()
log = logging.getLogger("raktsetu")
settings = get_settings()
if settings.env == "prod" and settings.auth_mode in ("demo", "both") and settings.demo_auth_secret == "dev-only-change-me":  # noqa: S105
    raise RuntimeError("DEMO_AUTH_SECRET must be set (Secret Manager) when demo auth is enabled in prod")

app = FastAPI(
    title="RaktSetu API",
    version="1.0.0",
    description="AI-powered predictive blood network: forecasting, probabilistic stockout risk, "
                "expiry-aware rebalancing and coordinated transfers. Decision support only.",
)
app.add_middleware(
    CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def access_log(request: Request, call_next):
    rid = request.headers.get("x-cloud-trace-context", uuid.uuid4().hex)[:32]
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = round((time.perf_counter() - t0) * 1000, 1)
    response.headers["X-Request-Id"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path not in ("/healthz",):
        log.info("request", extra={"request_id": rid, "path": request.url.path, "status": response.status_code, "ms": ms})
    return response


@app.exception_handler(DomainError)
async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse({"detail": exc.message, **exc.details}, status_code=exc.status_code)


for r in (meta.router, inventory.router, risk.router, transfers.router, ops.router):
    app.include_router(r)
