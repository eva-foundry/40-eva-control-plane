# 40-eva-control-plane

**EVA Automation Control Plane** — the runtime layer that operates on top of [37-data-model](../37-data-model/README.md).

---

## What is this?

`37-data-model` is the **catalog** — it describes WHAT exists: services, endpoints, containers, agents, runbooks, workflows.

`40-eva-control-plane` is the **runtime** — it records WHAT HAPPENED: runs, step executions, evidence packs, and the `evidence_id` that ties a PR → deployment → telemetry snapshot together.

```
37-data-model (catalog, slow change)        40-eva-control-plane (runtime, high write)
  planes / connections / environments    →     runs / step_runs / artifacts
  cp_agents / cp_skills / runbooks       →     evidence packs (rb-001 → evidence-pack.json)
  cp_workflows / cp_policies             →     .github/workflows/*.yml (compiled)
```

---

## Two-plane evidence spine

```
evidence_id format:  GH<run_number>-PR<pr_number>-<short_sha>
                     e.g.  GH1234-PR56-abc1234

Propagated across:
  PR check run    →  evidence_id in check title
  Azure deploy    →  evidence_id as deployment tag
  ADO work item   →  evidence_id linked as artifact
  Cosmos run      →  evidence_id as partition key
```

---

## Project layout

```
40-eva-control-plane/
├── .github/
│   └── workflows/
│       ├── rb-001-pr-ci-evidence.yml   ← RB-001: PR → Build/Test → Evidence Pack (ACTIVE)
│       └── rb-002-promote-dev.yml      ← RB-002: Promote to DEV (stub)
├── model/
│   ├── runs.json          ← operational run seed / schema reference
│   ├── step_runs.json     ← step execution seed
│   └── artifacts.json     ← evidence artifact index seed
├── api/
│   ├── server.py          ← FastAPI runtime API (port 8020)
│   ├── config.py          ← pydantic-settings
│   ├── models/
│   │   └── run.py         ← Run, StepRun, Artifact pydantic models
│   └── routers/
│       ├── runs.py        ← /runs/* CRUD
│       ├── artifacts.py   ← /artifacts/* CRUD
│       └── evidence.py    ← GET /evidence/{evidence_id} (cross-run view)
├── scripts/
│   ├── pack-evidence.py   ← evidence pack assembler (called from GitHub Actions)
│   ├── assemble-model.ps1
│   └── validate-model.ps1
├── requirements.txt
├── ado-artifacts.json     ← ADO Epic/Features/PBIs manifest (Epic id=142)
├── ado-import.ps1         ← ADO onboarding hook
└── README.md
```

---

## Runbooks implemented

| ID | Name | Plane | Status | GitHub Actions |
|---|---|---|---|---|
| RB-001 | PR → Build/Test → Evidence Pack | GitHub | **ACTIVE** | `.github/workflows/rb-001-pr-ci-evidence.yml` |
| RB-002 | Promote to DEV | Azure | stub | `.github/workflows/rb-002-promote-dev.yml` |
| RB-003 | Alert → Triage → ADO Bug | Azure | catalog-only | — |
| RB-004 | Weekly Scrum Status | ADO | catalog-only | — |

---

## Runtime API (port 8020)

| Route | Method | Description |
|---|---|---|
| `GET /runs` | GET | List all runs (filter by `evidence_id`, `status`, `app_id`) |
| `GET /runs/{run_id}` | GET | Run detail with all step_runs |
| `POST /runs` | POST | Create new run (returns `run_id` + `evidence_id`) |
| `PATCH /runs/{run_id}` | PATCH | Update run status |
| `GET /artifacts` | GET | List evidence artifacts |
| `POST /artifacts` | POST | Register new artifact (with `sha256`, `uri`) |
| `GET /evidence/{evidence_id}` | GET | Full evidence view: run + steps + artifacts |
| `GET /health` | GET | Liveness check |

---

## Quick start

```powershell
# 1. Install dependencies
cd 40-eva-control-plane
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt

# 2. Start the runtime API
.\.venv\Scripts\python -m uvicorn api.server:app --port 8020 --reload

# 3. Open docs
# http://localhost:8020/docs
```

---

## Relationship with 37-data-model

The catalog layers added in Track A are **readable** via the 37-data-model API (port 8010):

```bash
# Get all runbooks from catalog
GET http://localhost:8010/model/runbooks

# Get RB-001 detail
GET http://localhost:8010/model/runbooks/rb-001

# Get all control-plane agents
GET http://localhost:8010/model/cp_agents
```

The runtime API (port 8020) creates and tracks execution records. They are NOT in the catalog.

---

## Evidence pack schema

```json
{
  "evidence_id": "GH1234-PR56-abc1234",
  "schema_version": "1.0",
  "generated_at": "2026-02-21T15:00:00Z",
  "runbook_id": "rb-001",
  "app_id": "app-eva-da-rebuild",
  "pr_number": 56,
  "commit_sha": "abc1234",
  "summary": {
    "passed": 142,
    "failed": 0,
    "coverage": 87.3
  },
  "artifacts": [
    { "name": "test-results.json", "sha256": "...", "uri": "..." },
    { "name": "coverage-report.json", "sha256": "...", "uri": "..." }
  ]
}
```

---

## Guardrails enforced

1. **No direct push to main** — branch protection, all changes via PR
2. **Evidence pack required** — PR merge blocked until `evidence-pack` check passes
3. **Human approval gates** — STG and PROD environments require reviewer approval
4. **Least-privilege identities** — GitHub App / Managed Identity / OIDC, no long-lived secrets
5. **Immutable evidence** — artifacts uploaded with SHA-256 hash, retention 90 days (365 PROD)
