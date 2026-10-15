"""OpenTelemetry tracer integration and span context management."""

import time
import uuid
from typing import Dict, Any, Optional
from opentelemetry import trace
from opentelemetry.trace import Tracer

_TRACER: Optional[Tracer] = None


def get_tracer() -> Tracer:
    global _TRACER
    if _TRACER is None:
        _TRACER = trace.get_tracer("ai-governance-plane", "0.1.0")
    return _TRACER


def create_trace_context(tenant_id: str, actor: str) -> Dict[str, Any]:
    """Create a correlated trace context for control plane operations."""
    correlation_id = str(uuid.uuid4())
    return {
        "correlation_id": correlation_id,
        "tenant_id": tenant_id,
        "actor": actor,
        "timestamp_ms": int(time.time() * 1000),
    }
