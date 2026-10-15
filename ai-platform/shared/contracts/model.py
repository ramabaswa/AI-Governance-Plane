"""Contracts for Approved Model Backends and Provider Catalog."""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    GEMINI = "gemini"
    VLLM = "vllm"


class ModelBackendCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9._-]{1,63}$")
    provider: ProviderType
    model_name: str = Field(..., min_length=1, max_length=128)
    secret_ref: str = Field(
        ...,
        max_length=256,
        pattern=r"^[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?/[A-Za-z0-9._-]+$",
        description="Kubernetes Secret key reference as 'secret-name/key' in the gateway namespace",
    )
    base_url: Optional[str] = Field(default=None, description="Optional custom endpoint URL without query params")
    cost_per_1k_input_tokens: float = Field(default=0.003, ge=0)
    cost_per_1k_output_tokens: float = Field(default=0.015, ge=0)
    is_active: bool = True


class ModelBackend(BaseModel):
    id: str
    tenant_id: str
    name: str
    provider: ProviderType
    model_name: str
    secret_ref: str
    base_url: Optional[str] = None
    cost_per_1k_input_tokens: float
    cost_per_1k_output_tokens: float
    is_active: bool
    created_at: int
    updated_at: int
