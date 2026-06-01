# Fresh Session Prompt: Execute Elenchus Core Evaluation Tests

Repo: `/home/leonb/projects/elenchus-core`

Goal: Implement the Opus-reviewed evaluation test harness described in `docs/plans/2026-05-31-evaluation-test-execution-plan.md`.

Mandatory context to read first:
1. `docs/plans/2026-05-31-evaluation-test-execution-plan.md`
2. `docs/verification/2026-05-31-evaluation-test-plan-opus-review.md`
3. `src/elenchus_core/models.py`
4. `src/elenchus_core/report.py`
5. `src/elenchus_core/evaluator.py`
6. `src/elenchus_core/grounding.py`
7. `.gitignore`

Hard boundaries:
- Do not add live model/provider calls.
- Do not download or vendor full benchmark datasets.
- Do not include credentials, customer data, hidden chain-of-thought, or raw sensitive incidents.
- Do not tune evaluator weights/regexes around fixtures unless a failing regression test proves a general bug and the user authorizes the production-code change.
- Treat benchmark-derived examples as scenario-provenance tags, not benchmark submissions or detector claims.
- Keep outputs `uncalibrated_internal_alpha` and operator-review-required.
- Do not commit, push, deploy, or run spend-incurring providers without explicit user authorization.

Start by running:

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

If the tree is dirty, classify files before editing:
- current plan/review docs: OK to continue;
- unrelated source/test edits: stop and ask;
- generated caches/output: ignore or clean only with authorization.

Implementation sequence, using strict TDD:

1. Phase 1: recommendation contract/error sentinel
   - Create `tests/test_recommendation_contract.py` first.
   - Watch it fail.
   - Export a recommendation cap order from `src/elenchus_core/report.py` and update `_cap_recommendation` to use it.
   - Verify error reports expose null numeric signals and `abort_signal_only` as an error sentinel, not a restrictive recommendation.

2. Phase 2: eval-case schema/loaders
   - Create `tests/test_eval_case_schema.py` first.
   - Implement `src/elenchus_core/eval_cases.py` with strict Pydantic models, JSON/JSONL loaders, behavior labels, scenario tags, split handling, and `recommendation_at_most` that returns false for `abort_signal_only` in ordinary cap checks.

3. Phase 3: runner sanitizer/metrics
   - Create `tests/test_eval_suite_runner.py` first.
   - Implement `scripts/run_eval_suite.py`.
   - Sanitization must be allowlist-only.
   - Sentinel context/rationale tokens must not appear in `result.json`, `summary.md`, or `failures.jsonl`.
   - Error/non-complete reports must count as failures except for explicit `error_path` cases.

4. Phase 4: smoke vertical slice
   - Create `evaluation_cases/curated/smoke.jsonl` with one supported SRE case.
   - Create `tests/test_curated_eval_cases.py` and verify invariants.

5. Phase 5: expand curated smoke set
   - Add 16-20 small synthetic cases.
   - Cover behavior labels: supported, unsupported, contradicted, action_mismatch, policy_blocked, error_path.
   - Cover scenario tags honestly: gsm8k_style_numeric, bbh_style_logic, truthfulqa_style_misconception, sycophancy_seed, bbq_style_ambiguity, numeric_absent_anchor, shuffled_context_control, surface_overlap_control.
   - Do not assert capabilities the evaluator does not have.

6. Phase 6: paired adversarial ordering
   - Create `evaluation_cases/curated/paired_adversarial.jsonl`.
   - Create `tests/test_paired_adversarial_ordering.py`.
   - Hold domain/action type constant within pairs unless action mismatch is the target.
   - Prefer targeted subscore ordering with explicit `min_pair_delta` over exact overall-score bands.

7. Phase 7: negative controls/trivial baselines
   - Add shuffled context, surface overlap, absent numeric, generic fallback, and contradiction-flip controls.

8. Phase 8: verification docs
   - Create `docs/verification/benchmark-curation.md` and `docs/verification/eval-methodology.md`.
   - Update `README.md` to link them.
   - Include: `uncalibrated_internal_alpha`, not a benchmark submission, operator review required, no hidden chain-of-thought, scenario-provenance tags are not detector claims, not lockbox/calibration evidence.

9. Phase 9: full verification
   - Run:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q
uv run python scripts/run_eval_suite.py evaluation_cases/curated benchmark-output/eval-suite
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
git diff --check
git status --short
```

Final response requirements:
- State exactly which files changed.
- Paste the actual verification command results, not guesses.
- State whether implementation is committed or uncommitted.
- If any test is quarantined/exploratory, name it and explain why.
- Do not claim validation, calibration, benchmark performance, alignment measurement, or production readiness.
