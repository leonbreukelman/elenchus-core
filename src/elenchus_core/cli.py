from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from .evaluator import evaluate_request
from .models import EvaluationRequest, TypedAction


def _load_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("cases"), list):
        return [item for item in data["cases"] if isinstance(item, dict)]
    raise ValueError("input must be a JSON array or object with a cases array")


def _case_request(case: dict[str, Any]) -> EvaluationRequest:
    proposed = case.get("proposedAction", case.get("proposed_action"))
    if not isinstance(proposed, dict):
        proposed = {"type": "invalid"}
    return EvaluationRequest(
        traceId=str(case.get("id") or case.get("traceId") or "case"),
        domain="sre" if case.get("domain") == "sre" else "generic",
        context=str(case.get("context") or ""),
        proposedAction=TypedAction.model_validate(proposed),
        rationale=str(case.get("rationale") or ""),
        metadata={"source": case.get("source"), "split": case.get("split")},
    )


def run(cases_path: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for case in _load_cases(cases_path):
        request = _case_request(case)
        report = evaluate_request(request)
        row = {
            "id": request.traceId,
            "status": report.status,
            "calibration": report.calibration,
            "action_type": request.proposedAction.type,
            "human_label": case.get("human_label", case.get("humanLabel", case.get("label", ""))),
            "human_score": case.get("human_score", case.get("humanScore", "")),
            "recommendation": report.recommendation,
            "overall_signal": report.overallSignal,
            "specificity_margin": report.support.specificityMargin if report.support else None,
            "rationale_specificity": report.subscores.rationaleSpecificity if report.subscores else None,
            "context_grounding": report.subscores.contextGrounding if report.subscores else None,
            "load_bearing_absent": report.grounding.summary.absent if report.grounding else None,
            "load_bearing_contradicted": report.grounding.summary.contradicted if report.grounding else None,
            "split": case.get("split", ""),
            "source": case.get("source", ""),
        }
        rows.append(row)
    result = {"case_count": len(rows), "calibration": "uncalibrated_internal_alpha", "rows": rows}
    (output_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    if rows:
        with (output_dir / "comparison.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    else:
        (output_dir / "comparison.csv").write_text("", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Elenchus Core signal validation over labeled cases.")
    parser.add_argument("cases", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args(argv)
    result = run(args.cases, args.output_dir)
    for row in result["rows"]:
        print(
            f"{row['id']}	label={row['human_label']}	recommendation={row['recommendation']}	"
            f"overall={row['overall_signal']}	grounding={row['context_grounding']}"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
