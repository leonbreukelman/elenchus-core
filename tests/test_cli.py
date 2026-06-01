import csv
import json
import subprocess
import sys
from pathlib import Path


def test_signal_validation_cli_writes_result_and_comparison(tmp_path):
    cases_path = Path("evaluation_cases/sre-signal-validation-sample.json")
    output_dir = tmp_path / "out"

    completed = subprocess.run(
        [sys.executable, "-m", "elenchus_core.cli", str(cases_path), str(output_dir)],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "strong-lock-contention" in completed.stdout
    result = json.loads((output_dir / "result.json").read_text())
    assert result["case_count"] == 2
    assert result["calibration"] == "uncalibrated_internal_alpha"
    rows = list(csv.DictReader((output_dir / "comparison.csv").open()))
    assert [row["id"] for row in rows] == ["strong-lock-contention", "unsupported-rollback"]
    assert rows[0]["human_label"] == "strong_specific"
    assert rows[1]["recommendation"] in {"reconsider", "escalate"}
