"""Transactional audit-chain persistence."""

import hashlib
import json
import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from features.persistence import AuditChainHeadRecord, AuditEventRecord
from shared.contracts.audit import AuditAction, AuditEvent


_GENESIS_HASH = "0" * 64


def append_event(
    session: Session,
    *,
    tenant_id: str,
    actor: str,
    action: AuditAction,
    resource_type: str,
    resource_id: str,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    safe_details = details or {}
    serialized_details = json.dumps(safe_details, sort_keys=True, separators=(",", ":"), default=str)
    payload_hash = hashlib.sha256(serialized_details.encode("utf-8")).hexdigest()
    head = session.scalar(
        select(AuditChainHeadRecord)
        .where(AuditChainHeadRecord.tenant_id == tenant_id)
        .with_for_update()
    )
    if head is None:
        try:
            with session.begin_nested():
                head = AuditChainHeadRecord(tenant_id=tenant_id, last_event_hash=_GENESIS_HASH)
                session.add(head)
                session.flush()
        except IntegrityError:
            head = session.scalar(
                select(AuditChainHeadRecord)
                .where(AuditChainHeadRecord.tenant_id == tenant_id)
                .with_for_update()
            )
            if head is None:
                raise

    timestamp = int(time.time())
    event_id = f"evt-{uuid.uuid4().hex}"
    event_hash = AuditEvent.calculate_event_hash(
        event_id=event_id,
        tenant_id=tenant_id,
        actor=actor,
        action=action.value,
        resource_id=resource_id,
        payload_hash=payload_hash,
        prev_hash=head.last_event_hash,
        timestamp=timestamp,
        resource_type=resource_type,
    )
    row = AuditEventRecord(
        id=event_id,
        tenant_id=tenant_id,
        actor=actor,
        action=action.value,
        resource_type=resource_type,
        resource_id=resource_id,
        payload_hash=payload_hash,
        details=safe_details,
        prev_event_hash=head.last_event_hash,
        event_hash=event_hash,
        timestamp=timestamp,
    )
    head.last_event_hash = event_hash
    session.add(row)
    return AuditEvent.model_validate(row, from_attributes=True)


def list_events(session: Session, *, tenant_id: str, actor: str, limit: int = 100) -> list[AuditEvent]:
    append_event(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.AUDIT_READ,
        resource_type="audit_log",
        resource_id="tenant",
        details={"limit": limit},
    )
    session.flush()
    rows = session.scalars(
        select(AuditEventRecord)
        .where(AuditEventRecord.tenant_id == tenant_id)
        .order_by(AuditEventRecord.timestamp.desc(), AuditEventRecord.id.desc())
        .limit(limit)
    ).all()
    return [AuditEvent.model_validate(row, from_attributes=True) for row in rows]


def verify_chain(session: Session, *, tenant_id: str) -> bool:
    rows = session.scalars(
        select(AuditEventRecord).where(AuditEventRecord.tenant_id == tenant_id)
    ).all()
    head = session.get(AuditChainHeadRecord, tenant_id)
    if not rows:
        return head is None or head.last_event_hash == _GENESIS_HASH

    by_previous_hash: dict[str, AuditEventRecord] = {}
    for row in rows:
        if row.prev_event_hash in by_previous_hash:
            return False
        by_previous_hash[row.prev_event_hash] = row

    previous_hash = _GENESIS_HASH
    visited = 0
    while previous_hash in by_previous_hash:
        row = by_previous_hash[previous_hash]
        serialized_details = json.dumps(row.details, sort_keys=True, separators=(",", ":"), default=str)
        payload_hash = hashlib.sha256(serialized_details.encode("utf-8")).hexdigest()
        expected_hash = AuditEvent.calculate_event_hash(
            event_id=row.id,
            tenant_id=row.tenant_id,
            actor=row.actor,
            action=row.action,
            resource_id=row.resource_id,
            payload_hash=payload_hash,
            prev_hash=row.prev_event_hash,
            timestamp=row.timestamp,
            resource_type=row.resource_type,
        )
        if payload_hash != row.payload_hash or expected_hash != row.event_hash:
            return False
        previous_hash = row.event_hash
        visited += 1

    return (
        visited == len(rows)
        and head is not None
        and head.last_event_hash == previous_hash
    )
