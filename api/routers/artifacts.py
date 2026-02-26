"""
Artifacts router — register and list evidence artifacts.

An artifact is a file produced during a run step (test-results.json, evidence-pack.json, etc.)
linked to the run and evidence_id.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, HTTPException, Query

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


def _store():
    from api.server import _store as s
    return s["artifacts"]


@router.get("", summary="List artifacts")
async def list_artifacts(
    evidence_id: str | None = Query(None),
    run_id: str | None = Query(None),
    artifact_type: str | None = Query(None, alias="type"),
    limit: int = Query(100, le=500),
) -> list[dict]:
    items = list(_store().values())
    if evidence_id:
        items = [x for x in items if x.get("evidence_id") == evidence_id]
    if run_id:
        items = [x for x in items if x.get("run_id") == run_id]
    if artifact_type:
        items = [x for x in items if x.get("type") == artifact_type]
    return items[:limit]


@router.get("/{artifact_id}", summary="Get artifact by ID")
async def get_artifact(artifact_id: str) -> dict:
    artifact = _store().get(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Artifact '{artifact_id}' not found")
    return artifact


@router.post("", status_code=201, summary="Register artifact")
async def register_artifact(body: dict = Body(...)) -> dict:
    artifact_id = body.get("id") or f"artifact-{uuid.uuid4().hex[:8]}"
    if artifact_id in _store():
        raise HTTPException(status_code=409, detail=f"Artifact '{artifact_id}' already exists")
    now = datetime.now(timezone.utc).isoformat()
    artifact = {
        "id": artifact_id,
        "evidence_id": body.get("evidence_id", ""),
        "run_id": body.get("run_id", ""),
        "step_id": body.get("step_id", ""),
        "name": body.get("name", ""),
        "type": body.get("type", "artifact"),
        "sha256": body.get("sha256", ""),
        "uri": body.get("uri", ""),
        "size_bytes": body.get("size_bytes"),
        "retention_days": body.get("retention_days", 90),
        "uploaded_at": body.get("uploaded_at", now),
        "notes": body.get("notes", ""),
    }
    _store()[artifact_id] = artifact
    return artifact
