# Elenchus Core Python Port Plan

Goal: create a standalone Python repo that ports the useful core of `elenchus-validator` while keeping the product claim narrow: uncalibrated rationale-action specificity and supplied-context grounding.

Implementation scope:

1. Build a Python package under `src/elenchus_core` with Pydantic models.
2. Port deterministic evaluator behavior first: Toulmin/specificity, alternatives, SRE policy, grounding, report assembly.
3. Add an audit-safe file logger that does not persist raw context/rationale/anchor text.
4. Add FastAPI endpoints compatible with `/api/v2/evaluate` and legacy `/api/v1/intercept` response shape.
5. Add a CLI runner for labeled SRE validation files.
6. Verify with pytest, ruff, mypy, and local API/CLI smoke checks.

Non-goals for this initial port:

- no Hermes sidecar surface
- no MCP server
- no live paid LLM provider calls
- no production allow/deny gate
- no calibration upgrade beyond `uncalibrated_internal_alpha`
