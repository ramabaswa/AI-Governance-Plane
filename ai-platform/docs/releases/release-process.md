# Release Process & Staging Promotion Guide

**Date**: 2026-10-15  
**Platform**: AI Governance Plane  
**Author**: Release Engineering Lead  

---

## 1. Release Strategy & Versioning

The AI Governance Plane follows Semantic Versioning 2.0.0 (`vMAJOR.MINOR.PATCH`):
- **MAJOR**: Breaking API changes, schema incompatibility, or major gateway migration.
- **MINOR**: New capability features (e.g., new guardrail engine, MCP federation).
- **PATCH**: Bug fixes, security remediations, performance enhancements.

---

## 2. Release Promotion Pipeline

```
[ Pull Request ]
       ↓ (Automated CI: Lint, Tests, Security Scan, Container Build)
[ Merge to Main ]
       ↓
[ Tag Release: v0.1.0 ] ──→ Triggers `.github/workflows/release.yml`
       ↓
[ Container Images Published to ghcr.io ]
       ↓
[ Deploy to Staging Environment ]
       ↓
[ Automated Smoke & Reconciler Tests ]
       ↓
[ Explicit Human Sign-Off (Platform Admin) ]
       ↓
[ Canary Rollout to Production ] ──→ [ Automated Health Probe Verification ]
```

---

## 3. Pre-Flight Checklist
- [x] All 13 core invariant tests pass.
- [x] Secret scanning reports 0 leaked keys.
- [x] agentgateway compatibility verified against pinned release `v0.8.2`.
- [x] Audit ledger hash chain verified.
- [x] OpenAPI documentation generated without inference proxy routes.
