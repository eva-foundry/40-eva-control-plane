# EVA-FEATURE: F40-01
# EVA-STORY: F40-01-001
# EVA-STORY: F40-03-001
# EVA-STORY: F40-03-002
# EVA-STORY: F40-ARTIFACT_ID-001
# EVA-STORY: F40-EVIDENCE_ID-001
# EVA-STORY: F40-HEALTH-001
# EVA-STORY: F40-RUN_ID-001
# EVA-STORY: F40-RUN_ID-002
"""
40-eva-control-plane — Runtime API
FastAPI application serving runs, step_runs, artifacts and evidence views.
Port: 8020

Store selection:
  COSMOS_URL + COSMOS_KEY set  →  CosmosStore (runs container, partition=/evidence_id)
  otherwise                    →  MemoryStore (local dev)

This API is complementary to 37-data-model Model API (port 8010):
  - Port 8010  →  catalog/config objects (planes, agents, runbooks, workflows, ...)
  - Port 8020  →  runtime/operational records (runs, step_runs, artifacts, evidence)
"""
from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

log = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent.parent / "model"

# ── In-memory store (replaced by Cosmos in production) ────────────────────────

_store: dict[str, dict] = {"runs": {}, "step_runs": {}, "artifacts": {}}


def _seed_from_disk():
    """Load model seed files into in-memory store at startup."""
    count = 0
    for layer, filename in [("runs", "runs.json"), ("step_runs", "step_runs.json"), ("artifacts", "artifacts.json")]:
        path = MODEL_DIR / filename
        if not path.exists():
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        objects = raw.get(layer, [])
        for obj in objects:
            obj_id = obj.get("id", "")
            if obj_id:
                _store[layer][obj_id] = obj
                count += 1
    log.info("Seeded %d runtime objects from disk JSON", count)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed_from_disk()
    yield


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="EVA Control Plane — Runtime API",
        version="0.1.0",
        description=(
            "Operational runtime records for the EVA Automation Control Plane.  \n\n"
            "**Port 8020** — runtime (runs, step_runs, artifacts, evidence packs)  \n"
            "**Port 8010** — catalog (planes, agents, runbooks, workflows)  \n\n"
            "Evidence ID format: `GH<run>-PR<pr>-<sha>`"
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from api.routers.runs import router as runs_router
    from api.routers.artifacts import router as artifacts_router
    from api.routers.evidence import router as evidence_router

    for r in [runs_router, artifacts_router, evidence_router]:
        app.include_router(r)

    @app.get("/health", tags=["health"], summary="Liveness check")
    async def health() -> dict:
        return {
            "status": "ok",
            "service": "control-plane-runtime-api",
            "version": "0.1.0",
            "store": "memory",
            "runs": len(_store["runs"]),
            "step_runs": len(_store["step_runs"]),
            "artifacts": len(_store["artifacts"]),
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8020, reload=True)
