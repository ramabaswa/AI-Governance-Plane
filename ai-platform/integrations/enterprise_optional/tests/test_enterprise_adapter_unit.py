from integrations.enterprise_optional.adapter import EnterpriseOptionalAdapter


def test_adapter_defaults_to_oss_capability(monkeypatch):
    monkeypatch.delenv("SOLO_ENTERPRISE_ENABLED", raising=False)

    catalog = EnterpriseOptionalAdapter.get_extended_pricing_catalog()

    assert catalog == {
        "enterprise_active": False,
        "tier": "standard_oss",
        "sla": "best_effort",
    }


def test_adapter_reports_explicit_enterprise_flag(monkeypatch):
    monkeypatch.setenv("SOLO_ENTERPRISE_ENABLED", "true")

    assert EnterpriseOptionalAdapter.is_enterprise_enabled() is True
