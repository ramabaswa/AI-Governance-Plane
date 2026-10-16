from features.audit_evidence.service import append_event, verify_chain
from features.persistence import AuditEventRecord
from tests.feature_test_support import feature_database
from shared.contracts.audit import AuditAction


def test_audit_chain_validates_then_detects_event_tampering():
    with feature_database() as session:
        append_event(
            session,
            tenant_id="tenant-acme",
            actor="unit-test",
            action=AuditAction.APPLICATION_CREATED,
            resource_type="application",
            resource_id="app-test",
            details={"name": "test"},
        )
        session.flush()
        assert verify_chain(session, tenant_id="tenant-acme") is True
        row = session.query(AuditEventRecord).filter_by(tenant_id="tenant-acme").one()
        row.details = {"name": "tampered"}
        assert verify_chain(session, tenant_id="tenant-acme") is False
