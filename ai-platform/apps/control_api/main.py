"""FastAPI application factory and middleware configuration for AI Governance Control Plane."""

import os
import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from opentelemetry import trace

from shared.errors.exceptions import ControlPlaneError
from shared.errors.handlers import (
    control_plane_error_handler,
    validation_error_handler,
    generic_error_handler,
)
from apps.control_api.routers.auth_router import router as auth_router
from apps.control_api.routers.tenants_router import router as tenants_router
from apps.control_api.routers.applications_router import router as applications_router
from apps.control_api.routers.routes_router import router as routes_router
from apps.control_api.routers.models_router import router as models_router
from apps.control_api.routers.audit_router import router as audit_router
from apps.control_api.routers.observability_router import router as observability_router
from apps.control_api.routers.approvals_router import router as approvals_router
from apps.control_api.routers.finops_router import router as finops_router
from apps.control_api.routers.mcp_router import router as mcp_router
from apps.control_api.routers.onboarding_router import router as onboarding_router
from apps.control_api.routers.operations_router import router as operations_router
from apps.control_api.routers.policy_lifecycle_router import router as policy_lifecycle_router
from features.database import initialize_development_schema, seed_development_data
from integrations.observability.otel import TelemetryProviders, initialize_telemetry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("control-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Governance Plane Control API...")
    if os.getenv("ENVIRONMENT", "").strip().lower() == "development":
        initialize_development_schema()
        seed_development_data()
    app.state.telemetry = initialize_telemetry()
    try:
        yield
    finally:
        app.state.telemetry.shutdown()
    logger.info("Shutting down AI Governance Plane Control API...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AI Governance Plane Control API",
        version="0.1.0",
        description="Tenant-scoped control plane and management layer for agentgateway.",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS configuration
    allowed_origins = [
        origin.strip()
        for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Tenant-ID", "X-Correlation-ID"],
    )

    # Correlation ID middleware
    @app.middleware("http")
    async def add_correlation_id(request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        tracer = trace.get_tracer("ai-governance-control-api")
        with tracer.start_as_current_span("http.server.request") as span:
            span.set_attribute("http.request.method", request.method)
            response = await call_next(request)
            span.set_attribute("http.response.status_code", response.status_code)
            telemetry: TelemetryProviders | None = getattr(request.app.state, "telemetry", None)
            tenant_id = getattr(request.state, "tenant_id", None)
            if telemetry is not None and telemetry.api_request_counter is not None and tenant_id:
                telemetry.api_request_counter.add(1, {
                    "tenant_id": tenant_id,
                    "http.request.method": request.method,
                    "http.response.status_code": response.status_code,
                })
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    # Exception Handlers
    app.add_exception_handler(ControlPlaneError, control_plane_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    # Health & Readiness Probes
    @app.get("/healthz", tags=["System"])
    async def healthz():
        return {"status": "ok", "service": "control-api"}

    @app.get("/readyz", tags=["System"])
    async def readyz():
        from features.database import engine

        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1 FROM tenants LIMIT 1"))
        except SQLAlchemyError:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "service": "control-api", "dependency": "database"},
            )
        return {"status": "ready", "service": "control-api"}

    # Include API Routers
    app.include_router(auth_router)
    app.include_router(tenants_router)
    app.include_router(applications_router)
    app.include_router(routes_router)
    app.include_router(models_router)
    app.include_router(audit_router)
    app.include_router(observability_router)
    app.include_router(approvals_router)
    app.include_router(finops_router)
    app.include_router(mcp_router)
    app.include_router(onboarding_router)
    app.include_router(operations_router)
    app.include_router(policy_lifecycle_router)

    # Static files mount for Console UI if directory exists
    console_dir = os.path.join(os.path.dirname(__file__), "..", "console")
    if os.path.exists(console_dir):
        app.mount("/console", StaticFiles(directory=console_dir, html=True), name="console")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("apps.control_api.main:app", host="0.0.0.0", port=8000, reload=True)
