# How to Add a Feature (10-Step Workflow)

**Date**: 2026-10-15  
**Platform**: AI Governance Plane  

---

Every new platform feature must strictly follow this 10-step engineering workflow:

1. **Step 1: Confirm Reference & Behavioral Intent**  
   Identify upstream agentgateway PR, lab example, or capability spec. Document in `docs/references/feature-source-matrix.md`.
2. **Step 2: Define Contracts & Authorization Rules**  
   Create Pydantic schemas in `shared/contracts/<feature>.py`. Define necessary permissions in `shared/authorization/roles.py`.
3. **Step 3: Implement Domain Logic & State Store Integration**  
   Add feature service methods to `features/<feature>/` or `features/state_store.py`. Ensure tenant isolation is strictly enforced.
4. **Step 4: Write Backend Unit & Invariant Tests**  
   Add tests in `tests/test_<feature>.py`. Ensure tests verify unauthorized access rejection, cross-tenant 404s, and audit logging.
5. **Step 5: Implement API Router**  
   Add FastAPI router in `apps/control_api/routers/<feature>_router.py`. Mount router in `apps/control_api/main.py`.
6. **Step 6: Update Management Console UI**  
   Add screen view in `apps/console/index.html` and corresponding controller methods in `console.js`.
7. **Step 7: Add Component & Interaction Tests**  
   Verify form validation, loading states, empty states, and error handling.
8. **Step 8: Reconciler Integration**  
   If the feature mutates agentgateway configuration, update `integrations/agentgateway/translator.py` and `reconciler.py`.
9. **Step 9: Update Documentation**  
   Update User Guide, Screen Specifications, and Threat Model.
10. **Step 10: Run Full Test Suite & Document Evidence**  
    Run `pytest tests/ -v` and record passing evidence in `docs/features/test-traceability.md`.
