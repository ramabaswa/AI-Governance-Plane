from features.application_agent_registry.naming import (
    tenant_api_key_configmap_name,
    tenant_fingerprint,
)


def test_tenant_key_catalog_names_are_stable_and_tenant_scoped():
    acme_fingerprint = tenant_fingerprint("tenant-acme")
    assert acme_fingerprint == tenant_fingerprint("tenant-acme")
    assert len(acme_fingerprint) == 16
    assert tenant_api_key_configmap_name("tenant-acme") == f"tenant-api-keys-{acme_fingerprint}"
    assert tenant_api_key_configmap_name("tenant-acme") != tenant_api_key_configmap_name("tenant-globex")
