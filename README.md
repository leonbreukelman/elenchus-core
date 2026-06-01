# Elenchus Core

Python core for Elenchus Validator: an internal-alpha task-local evidence-resolving explanation-quality auditor for agent workflows.

Elenchus Core is an advisory signal only. It is not a truth oracle, hidden chain-of-thought detector, autonomous allow/deny gate, production safety system, calibrated decision system, or action-correctness judge. Until human-labeled calibration exists, outputs remain `uncalibrated_internal_alpha` and require operator review.

## Product claim

Given context, a proposed typed action, and a public rationale, Elenchus estimates whether the rationale specifically supports the proposed action over typed near-neighbor alternatives, whether load-bearing rationale anchors are present in supplied context, and, for v2 structured requests, whether load-bearing public structured rationale grounds cite task-local artifacts that mechanically resolve.

For structured evidence-backed requests, Elenchus separates mechanical artifact validation from fuzzy support scoring:

- Mechanical validation checks task-local evidence refs, duplicate artifact IDs, content pointers, local content availability, and supplied sha256 self-consistency.
- Advisory support scoring is a conservative lexical-overlap proxy only; it is not entailment, external provenance validation, objective truth validation, or action correctness.
- Counterfactual probing is reported as `not_run` unless an operational-agent re-execution contract is supplied.

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

`POST /api/v2/evaluate` accepts legacy free-text requests and additive structured evidence fields:

```json
{
  "traceId": "sre-monitor-001",
  "domain": "sre",
  "context": "Postgres primary has 95% I/O wait. 12 idle in transaction sessions hold locks on audit_logs and block VACUUM.",
  "proposedAction": {"type": "terminate_idle_sessions", "target": "postgres-primary", "riskLevel": "medium"},
  "rationale": "Because 12 idle in transaction sessions are holding locks on audit_logs and blocking VACUUM, terminating them releases the locks rather than only adding capacity.",
  "structuredRationale": {
    "claim": "Terminate idle database sessions holding locks.",
    "grounds": [{"text": "12 idle in transaction sessions hold locks on audit_logs.", "evidenceRefs": ["pg-stat-activity"], "loadBearing": true}],
    "rejectedAlternatives": [{"actionId": "increase_iops", "reason": "I/O capacity does not release the specific locks."}],
    "uncertainty": ["Session owners still need post-action review."],
    "wouldChangeIf": ["If sessions are active user writes, page a human instead."]
  },
  "evidenceBundle": [{
    "id": "pg-stat-activity",
    "type": "query_result",
    "contentPointer": "postgres://primary/pg_stat_activity?snapshot=2026-06-01T00:00Z",
    "content": "12 idle in transaction sessions hold locks on audit_logs and block VACUUM"
  }],
  "domainHints": ["cloud"]
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
- task-local evidence-resolving explanation auditor for public structured rationale
- mechanical evidence validation separate from advisory lexical support scoring
- thin domain lenses for `sre`, `tech`, `cloud`, `security`, `software`, and `ai_ml`
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
- paid/live LLM provider adapters in production code
- operational-agent re-execution/counterfactual probing contract
- external artifact dereferencing or provenance certification
- production calibration claims

