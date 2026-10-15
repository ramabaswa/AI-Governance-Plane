"""Optional enterprise adapters for Solo Enterprise for agentgateway."""

import os
from typing import Dict, Any, Optional


class EnterpriseOptionalAdapter:
    """Provides non-blocking hooks for optional enterprise capabilities."""

    @staticmethod
    def is_enterprise_enabled() -> bool:
        return os.getenv("SOLO_ENTERPRISE_ENABLED", "false").lower() == "true"

    @staticmethod
    def get_extended_pricing_catalog() -> Dict[str, Any]:
        """Fetch enterprise pricing catalog if available, else default pricing."""
        return {
            "enterprise_active": EnterpriseOptionalAdapter.is_enterprise_enabled(),
            "tier": "enterprise" if EnterpriseOptionalAdapter.is_enterprise_enabled() else "standard_oss",
            "sla": "99.99%" if EnterpriseOptionalAdapter.is_enterprise_enabled() else "best_effort",
        }
