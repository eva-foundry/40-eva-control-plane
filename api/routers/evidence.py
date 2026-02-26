# EVA-FEATURE: F40-02
# EVA-STORY: F40-02-001
"""
Evidence router — cross-run evidence view by evidence_id.

GET /evidence/{evidence_id}  returns the full picture:
  - the run record
  - all step_runs
  - all artifacts
  - links back to catalog objects (runbook, agents) via 37-data-model URL
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/{evidence_id}", summary="Full evidence view by evidence_id")
async def get_evidence(evidence_id: str) -> dict:
    from api.server import _store as s

    # Find runs for this evidence_id
    runs = [r for r in s["runs"].values() if r.get("evidence_id") == evidence_id]
    if not runs:
        raise HTTPException(status_code=404, detail=f"No runs found for evidence_id '{evidence_id}'")

    run = runs[0]
    step_runs = [sr for sr in s["step_runs"].values() if sr.get("evidence_id") == evidence_id]
    artifacts = [a for a in s["artifacts"].values() if a.get("evidence_id") == evidence_id]

    return {
        "evidence_id": evidence_id,
        "run": run,
        "step_runs": sorted(step_runs, key=lambda x: x.get("started_at", "")),
        "artifacts": sorted(artifacts, key=lambda x: x.get("uploaded_at", "")),
        "artifact_count": len(artifacts),
        "step_count": len(step_runs),
        "catalog_links": {
            "runbook": f"http://localhost:8010/model/runbooks/{run.get('runbook_id', '')}",
            "cp_agents": "http://localhost:8010/model/cp_agents",
            "cp_workflows": "http://localhost:8010/model/cp_workflows",
        },
    }
