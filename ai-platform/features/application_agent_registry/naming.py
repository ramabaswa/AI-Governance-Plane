"""Stable Kubernetes names for tenant-scoped API-key metadata."""

import hashlib


def tenant_fingerprint(tenant_id: str) -> str:
    return hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:16]


def tenant_api_key_configmap_name(tenant_id: str) -> str:
    return f"tenant-api-keys-{tenant_fingerprint(tenant_id)}"
