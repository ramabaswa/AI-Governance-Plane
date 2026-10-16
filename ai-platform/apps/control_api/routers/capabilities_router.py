"""Tenant-authorized report of implemented and target-only platform capabilities."""

from fastapi import APIRouter, Depends

from integrations.agentgateway.translator import (
    AGENTGATEWAY_TARGET_RELEASE,
    SUPPORTED_PROVIDER_TYPES,
)
from shared.authorization.dependencies import (
    AuthenticatedUser,
    get_current_user,
    require_tenant_context,
)

router = APIRouter(prefix="/api/v1/platform", tags=["Platform Capabilities"])


@router.get("/capabilities")
async def get_platform_capabilities(
    _tenant_id: str = Depends(require_tenant_context),
    _current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Describe source-supported configuration separately from runtime verification."""
    return {
        "control_plane": {
            "inference_proxy": False,
            "configuration_path": "kubernetes_api",
        },
        "gateway": {
            "release": AGENTGATEWAY_TARGET_RELEASE,
            "supported_providers": list(SUPPORTED_PROVIDER_TYPES),
            "runtime_verified": False,
        },
        "ingress": {
            "apim": {"status": "target_only"},
            "direct_private": {"status": "target_only"},
        },
        "integrations": {
            "oidc": {"status": "configured_but_unverified"},
            "kubernetes_api": {"status": "configured_but_unverified"},
            "cmdb": {"status": "target_only"},
            "itsm": {"status": "target_only"},
            "openfga": {"status": "target_only"},
            "opa": {"status": "target_only"},
            "azure_policy": {"status": "target_only"},
            "mcp_runtime_policy_enforcement": {"status": "not_published_to_gateway"},
        },
    }
