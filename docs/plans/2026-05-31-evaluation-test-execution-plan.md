# Elenchus Core Evaluation Test Execution Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build and run a deterministic, benchmark-derived test harness that validates Elenchus Core's narrow internal-alpha contract: public rationale-action specificity and context-grounding for supplied context, proposed action, and public rationale.

**Architecture:** Add strict evaluation-case schemas, small curated JSONL fixtures, pytest contract tests, paired adversarial ordering tests, and an offline eval runner that emits sanitized allowlisted aggregate metrics. Benchmark-derived items are scenario seeds and regression fixtures, not benchmark submissions, alignment scores, truth validation, or calibration evidence.

**Tech Stack:** Python 3.12, uv, pytest, Pydantic v2, ruff, mypy, JSONL fixtures, existing deterministic `elenchus_core.evaluate_request`.

**Review Status:** Opus reviewed this plan and returned `ACCEPT_WITH_CHANGES`. The critical changes from `docs/verification/2026-05-31-evaluation-test-plan-opus-review.md` are incorporated here: error/`abort_signal_only` cannot pass caps, artifact sanitization must be allowlist + sentinel-tested, non-SRE alignment labels are scenario-provenance tags rather than detector claims, recommendation cap ordering excludes `abort_signal_only`, CI/exploratory separation is enforced, and paired tests hold domain/action factors constant or assert targeted subscores.

---

## Product Boundary

Elenchus Core remains `uncalibrated_internal_alpha`.

This test program may support these claims:
- The Python evaluator preserves hard advisory/product invariants.
- Curated cases exercise known grounding/action-coupling failure modes.
- The harness detects regressions against expected advisory behavior.
- Scores provide directional internal diagnostics only.

This test program must not claim:
- Truth validation.
- Hidden chain-of-thought faithfulness.
- Alignment benchmark performance.
- Bias, sycophancy, or hallucination detection as standalone capabilities.
- Production allow/deny readiness.
- Calibration, certification, safety approval, or lockbox attestation.

## Existing Repo State

Current repo: `/home/leonb/projects/elenchus-core`

Already present:
- `src/elenchus_core/evaluator.py` deterministic evaluator.
- `src/elenchus_core/grounding.py` anchor extraction/status heuristics.
- `src/elenchus_core/report.py` recommendation/readiness semantics.
- `src/elenchus_core/policy.py` SRE policy overlay.
- `src/elenchus_core/cli.py` basic JSON evaluation runner.
- Current tests under `tests/`.
- `evaluation_cases/sre-signal-validation-sample.json`.
- `.gitignore` already ignores `benchmark-output/` and `.elenchus-audit/`.

Current gates to preserve:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q
```

## Evaluation Design

### Behavior Labels vs Scenario Provenance Tags

Do not encode benchmark families as detector claims.

Each case has one behavior label:
- `supported`: rationale anchors are present and action is specifically supported.
- `unsupported`: rationale relies on absent anchors.
- `contradicted`: context directly contradicts load-bearing anchors.
- `action_mismatch`: rationale supports a near-neighbor action more strongly than the proposed action.
- `policy_blocked`: SRE policy overlay should add blocker/warning findings.
- `error_path`: intentionally exercises safe error reporting.
- `invalid`: intentionally schema-invalid fixture for loader validation only; not evaluated.

Each case may also have `scenario_tags`, which are provenance/stress tags, not claimed capabilities:
- `sre_native`
- `gsm8k_style_numeric`
- `bbh_style_logic`
- `truthfulqa_style_misconception`
- `sycophancy_seed`
- `bbq_style_ambiguity`
- `numeric_absent_anchor`
- `shuffled_context_control`
- `surface_overlap_control`

A `sycophancy_seed` case is still judged only as unsupported/contradicted/fallback-grounded under the current evaluator. A `bbq_style_ambiguity` case is judged only as unsupported assumption/fallback-grounded. A `gsm8k_style_numeric` case checks absent/present numeric anchors; it does not prove arithmetic correctness.

### Fixture Rules

- Commit only small, transformed synthetic fixtures with source metadata and license/source URLs where applicable.
- Do not vendor full benchmark datasets in this repo.
- Do not include credentials, customer data, raw hidden model chain-of-thought, or sensitive real incidents.
- Public rationales only; never hidden CoT.
- Expected labels and source metadata are used only by tests/runners and are never passed to `evaluate_request`.
- Generated artifacts are sanitized by allowlist, not denylist.
- Generated artifacts must not include raw context, raw rationale, grounding anchor text, normalized anchor text, context evidence, contradiction evidence, Toulmin prose, or alternative rationale prose.

### CI vs Exploratory Separation

- CI-blocking fixtures live in `split in {"smoke", "paired"}`.
- Exploratory fixtures live in `split == "exploratory"` and are only processed by the offline runner.
- Future lockbox fixtures live in `split == "lockbox"`; until a blindness protocol exists, docs must warn that all current cases are author-visible curated fixtures and not lockbox evidence.
- Quarantined known weaknesses must use an explicit mechanism: `pytest.mark.xfail(strict=True)` with a tracked issue reference or an `exploratory` split. Do not silently drop failures.

## File Plan

Create:
- `src/elenchus_core/eval_cases.py`
- `tests/test_eval_case_schema.py`
- `tests/test_recommendation_contract.py`
- `tests/test_curated_eval_cases.py`
- `tests/test_paired_adversarial_ordering.py`
- `tests/test_eval_suite_runner.py`
- `scripts/run_eval_suite.py`
- `evaluation_cases/curated/smoke.jsonl`
- `evaluation_cases/curated/paired_adversarial.jsonl`
- `docs/verification/benchmark-curation.md`
- `docs/verification/eval-methodology.md`

Modify:
- `src/elenchus_core/report.py` to expose a single recommendation-cap order constant used by report and tests.
- `README.md` to point to the verification docs after implementation.

Avoid modifying in this slice unless a RED test proves it necessary:
- `src/elenchus_core/grounding.py` weights/regexes.
- `src/elenchus_core/evaluator.py` scoring formula.
- Provider/live model code.

Do not implement in this slice:
- Live model/provider simulations.
- Benchmark dataset downloaders.
- Human-label calibration.
- Threshold tuning based on fixture outcomes.

## Schema Shape

`src/elenchus_core/eval_cases.py` should define strict Pydantic models. Exact names may vary, but the model must support:

```python
BehaviorLabel = Literal[
    "supported",
    "unsupported",
    "contradicted",
    "action_mismatch",
    "policy_blocked",
    "error_path",
    "invalid",
]
SplitName = Literal["smoke", "paired", "exploratory", "lockbox"]
ScenarioTag = Literal[
    "sre_native",
    "gsm8k_style_numeric",
    "bbh_style_logic",
    "truthfulqa_style_misconception",
    "sycophancy_seed",
    "bbq_style_ambiguity",
    "numeric_absent_anchor",
    "shuffled_context_control",
    "surface_overlap_control",
]

class ExpectedBehavior(BaseModel):
    label: BehaviorLabel
    recommendation_max: EvaluationRecommendation | None = None
    min_absent_anchors: int = 0
    min_contradicted_anchors: int = 0
    review_reasons_include: list[EvaluationReviewReason] = []
    policy_findings_include: list[str] = []
    require_complete: bool = True
    ordering_metric: Literal["overallSignal", "contextGrounding", "actionCoupling", "alternativeResistance"] | None = None
    min_pair_delta: float | None = None
```

Important schema constraints:
- `extra="forbid"` everywhere.
- `request` is an actual `EvaluationRequest`; fixture keys must use camelCase fields like `traceId`, `proposedAction`, `riskLevel`, `expectedEffect`.
- Expected/source/split fields must not be copied into `request.metadata` automatically.
- `review_reasons_include` should use the existing `EvaluationReviewReason` literal set from `models.py` so typos fail validation.

Loader scope:
- New strict loaders are only for `evaluation_cases/curated/`.
- The existing `evaluation_cases/sre-signal-validation-sample.json` may remain supported by the legacy CLI and does not need to satisfy the new strict schema unless explicitly migrated.

## Recommendation-Cap Semantics

`abort_signal_only` is not a restrictive recommendation. It is an error sentinel.

Implementation requirement:
- Export a single recommendation cap order from `report.py`, for example:

```python
RECOMMENDATION_CAP_ORDER: tuple[EvaluationRecommendation, ...] = (
    "proceed",
    "proceed_with_caveats",
    "reconsider",
    "escalate",
)
```

- Update `_cap_recommendation` to use that constant.
- Add a test helper `recommendation_at_most(actual, cap)` using the same constant.
- If `actual == "abort_signal_only"`, cap checks for non-`error_path`/non-`invalid` cases must fail because the evaluation did not complete.
- Every non-`invalid` and non-`error_path` fixture must assert `report.status == "complete"` before behavioral assertions.

## Sanitization Contract

The offline runner must sanitize by allowlist.

Allowed per-case fields in generated artifacts:
- case id
- split
- behavior label
- scenario tags
- source benchmark name only, not raw source text
- status
- recommendation
- calibration
- numeric scores/subscores
- support margin numbers
- grounding counts only: present/absent/contradicted/loadBearing
- policy finding codes/severities only
- readiness review reason codes
- pass/fail booleans and failure codes

Forbidden generated artifact fields/content:
- raw `context`
- raw `rationale`
- `grounding.anchors[].text`
- `grounding.anchors[].normalizedText`
- `grounding.anchors[].contextEvidence`
- `grounding.anchors[].contradictionEvidence`
- `toulmin.*` prose
- `alternatives[].rationale`
- credentials or connection strings

Sentinel test:
- At least one smoke fixture should include unique tokens like `CTX_SENTINEL_DO_NOT_LEAK_7319` in context and `RAT_SENTINEL_DO_NOT_LEAK_7319` in rationale.
- `tests/test_eval_suite_runner.py` must run the runner in a temp output directory and assert those tokens appear in none of `result.json`, `summary.md`, or `failures.jsonl`.

## Execution Plan

### Phase 0: Preflight and baseline

**Objective:** Capture current clean baseline before edits.

Run:

```bash
pwd
git status --short
git diff --stat
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q
```

Expected:
- Working directory is `/home/leonb/projects/elenchus-core`.
- No unexpected dirty files beyond this plan/review if implementation starts later in the same tree.
- Existing gates pass before feature edits.

### Phase 1: Recommendation contract and error sentinel

**Objective:** Make cap semantics safe before fixture assertions depend on them.

**Files:**
- Modify: `src/elenchus_core/report.py`
- Create: `tests/test_recommendation_contract.py`

**RED tests:**
- `RECOMMENDATION_CAP_ORDER` excludes `abort_signal_only`.
- `_cap_recommendation("proceed", "reconsider") == "reconsider"`.
- `_cap_recommendation("reconsider", "proceed_with_caveats") == "reconsider"`.
- Error report has `status == "error"`, `recommendation == "abort_signal_only"`, `overallSignal is None`, `confidence is None`, `readiness.advisorySummary == "error_no_numeric_signal"`, and `"incomplete_evaluation" in reviewReasons`.

Run RED:

```bash
uv run pytest tests/test_recommendation_contract.py -q
```

Implement the exported constant and adjust `_cap_recommendation` to use it.

Run GREEN:

```bash
uv run pytest tests/test_recommendation_contract.py -q
uv run pytest tests/test_evaluator.py -q
```

### Phase 2: Strict eval-case schema and loaders

**Objective:** Validate curated fixture format before writing many cases.

**Files:**
- Create: `tests/test_eval_case_schema.py`
- Create: `src/elenchus_core/eval_cases.py`

**RED tests:**
- Loads one JSONL `EvalCase` with nested `EvaluationRequest`.
- Rejects unknown fields.
- Rejects invalid split/label/tag.
- Rejects thresholds/counts outside allowed ranges.
- `recommendation_at_most("reconsider", "proceed_with_caveats")` is true.
- `recommendation_at_most("proceed", "reconsider")` is false.
- `recommendation_at_most("abort_signal_only", "proceed_with_caveats")` is false.
- Expected/source/split fields do not appear in `case.request.metadata` unless explicitly supplied as safe request metadata.

Run RED:

```bash
uv run pytest tests/test_eval_case_schema.py -q
```

Implement strict Pydantic models and JSON/JSONL loaders.

Run GREEN:

```bash
uv run pytest tests/test_eval_case_schema.py -q
```

### Phase 3: Runner sanitizer and metric helpers before real fixtures

**Objective:** Prove output sanitization and metric handling with temp synthetic cases.

**Files:**
- Create: `tests/test_eval_suite_runner.py`
- Create: `scripts/run_eval_suite.py`

**RED tests for pure helpers:**
- `sanitize_report_outcome` returns only allowlisted keys.
- Sentinel tokens in context/rationale do not appear in serialized sanitized output.
- `status != complete` counts as invariant failure and cap violation for ordinary cases.
- `error_path` cases count separately and preserve null numeric signals.
- `compute_pair_ordering_accuracy` treats nulls and ties inside `min_pair_delta` as failures.
- `compute_label_counts` reports null counts separately from null-excluded means.
- Runner output path under `benchmark-output/` is gitignored.

Run RED:

```bash
uv run pytest tests/test_eval_suite_runner.py -q
```

Implement runner helpers and a CLI:

```bash
uv run python scripts/run_eval_suite.py evaluation_cases/curated benchmark-output/eval-suite
```

Runner outputs:
- `result.json`: aggregate metrics and sanitized per-case outcomes.
- `summary.md`: concise summary with strongest positive/negative findings.
- `failures.jsonl`: sanitized failure records only.

Run GREEN:

```bash
uv run pytest tests/test_eval_suite_runner.py -q
```

### Phase 4: Curated smoke vertical slice

**Objective:** Prove one end-to-end fixture before expanding the matrix.

**Files:**
- Create: `evaluation_cases/curated/smoke.jsonl`
- Create: `tests/test_curated_eval_cases.py`

**RED test:**
- Load smoke cases.
- Assert there is at least one `supported` + `sre_native` case.
- Evaluate it.
- Assert universal invariants:
  - `report.status == "complete"`;
  - `report.calibration == "uncalibrated_internal_alpha"`;
  - `report.readiness.operatorReviewRequired is True`;
  - `"production_allow_deny" in report.readiness.blockedUses`;
  - no complete report uses `abort_signal_only`.
- Assert case-specific expected behavior.

Run RED:

```bash
uv run pytest tests/test_curated_eval_cases.py -q
```

Add one supported SRE fixture using explicit present anchors.

Run GREEN:

```bash
uv run pytest tests/test_curated_eval_cases.py -q
```

### Phase 5: Expand smoke set with honest expectations

**Objective:** Cover core failure modes without overclaiming capabilities.

Add cases incrementally, running the targeted test after each small group:

```bash
uv run pytest tests/test_curated_eval_cases.py -q
```

Initial target: 16–20 cases.

Required behavior-label coverage:
- `supported`: SRE-native with present numeric/entity/mechanism anchors.
- `unsupported`: absent release/resource/numeric anchors.
- `contradicted`: no deployment vs deployment-regression rationale; CPU normal vs CPU saturation rationale.
- `action_mismatch`: rationale supports scale-up but proposed action is rollback, and vice versa.
- `policy_blocked`: `domain="sre"` and action type in `{delete_data, drop_database, force_push}` for `irreversible_action_blocker`; high/critical risk for `high_risk_operator_review_required` warning.
- `error_path`: provider/forced-error test can live in pytest rather than fixture if cleaner.

Required scenario-tag coverage, with honest expectations:
- `gsm8k_style_numeric`: absent/present numeric anchors only; no arithmetic correctness claim.
- `truthfulqa_style_misconception`: either SRE-shaped contradiction or generic fallback/unsupported; no truth detector claim.
- `sycophancy_seed`: unsupported/fallback or absent anchors; no sycophancy detector claim.
- `bbq_style_ambiguity`: unsupported assumption/fallback; no bias detector claim.
- `surface_overlap_control`: rationale shares words with action but context is irrelevant or shuffled.

Avoid tight absolute score bands. Prefer structural assertions:
- min absent anchors.
- min contradicted anchors.
- recommendation cap.
- conditional review reasons: `contradicted_grounding`, `weak_context_grounding`, `policy_blocker`, `fallback_grounding`, `low_overall_signal`, `incomplete_evaluation`.

Do not assert vacuous always-present reasons like `uncalibrated_internal_alpha` or `specificity_margin_unreliable` except in global product-invariant tests.

### Phase 6: Paired adversarial ordering tests

**Objective:** Verify controlled contrast cases rank in the expected direction.

**Files:**
- Create: `evaluation_cases/curated/paired_adversarial.jsonl`
- Create: `tests/test_paired_adversarial_ordering.py`

**RED test:**
- Load pairs.
- Evaluate supported and challenged members.
- For ordinary pairs, assert both reports are complete.
- Hold `domain` constant within each pair.
- Prefer same action type within each pair unless testing action mismatch explicitly.
- Use `expected.ordering_metric`; default to `contextGrounding` for grounding pairs.
- Assert `supported_metric >= challenged_metric + min_pair_delta` with a small explicit margin, e.g. `0.05`, rather than strict `>`.
- Assert challenged contradicted cases do not recommend `proceed`.

Run RED:

```bash
uv run pytest tests/test_paired_adversarial_ordering.py -q
```

Add 8–10 pairs:
- deployment rollback supported vs no deployment contradicted;
- CPU scale-out supported vs CPU normal contradicted;
- memory leak supported vs memory steady contradicted;
- lock contention supported vs no locks contradicted;
- numeric threshold present vs absent;
- rollback-vs-scale action mismatch with same SRE domain;
- sycophancy-seed unsupported vs evidence-supported, with expectations limited to fallback/absence;
- BBQ-style unsupported assumption vs evidence-supported, with expectations limited to fallback/absence;
- shuffled context control;
- surface-overlap control.

Run GREEN:

```bash
uv run pytest tests/test_paired_adversarial_ordering.py -q
```

### Phase 7: Negative controls and trivial baselines

**Objective:** Make aggregate metrics harder to game by lexical overlap alone.

Add tests/cases for:
- shuffled/irrelevant context degrades grounding;
- empty/garbage rationale cannot be labeled supported;
- same rationale against supporting vs contradicting context flips `summary.contradicted`;
- near-duplicate hyphenated tokens do not create spurious entity success;
- surface action-word overlap does not bypass absent/contradicted grounding;
- generic/non-SRE cases fall back honestly rather than pretending contradiction support.

These may live in `tests/test_curated_eval_cases.py` or as `surface_overlap_control` cases in `smoke.jsonl`.

Run:

```bash
uv run pytest tests/test_curated_eval_cases.py tests/test_paired_adversarial_ordering.py -q
```

### Phase 8: Verification docs

**Objective:** Prevent future overclaiming and explain fixture provenance.

**Files:**
- Create: `docs/verification/benchmark-curation.md`
- Create: `docs/verification/eval-methodology.md`
- Modify: `README.md`

Docs must include these phrases/concepts:
- `uncalibrated_internal_alpha`
- not a benchmark submission
- operator review required
- no hidden chain-of-thought
- scenario-provenance tags are not detector claims
- author-visible fixtures are not lockbox/calibration evidence
- generated artifacts are sanitized allowlisted summaries
- live model simulation is future work and spend-gated

Doc marker check:

```bash
python3 - <<'PY'
from pathlib import Path
markers = [
    'uncalibrated_internal_alpha',
    'not a benchmark submission',
    'operator review',
    'no hidden chain-of-thought',
    'scenario-provenance',
    'not detector claims',
    'not lockbox',
]
for path in [Path('docs/verification/benchmark-curation.md'), Path('docs/verification/eval-methodology.md')]:
    text = path.read_text(encoding='utf-8').lower()
    missing = [m for m in markers if m.lower() not in text]
    if missing:
        raise SystemExit(f'{path}: missing {missing}')
print('doc markers ok')
PY
```

### Phase 9: Full local verification and artifact inspection

Run:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q
uv run python scripts/run_eval_suite.py evaluation_cases/curated benchmark-output/eval-suite
```

Inspect generated files:

```bash
python3 - <<'PY'
from pathlib import Path
out = Path('benchmark-output/eval-suite')
for name in ['result.json', 'summary.md', 'failures.jsonl']:
    path = out / name
    assert path.exists(), path
    text = path.read_text(encoding='utf-8')
    for forbidden in [
        'CTX_SENTINEL_DO_NOT_LEAK',
        'RAT_SENTINEL_DO_NOT_LEAK',
        'raw_context',
        'raw_rationale',
        'contextEvidence',
        'contradictionEvidence',
    ]:
        assert forbidden not in text, (path, forbidden)
print('artifact inspection ok')
PY
```

Then:

```bash
git diff --check
git status --short
```

Expected:
- lint, typecheck, and tests pass;
- eval runner exits 0;
- output artifacts are generated under ignored `benchmark-output/`;
- generated artifacts do not leak sentinel/raw prose;
- dirty tree contains only intentional source/docs/fixture/test changes.

## Commit Boundary

Commit only after implementation and verification pass.

Suggested commit:

```bash
git add \
  src/elenchus_core/report.py \
  src/elenchus_core/eval_cases.py \
  tests/test_recommendation_contract.py \
  tests/test_eval_case_schema.py \
  tests/test_eval_suite_runner.py \
  tests/test_curated_eval_cases.py \
  tests/test_paired_adversarial_ordering.py \
  scripts/run_eval_suite.py \
  evaluation_cases/curated \
  docs/verification/benchmark-curation.md \
  docs/verification/eval-methodology.md \
  README.md

git commit -m "test: add curated evaluation harness"
```

Do not commit:
- `benchmark-output/`
- `.elenchus-audit/`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- live model outputs
- downloaded full benchmark datasets

## Future Work After This Plan

- Optional benchmark dataset builder scripts after license review.
- Spend-gated model-generated simulation lane.
- Human-label review workflow.
- True split/lockbox protocol once enough cases exist and evaluator rules are frozen before lockbox inspection.
- TypeScript-oracle parity checks if the original TypeScript repo remains the canonical reference.
