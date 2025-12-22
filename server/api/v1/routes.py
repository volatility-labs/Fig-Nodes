"""API v1 HTTP routes."""

from typing import Any

from fastapi import APIRouter

from core.api_key_vault import APIKeyVault
from core.node_registry import NODE_REGISTRY
from core.types_registry import NodeCategory, ParamMeta
from core.types_utils import parse_type

from ..schemas import (
    APIKeysResponse,
    DeleteAPIKeyRequest,
    DeleteAPIKeyResponse,
    NodesResponse,
    SetAPIKeyRequest,
    SetAPIKeyResponse,
)

# Import scan routes
from . import scans
# Import watchlist routes
from . import watchlist

router = APIRouter()

# Include scan routes
router.include_router(scans.router)
# Include watchlist routes
router.include_router(watchlist.router)


@router.get("/nodes", response_model=NodesResponse, summary="List Node Metadata")
def list_nodes() -> NodesResponse:
    """Get metadata for all registered nodes.

    Returns information about node inputs, outputs, parameters, categories,
    required API keys, and descriptions.
    """
    nodes_meta: dict[str, dict[str, Any]] = {}

    for name, cls in NODE_REGISTRY.items():
        inputs_meta = {k: parse_type(v) for k, v in cls.inputs.items()}
        outputs_meta = {k: parse_type(v) for k, v in cls.outputs.items()}
        params: list[ParamMeta] = getattr(cls, "params_meta", [])

        category = getattr(cls, "CATEGORY", str(NodeCategory.BASE))

        nodes_meta[name] = {
            "inputs": inputs_meta,
            "outputs": outputs_meta,
            "params": params,
            "category": category,
            "required_keys": getattr(cls, "required_keys", []),
            "description": (
                (cls.__doc__ or "").strip().splitlines()[0] if getattr(cls, "__doc__", None) else ""
            ),
        }

    return NodesResponse(nodes=nodes_meta)


@router.get("/api_keys", response_model=APIKeysResponse, summary="Get API Keys")
def get_api_keys() -> APIKeysResponse:
    """Get all stored API keys.

    Returns a map of API key names to their values.
    Note: This endpoint returns all keys for convenience, but in production
    you may want to mask sensitive values.
    """
    vault = APIKeyVault()
    return APIKeysResponse(keys=vault.get_all())


@router.post("/api_keys", response_model=SetAPIKeyResponse, summary="Set API Key")
async def set_api_key(request: SetAPIKeyRequest) -> SetAPIKeyResponse:
    """Store an API key in the vault.

    The key will be stored securely and made available to nodes that require it.
    Keys are persisted to the .env file.
    """
    vault = APIKeyVault()
    vault.set(request.key_name, request.value)
    return SetAPIKeyResponse()


@router.delete("/api_keys", response_model=DeleteAPIKeyResponse, summary="Delete API Key")
async def delete_api_key(request: DeleteAPIKeyRequest) -> DeleteAPIKeyResponse:
    """Remove an API key from the vault.

    The key will be deleted from the .env file and will no longer be available
    to nodes.
    """
    vault = APIKeyVault()
    vault.unset(request.key_name)
    return DeleteAPIKeyResponse()
