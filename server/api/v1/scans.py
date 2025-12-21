"""API endpoints for cloud scan storage (graph configurations/workflows)."""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/scans", tags=["scans"])

# Storage directory for scan configurations (can be replaced with cloud storage later)
SCANS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "scans"
SCANS_DIR.mkdir(exist_ok=True)

# Metadata file to track scans
METADATA_FILE = SCANS_DIR / ".scans_metadata.json"


class ScanMetadata(BaseModel):
    """Metadata for a saved scan (graph configuration)."""
    id: str
    name: str
    description: str | None = None
    graph_data: dict[str, Any]  # The actual graph configuration
    created_at: str
    updated_at: str
    last_executed: str | None = None


class ScanListResponse(BaseModel):
    """Response model for listing scans."""
    scans: list[ScanMetadata]


class ScanCreateRequest(BaseModel):
    """Request model for creating a scan (saving graph configuration)."""
    name: str
    description: str | None = None
    graph_data: dict[str, Any]  # The graph configuration to save


def _load_metadata() -> dict[str, ScanMetadata]:
    """Load scan metadata from file."""
    if not METADATA_FILE.exists():
        return {}
    
    try:
        with open(METADATA_FILE, 'r') as f:
            data = json.load(f)
            return {k: ScanMetadata(**v) for k, v in data.items()}
    except Exception:
        return {}


def _save_metadata(metadata: dict[str, ScanMetadata]) -> None:
    """Save scan metadata to file."""
    with open(METADATA_FILE, 'w') as f:
        json.dump(
            {k: v.model_dump() for k, v in metadata.items()},
            f,
            indent=2
        )


def _save_graph_file(scan_id: str, graph_data: dict[str, Any]) -> Path:
    """Save graph configuration to a file."""
    filepath = SCANS_DIR / f"{scan_id}.json"
    with open(filepath, 'w') as f:
        json.dump(graph_data, f, indent=2)
    return filepath


def _load_graph_file(scan_id: str) -> dict[str, Any]:
    """Load graph configuration from a file."""
    filepath = SCANS_DIR / f"{scan_id}.json"
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Scan file not found")
    with open(filepath, 'r') as f:
        return json.load(f)


@router.get("", response_model=ScanListResponse, summary="List all scans")
def list_scans() -> ScanListResponse:
    """List all saved scans for the current user.
    
    In a multi-user cloud environment, this would filter by user_id.
    For now, returns all scans.
    """
    metadata = _load_metadata()
    scans = list(metadata.values())
    # Sort by updated_at descending
    scans.sort(key=lambda s: s.updated_at, reverse=True)
    return ScanListResponse(scans=scans)


@router.post("", response_model=ScanMetadata, summary="Save a scan (graph configuration)")
async def create_scan(request: ScanCreateRequest) -> ScanMetadata:
    """Save a graph configuration/workflow to cloud storage.
    
    This saves the graph setup (nodes, connections, parameters) so it can be
    loaded and executed later. This replaces saving to local files.
    """
    scan_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()
    
    try:
        # Save graph configuration to file
        _save_graph_file(scan_id, request.graph_data)
        
        # Create metadata
        scan_metadata = ScanMetadata(
            id=scan_id,
            name=request.name,
            description=request.description,
            graph_data=request.graph_data,
            created_at=timestamp,
            updated_at=timestamp,
            last_executed=None
        )
        
        # Save metadata
        metadata = _load_metadata()
        metadata[scan_id] = scan_metadata
        _save_metadata(metadata)
        
        return scan_metadata
    
    except Exception as e:
        # Clean up file if metadata save fails
        filepath = SCANS_DIR / f"{scan_id}.json"
        if filepath.exists():
            filepath.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to save scan: {str(e)}")


@router.get("/{scan_id}", response_model=ScanMetadata, summary="Get scan (graph configuration)")
def get_scan(scan_id: str) -> ScanMetadata:
    """Get a saved scan (graph configuration) by ID.
    
    Returns the full graph configuration that can be loaded into the editor.
    """
    metadata = _load_metadata()
    if scan_id not in metadata:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # Reload graph data from file to ensure it's up to date
    try:
        graph_data = _load_graph_file(scan_id)
        scan = metadata[scan_id]
        scan.graph_data = graph_data
    except HTTPException:
        # If file doesn't exist, return metadata without graph_data
        pass
    
    return metadata[scan_id]


@router.put("/{scan_id}", response_model=ScanMetadata, summary="Update scan")
async def update_scan(scan_id: str, request: ScanCreateRequest) -> ScanMetadata:
    """Update an existing scan (graph configuration)."""
    metadata = _load_metadata()
    if scan_id not in metadata:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    timestamp = datetime.utcnow().isoformat()
    
    try:
        # Save updated graph configuration
        _save_graph_file(scan_id, request.graph_data)
        
        # Update metadata
        scan = metadata[scan_id]
        scan.name = request.name
        scan.description = request.description
        scan.graph_data = request.graph_data
        scan.updated_at = timestamp
        
        _save_metadata(metadata)
        
        return scan
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update scan: {str(e)}")


@router.post("/{scan_id}/execute", summary="Mark scan as executed")
def mark_executed(scan_id: str) -> dict[str, str]:
    """Mark a scan as recently executed (updates last_executed timestamp)."""
    metadata = _load_metadata()
    if scan_id not in metadata:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    scan = metadata[scan_id]
    scan.last_executed = datetime.utcnow().isoformat()
    _save_metadata(metadata)
    
    return {"status": "success", "message": f"Scan '{scan.name}' marked as executed"}


@router.delete("/{scan_id}", summary="Delete scan")
def delete_scan(scan_id: str) -> dict[str, str]:
    """Delete a scan (graph configuration) and its file."""
    metadata = _load_metadata()
    if scan_id not in metadata:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    scan = metadata[scan_id]
    filepath = SCANS_DIR / f"{scan_id}.json"
    
    # Delete file
    if filepath.exists():
        filepath.unlink()
    
    # Remove metadata
    del metadata[scan_id]
    _save_metadata(metadata)
    
    return {"status": "success", "message": f"Scan '{scan.name}' deleted"}

