"""Structured domain exceptions for AI Governance Control Plane."""

from typing import Any, Dict, List, Optional


class ControlPlaneError(Exception):
    """Base class for all domain exceptions."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []


class TenantNotFoundError(ControlPlaneError):
    def __init__(self, tenant_id: str):
        super().__init__(
            message=f"Tenant '{tenant_id}' not found",
            code="TENANT_NOT_FOUND",
            status_code=404,
        )


class ResourceNotFoundError(ControlPlaneError):
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            message=f"{resource_type} '{resource_id}' not found",
            code="RESOURCE_NOT_FOUND",
            status_code=404,
        )


class ResourceConflictError(ControlPlaneError):
    def __init__(self, message: str, details: Optional[List[Dict[str, Any]]] = None):
        super().__init__(
            message=message,
            code="RESOURCE_CONFLICT",
            status_code=409,
            details=details,
        )


class ValidationError(ControlPlaneError):
    def __init__(self, message: str, details: Optional[List[Dict[str, Any]]] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


class UnauthorizedError(ControlPlaneError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=401,
        )


class ForbiddenError(ControlPlaneError):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=403,
        )


class PolicyApprovalRequiredError(ControlPlaneError):
    def __init__(self, message: str = "Policy mutation requires approval in production"):
        super().__init__(
            message=message,
            code="APPROVAL_REQUIRED",
            status_code=403,
        )


class GatewayReconciliationError(ControlPlaneError):
    def __init__(self, message: str, details: Optional[List[Dict[str, Any]]] = None):
        super().__init__(
            message=message,
            code="GATEWAY_RECONCILIATION_FAILED",
            status_code=502,
            details=details,
        )


class ObservabilityUnavailableError(ControlPlaneError):
    def __init__(self, source: str, reason: str):
        super().__init__(
            message=f"{source} observability source is unavailable: {reason}",
            code="OBSERVABILITY_UNAVAILABLE",
            status_code=503,
        )
