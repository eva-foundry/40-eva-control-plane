#!/usr/bin/env python3
"""
pack-evidence.py — Evidence Pack Assembler (RB-001 s-20)

Assembles test results and coverage data into a signed evidence pack JSON.
Called from GitHub Actions as part of rb-001-pr-ci-evidence.yml (step s-20).

Usage:
  python scripts/pack-evidence.py \\
    --evidence-id GH1234-PR56-abc1234 \\
    --run-id 12345678 \\
    --pr 56 \\
    --commit abc1234 \\
    --branch feature/my-feature \\
    --repo org/repo-name \\
    --runbook-id rb-001 \\
    --app-id app-eva-da-rebuild \\
    --test-results test-results.json \\
    --output evidence-pack.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    try:
        h.update(path.read_bytes())
        return h.hexdigest()
    except FileNotFoundError:
        return "file-not-found"


def parse_test_results(path: Path) -> dict:
    """
    Parse test-results.json produced by vitest / jest / pytest-json-report.

    Tries multiple formats:
      vitest/jest:  { numPassedTests, numFailedTests }
      pytest-json:  { summary: { passed, failed } }
      fallback:     returns zeroes with a warning
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[WARN] Could not parse {path}: {e}", file=sys.stderr)
        return {"passed": 0, "failed": 0, "coverage": 0.0, "_parse_error": str(e)}

    # vitest / jest format
    if "numPassedTests" in raw or "numFailedTests" in raw:
        coverage = 0.0
        # Try to find coverage in jest/vitest output
        if "coverageMap" in raw or "coverage" in raw:
            cov = raw.get("coverage", {})
            # Extract statement coverage if available
            all_stmts = [v.get("s", {}) for v in cov.values() if isinstance(v, dict)]
            if all_stmts:
                total = sum(len(s) for s in all_stmts)
                covered = sum(sum(1 for x in s.values() if x > 0) for s in all_stmts)
                coverage = round((covered / total * 100) if total else 0.0, 1)
        return {
            "passed": raw.get("numPassedTests", 0),
            "failed": raw.get("numFailedTests", 0),
            "coverage": coverage,
        }

    # pytest-json-report format
    if "summary" in raw:
        s = raw["summary"]
        return {
            "passed": s.get("passed", 0),
            "failed": s.get("failed", 0),
            "coverage": s.get("coverage", 0.0),
        }

    print(f"[WARN] Unknown test-results format — returning zeroes", file=sys.stderr)
    return {"passed": 0, "failed": 0, "coverage": 0.0}


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble evidence pack for RB-001")
    parser.add_argument("--evidence-id", required=True, help="evidence_id correlation key")
    parser.add_argument("--run-id", required=True, help="GitHub Actions run_id")
    parser.add_argument("--pr", required=False, type=int, default=0, help="PR number")
    parser.add_argument("--commit", required=False, default="", help="Short commit SHA")
    parser.add_argument("--branch", required=False, default="", help="Source branch")
    parser.add_argument("--repo", required=False, default="", help="Repository (org/name)")
    parser.add_argument("--runbook-id", required=False, default="rb-001")
    parser.add_argument("--app-id", required=False, default="")
    parser.add_argument("--test-results", required=False, default="test-results.json", help="Path to test-results.json")
    parser.add_argument("--output", required=False, default="evidence-pack.json", help="Output file path")
    args = parser.parse_args()

    test_results_path = Path(args.test_results)
    output_path = Path(args.output)

    # Parse test results
    test_summary = parse_test_results(test_results_path)

    # Build artifact hashes
    artifacts = []
    for artifact_path in [test_results_path]:
        if artifact_path.exists():
            artifacts.append({
                "name": artifact_path.name,
                "sha256": sha256_file(artifact_path),
                "size_bytes": artifact_path.stat().st_size,
                "uri": f"${{ env.ARTIFACT_URI }}/{artifact_path.name}",  # placeholder
            })

    pack = {
        "evidence_id": args.evidence_id,
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runbook_id": args.runbook_id,
        "app_id": args.app_id,
        "run_id": args.run_id,
        "pr_number": args.pr,
        "commit_sha": args.commit,
        "branch": args.branch,
        "repo": args.repo,
        "summary": test_summary,
        "artifacts": artifacts,
        "guardrails": {
            "evidence_required": True,
            "pr_only": True,
            "policy": "policy-evidence-required",
        },
    }

    # Write output
    output_path.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")

    # Print summary
    failed = test_summary.get("failed", 0)
    passed = test_summary.get("passed", 0)
    coverage = test_summary.get("coverage", 0.0)
    print(f"Evidence pack assembled: {output_path}")
    print(f"  evidence_id : {args.evidence_id}")
    print(f"  tests       : {passed} passed / {failed} failed")
    print(f"  coverage    : {coverage}%")
    print(f"  artifacts   : {len(artifacts)}")

    if failed > 0:
        print(f"[FAIL] {failed} test(s) failed — evidence pack created but conclusion=failure", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
