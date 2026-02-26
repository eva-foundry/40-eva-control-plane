"""
Runs router — CRUD for run records.

Runs represent a single execution of a runbook (e.g., one PR triggering RB-001).
The evidence_id is the cross-plane correlation key.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

router = APIRouter(prefix="/runs", tags=["runs"])


def _store():
    from api.server import _store as s
    return s["runs"]


@router.get("", summary="List runs")
async def list_runs(
    evidence_id: str | None = Query(None),
    status: str | None = Query(None),
    app_id: str | None = Query(None),
    limit: int = Query(100, le=500),
) -> list[dict]:
    items = list(_store().values())
    if evidence_id:
        items = [x for x in items if x.get("evidence_id") == evidence_id]
    if status:
        items = [x for x in items if x.get("status") == status]
    if app_id:
        items = [x for x in items if x.get("app_id") == app_id]
    return items[:limit]


@router.get("/{run_id}", summary="Get run by ID")
async def get_run(run_id: str) -> dict:
    run = _store().get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    # Attach step_runs inline
    from api.server import _store as s
    run = dict(run)
    run["step_runs"] = [sr for sr in s["step_runs"].values() if sr.get("run_id") == run_id]
    return run


@router.post("", status_code=201, summary="Create run")
async def create_run(body: dict = Body(...)) -> dict:
    run_id = body.get("id") or f"run-{uuid.uuid4().hex[:8]}"
    if run_id in _store():
        raise HTTPException(status_code=409, detail=f"Run '{run_id}' already exists")
    now = datetime.now(timezone.utc).isoformat()
    run = {
        "id": run_id,
        "evidence_id": body.get("evidence_id", ""),
        "runbook_id": body.get("runbook_id", ""),
        "app_id": body.get("app_id", ""),
        "env_id": body.get("env_id", ""),
        "status": body.get("status", "running"),
        "initiated_by": body.get("initiated_by", "api"),
        "started_at": body.get("started_at", now),
        "completed_at": body.get("completed_at"),
        "duration_seconds": body.get("duration_seconds"),
        "pr_number": body.get("pr_number"),
        "commit_sha": body.get("commit_sha"),
        "ado_work_item_id": body.get("ado_work_item_id"),
        "evidence_pack_uri": body.get("evidence_pack_uri"),
        "notes": body.get("notes", ""),
    }
    _store()[run_id] = run
    return run


@router.patch("/{run_id}", summary="Update run status / fields")
async def update_run(run_id: str, body: dict = Body(...)) -> dict:
    run = _store().get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    run = dict(run)
    for k, v in body.items():
        if k != "id":
            run[k] = v
    _store()[run_id] = run
    return run
