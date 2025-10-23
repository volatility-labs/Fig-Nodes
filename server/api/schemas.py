"""Pydantic schemas for HTTP API request/response validation."""

from pydantic import BaseModel, Field
from typing import Dict, Any, Literal


class SetAPIKeyRequest(BaseModel):
    """Request model for setting an API key."""
    key_name: str = Field(..., min_length=1, description="Name of the API key")
    value: str = Field(default="", description="Value of the API key")


class DeleteAPIKeyRequest(BaseModel):
    """Request model for deleting an API key."""
    key_name: str = Field(..., min_length=1, description="Name of the API key to delete")


class SetAPIKeyResponse(BaseModel):
    """Response model for setting an API key."""
    status: Literal["success"] = "success"


class DeleteAPIKeyResponse(BaseModel):
    """Response model for deleting an API key."""
    status: Literal["success"] = "success"


class APIKeysResponse(BaseModel):
    """Response model for getting all API keys."""
    keys: Dict[str, str] = Field(..., description="Map of API key names to values")


class NodesResponse(BaseModel):
    """Response model for listing all node metadata."""
    nodes: Dict[str, Dict[str, Any]] = Field(..., description="Node metadata")


class APIError(BaseModel):
    """Standard API error response."""
    error: str = Field(..., description="Error message")
    code: str | None = Field(None, description="Error code")
    details: Dict[str, Any] | None = Field(None, description="Additional error details")

