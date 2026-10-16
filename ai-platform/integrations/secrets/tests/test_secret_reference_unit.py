from integrations.secrets.vault import SecretReferenceManager


def test_secret_reference_format_and_resolution_never_return_plaintext():
    reference = SecretReferenceManager.format_k8s_secret_ref("Provider Secret")

    assert reference == "provider-secret/api-key"
    assert SecretReferenceManager.resolve_secret_for_gateway(reference) == "provider-secret"
    assert "api-key-value" not in reference


def test_log_sanitizer_masks_bearer_tokens_and_provider_keys():
    sanitized = SecretReferenceManager.sanitize_for_logs(
        "Authorization: Bearer eyJhbGciOiJsecret token sk-abcd12345678"
    )

    assert "eyJhbGciOiJsecret" not in sanitized
    assert "sk-abcd12345678" not in sanitized
    assert "[REDACTED_TOKEN]" in sanitized
    assert "[REDACTED]" in sanitized
