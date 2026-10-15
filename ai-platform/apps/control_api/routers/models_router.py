"""Tenant-scoped approved model catalog endpoints."""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from features.database import get_db_session
from features.llm_governance import service
from shared.authorization.dependencies import (
    AuthenticatedUser,
    get_current_user,
    require_permission,
    require_tenant_context,
)
from shared.contracts.model import ModelBackend, ModelBackendCreate

router = APIRouter(prefix="/api/v1/models", tags=["Model Catalog"])


@router.get("", response_model=List[ModelBackend])
async def list_models(
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """List only model backends approved for the caller's tenant."""
    return service.list_models(session, tenant_id)


@router.post("", status_code=201, response_model=ModelBackend)
async def register_model(
    req: ModelBackendCreate,
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(require_permission("model:create")),
    session: Session = Depends(get_db_session),
):
    """Register an approved model backend without accepting provider credentials."""
    return service.create_model(
        session,
        tenant_id=tenant_id,
        actor=current_user.subject,
        request=req,
    )
