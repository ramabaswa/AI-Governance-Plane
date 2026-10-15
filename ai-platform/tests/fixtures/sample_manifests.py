"""Test fixtures and sample agentgateway manifests."""

SAMPLE_STANDALONE_YAML = """
version: v1alpha1
listeners:
  - name: ai-proxy
    port: 8080
    protocol: HTTP
    routes:
      - name: chat-completion
        matches:
          - path:
              prefix: /v1/chat/completions
        backend:
          ai:
            provider: anthropic
            model: claude-3-5-sonnet
            auth:
              secretRef: anthropic-secret
virtualKeys:
  - id: vk-01
    keyHash: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
    quota: 1000000
"""
