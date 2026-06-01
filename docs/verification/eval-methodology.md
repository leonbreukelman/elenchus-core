# Evaluation Methodology

Elenchus Core evaluates one narrow signal:

> Given supplied context, a proposed typed action, and a public rationale, does the rationale specifically support that action over near-neighbor alternatives, and are its load-bearing anchors present in the supplied context?

It does not validate objective truth, hidden model cognition, chain-of-thought faithfulness, alignment, bias, safety, or production readiness.

## Runner

Run the curated suite:

```bash
uv run python scripts/run_eval_suite.py evaluation_cases/curated benchmark-output/eval-suite
```

Outputs:

- `result.json`: sanitized case and pair rows plus aggregate metrics.
- `failures.jsonl`: sanitized failure rows only.
- `summary.md`: short human-readable run summary.

`benchmark-output/` is ignored because generated reports may still be operationally sensitive even after allowlist sanitization.

## Sanitized artifact contract

Per-case generated rows include only:

- case id
- split
- behavior label
- scenario tags
- source benchmark name
- status
- recommendation
- calibration
- numeric scores/subscores
- support-margin numbers
- grounding counts only
- policy finding codes and severities
- readiness review reason codes
- operator-review and blocked-use metadata
- pass/fail booleans and failure codes

The runner intentionally omits raw context, raw rationale, raw anchor text, normalized anchor text, evidence snippets, contradiction snippets, Toulmin prose, alternative rationales, and source item text.

## Expected behavior checks

For ordinary cases, tests require:

- `status == "complete"`
- `recommendation != "abort_signal_only"`
- `calibration == "uncalibrated_internal_alpha"`
- `operatorReviewRequired == true`
- blocked use includes `production_allow_deny`

`abort_signal_only` is an error sentinel, not a restrictive recommendation. Cap checks fail if a non-error-path case returns it.

Recommendation caps use the single source of truth exported by `elenchus_core.report.RECOMMENDATION_CAP_ORDER`:

```python
("proceed", "proceed_with_caveats", "reconsider", "escalate")
```

## Pairwise checks

Paired adversarial cases evaluate a supported case and a challenged case with the same intended action pattern, then assert that the supported case ranks higher on a targeted metric such as `contextGrounding`. This is a regression signal for coupling/grounding behavior, not a calibrated statistical claim.

## Interpreting results

A passing suite means the deterministic Python implementation preserved hard product invariants and handled curated intended-use examples as expected. It does not mean the evaluator is calibrated, production-ready, or generally correct on real incidents. Real incident use should remain advisory and operator-reviewed until human-labeled calibration and deployment controls exist.
