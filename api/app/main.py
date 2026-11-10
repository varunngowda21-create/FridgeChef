import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_v1_router
from app.api.routes import health
from app.core.config import get_settings
from app.core.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_error_handler,
)
from app.core.logging import setup_logging
from app.core.ratelimit import general_rate_limiter, get_client_identity
from app.db.session import engine

# 1. Setup structured logging
setup_logging()
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting FridgeChef AI API in %s mode", settings.ENVIRONMENT)

    # Basic DB connectivity verification on startup
    try:
        with engine.connect():
            logger.info("Successfully connected to PostgreSQL database at %s", settings.DATABASE_URL.split("@")[-1])
    except Exception as e:
        logger.error("Failed to connect to PostgreSQL database on startup: %s", e)

    yield

    logger.info("Shutting down FridgeChef AI API")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="FridgeChef AI API",
        version="1.0.0",
        description="Smart Indian recipe generator and fridge inventory management API",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # General Sliding-Window Rate Limiting Middleware (PRD NFR-022: 200 req/min)
    @app.middleware("http")
    async def general_rate_limit_middleware(request: Request, call_next):
        path = request.url.path
        if (
            "/health" in path
            or path in ("/docs", "/redoc", "/openapi.json")
        ):
            return await call_next(request)

        client_id = get_client_identity(request)
        try:
            general_rate_limiter.check_and_record(client_id)
        except AppError as exc:
            return await app_error_handler(request, exc)

        return await call_next(request)

    # Request ID & Access Logging Middleware (Outermost to ensure X-Request-ID on all responses)
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = req_id

        start_time = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        response.headers["X-Request-ID"] = req_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Emit HSTS strictly under production HTTPS conditions (PRD Sec 15.1, RFC 6797 Sec 7.2)
        from app.core.security import is_request_secure

        if settings.APP_ENV == "production" and is_request_secure(request):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Skip logging health checks in noisy detail
        if "/health" not in request.url.path:
            logger.info(
                "%s %s %s (%s ms) [req_id=%s]",
                request.method,
                request.url.path,
                response.status_code,
                latency_ms,
                req_id,
            )

        return response

    # Exception Handlers
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Routers
    app.include_router(api_v1_router)

    # Top-level health aliases per PRD Section 11.1 & 14.1
    app.include_router(health.router)
    app.include_router(health.router, prefix="/api")

    return app


app = create_app()
