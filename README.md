# Elenchus Core

Python core for Elenchus Validator: an internal-alpha rationale-action specificity and context-grounding signal for agent workflows.

Elenchus Core is not a truth oracle, hidden chain-of-thought detector, autonomous allow/deny gate, production safety system, or calibrated decision system. Until human-labeled calibration exists, outputs remain `uncalibrated_internal_alpha` and require operator review.

## Product claim

Given context, a proposed typed action, and a public rationale, Elenchus estimates whether the rationale specifically supports the proposed action over typed near-neighbor alternatives and whether load-bearing rationale anchors are present, absent, or contradicted in the supplied context.

## Local development

```bash
uv sync --dev
uv run pytest
uv run ruff check .
uv run mypy
```

## API

```bash
uv run uvicorn elenchus_core.http:app --reload
```

`POST /api/v2/evaluate` accepts:

```json
{
  "traceId": "sre-monitor-001",
  "domain": "sre",
  "context": "Postgres primary has 95% I/O wait. 12 idle in transaction sessions hold locks on audit_logs and block VACUUM.",
  "proposedAction": {"type": "terminate_idle_sessions", "target": "postgres-primary", "riskLevel": "medium"},
  "rationale": "Because 12 idle in transaction sessions are holding locks on audit_logs and blocking VACUUM, terminating them releases the locks rather than only adding capacity."
}
```

Set ELENCHUS_API_TOKEN to require a Bearer token in the Authorization header.

## CLI validation runner

```bash
uv run elenchus-evaluate evaluation_cases/sre-signal-validation-sample.json benchmark-output/sample-run
```

The runner writes `result.json` and `comparison.csv`.

## Curated intended-use evaluation suite

The Python core now includes deterministic, sanitized intended-use fixtures for the first SRE/incident-response wedge:

```bash
uv run python scripts/run_eval_suite.py evaluation_cases/curated benchmark-output/eval-suite
```

The suite writes `result.json`, `failures.jsonl`, and `summary.md` under `benchmark-output/eval-suite/`. Generated artifacts are allowlist-sanitized and are ignored by git. See:

- `docs/verification/benchmark-curation.md`
- `docs/verification/ai-dataset-source-catalog.md`
- `docs/verification/eval-methodology.md`

## Scope of this Python port

Implemented now:

- Pydantic request/report models
- deterministic evaluator pipeline
- SRE policy overlay
- near-neighbor alternatives
- Toulmin/specificity heuristics
- deterministic context-grounding proxy
- audit-safe file logger
- FastAPI v2 endpoint plus v1 compatibility endpoint
- signal-validation CLI

Deferred intentionally:

- sidecar integration
- MCP server surface
- paid/live LLM provider adapters
- production calibration claims

