# Migration & Upgrade Guide

**Date**: 2026-10-15  
**Platform**: AI Governance Plane  
**Target Release**: v0.1.0 (Initial Foundation Release)  

---

## 1. Upgrading from Legacy Scaffolding to v0.1.0

The v0.1.0 release consolidates the previous empty scaffold into a unified, tenant-isolated architecture.

### Schema Migration
1. Ensure the PostgreSQL / SQLite database volume is mounted.
2. Initialize tenant and role tables:
   ```bash
   python -m scripts.init_db
   ```
3. Existing virtual keys generated in development must be re-provisioned via the Onboarding Wizard to generate valid SHA-256 hashes.

### Kubernetes Manifests Upgrade
Update CRD custom resource definitions in your cluster:
```bash
kubectl apply -f ai-platform/deploy/kubernetes/namespace.yaml
kubectl apply -f ai-platform/deploy/kubernetes/control-api-deployment.yaml
```
