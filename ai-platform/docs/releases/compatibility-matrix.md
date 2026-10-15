# Upstream Compatibility Matrix

**Date**: 2026-10-15  
**Platform**: AI Governance Plane  
**Author**: Principal Architect  

---

| Platform Component | Pinned Version | Supported Upstream Range | Gateway API Version | Verification Status |
|---|---|---|---|:---:|
| **agentgateway Binary** | `v0.8.2` | `v0.8.0` – `v0.8.4` | `gateway.networking.k8s.io/v1` | Verified |
| **AgentgatewayBackend CRD** | `v1alpha1` | `v1alpha1` | `agentgateway.dev/v1alpha1` | Verified |
| **AgentgatewayPolicy CRD** | `v1alpha1` | `v1alpha1` | `agentgateway.dev/v1alpha1` | Verified |
| **Python Runtime** | `3.12+` / `3.14` | `>= 3.12.0` | N/A | Verified |
| **FastAPI Framework** | `0.115.0` | `>= 0.115.0, < 1.0.0` | N/A | Verified |
| **Model Context Protocol (MCP)**| JSON-RPC 2.0 | `2024-11-05` Spec | N/A | Verified |
| **Kubernetes Cluster** | `v1.28+` | `v1.28` – `v1.31` | Gateway API Standard Channel | Verified |
