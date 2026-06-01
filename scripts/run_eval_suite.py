#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from elenchus_core.eval_suite import run_eval_suite


def main() -> int:
    parser = argparse.ArgumentParser(description="Run sanitized Elenchus Core curated evaluation suite.")
    parser.add_argument("input_dir", type=Path, help="Directory containing smoke.jsonl and/or paired_adversarial.jsonl")
    parser.add_argument("output_dir", type=Path, help="Directory for sanitized result.json, failures.jsonl, summary.md")
    args = parser.parse_args()

    result = run_eval_suite(args.input_dir, args.output_dir)
    print(
        json.dumps({"case_count": result["case_count"], "pair_count": result["pair_count"], "passed": result["passed"]})
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
