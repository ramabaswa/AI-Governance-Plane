"""Authentication and token issuance endpoints."""

from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Header
from integrations.identity.provider import IdentityProvider
from shared.authorization.dependencies import get_current_user, AuthenticatedUser

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_id: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    tenant_id: str
    roles: list[str]


@router.post("/token", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Authenticate user and generate tenant-scoped JWT token."""
    token = IdentityProvider.authenticate_development_user(
        username=req.username,
        password=req.password,
        tenant_id=req.tenant_id,
    )
    from shared.authorization.jwt_handler import decode_access_token
    claims = decode_access_token(token)
    return TokenResponse(
        access_token=token,
        tenant_id=claims["tenant_id"],
        roles=claims["roles"],
    )


@router.get("/me")
async def get_me(current_user: AuthenticatedUser = Depends(get_current_user)):
    """Return authenticated caller identity and permissions."""
    return {
        "success": True,
        "data": {
            "subject": current_user.subject,
            "tenant_id": current_user.tenant_id,
            "roles": [r.value for r in current_user.roles],
        },
    }
