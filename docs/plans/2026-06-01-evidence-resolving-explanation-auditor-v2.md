# Evidence-Resolving Explanation Auditor v2 Implementation Plan

> **For Hermes:** Use disciplined-project-delivery, test-driven-development, systematic-debugging, and requesting-code-review. This plan is intentionally a session-sized vertical slice, not the entire future Elenchus platform.

**Goal:** Upgrade Elenchus Core from an SRE-weighted rationale/action specificity prototype into a broader tech-operations explanation-quality auditor that resolves load-bearing public-rationale evidence against task-local artifacts, while keeping the output advisory-only and backwards compatible with the current API.

**Architecture:** Keep the current deterministic evaluator, but add a structured public-rationale contract, task-local evidence bundle, evidence-resolution layer, composable domain-lens fragments, method-trust metadata, and anti-overclaiming report semantics. Counterfactual re-execution is not implemented in this slice because no operational-agent runner contract exists yet; the report must explicitly mark counterfactual probing as `not_run` rather than pretending to measure it.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, uv, pytest, ruff, mypy.

---

## Non-goals and safety boundaries

- Do not claim action correctness, objective truth validation, hidden chain-of-thought faithfulness, production allow/deny readiness, calibration, or autonomous approval.
- Do not call live LLMs from production code in this slice.
- Do not require an internet-scale corpus; evidence is task-local only.
- Do not break old unstructured requests using `context`, `proposedAction`, and `rationale`.
- Do not emit raw evidence artifact content in eval-suite sanitized outputs.
- Do not make `proceed` machine-actionable; operator review remains required in internal-alpha mode.

## Acceptance criteria

1. Legacy requests still pass all current tests and curated SRE evaluation cases.
2. New structured requests can include:
   - `availableActions`
   - `structuredRationale` with claim, grounds, warrants, assumptions, rejected alternatives, uncertainty, and would-change-if clauses
   - `evidenceBundle` with stable IDs, type, content pointer, content, and optional sha256 hash
   - `domainHints` / composable lens hints
3. Evidence resolution separates **mechanical artifact validation** from **heuristic support scoring**:
   - referenced artifact exists
   - pointer is present for high trust
   - supplied sha256 hash matches artifact content when present
   - pointer-only artifacts with no local content are treated as `unresolved_pointer`, not verified, because this slice has no dereferencer
   - ground text receives only advisory heuristic support scoring; this fuzzy score cannot by itself uncap or cap recommendations
   - unreferenced load-bearing grounds cannot receive high grounding scores
   - hash mismatches, missing refs, duplicate artifact IDs, or missing required pointers lower/cap recommendations and add explicit weaknesses/review reasons
4. Domain support broadens beyond `sre` without giant packs:
   - `tech`, `cloud`, `security`, `software`, and `ai_ml` are valid domains/hints
   - lenses are thin fragments: action verbs, artifact types, risk predicates, evidence markers, and perturbation templates
   - SRE behavior remains available as one lens, not privileged as the whole product
5. Report output adds method trust / layer status:
   - structural analysis trust
   - evidence-resolution trust
   - counterfactual-probe trust, explicitly `not_run` in this slice
   - blocked uses still include production allow/deny, machine-actionable consumption, hidden-CoT faithfulness, and objective truth validation
6. Anti-gaming improvements:
   - polished unsupported rationales are capped by mechanical evidence-resolution failures, not rewarded by prose quality
   - evidence coverage matters more than verbosity
   - unresolved/missing/hash-mismatched artifacts are explicit
   - keyword-stuffing cannot earn `supported` unless the frozen heuristic rubric requirements are met; even then, it remains advisory
7. Quality gates pass:
   - `uv run ruff check .`
   - `uv run mypy`
   - `uv run pytest -q`
   - `uv run python scripts/run_eval_suite.py evaluation_cases/curated benchmark-output/eval-suite-v2`
8. Independent Opus and Grok reviews are run on the plan before implementation and on the implementation before final handoff. Valid blockers are fixed and re-reviewed.

## Current-state observations

- Current repo is clean on `main` at merge commit `951c7dd`.
- Current core is deterministic and SRE-oriented:
  - `src/elenchus_core/models.py` defines the request/report models.
  - `src/elenchus_core/evaluator.py` orchestrates specificity, near-neighbor alternatives, policy, and grounding.
  - `src/elenchus_core/grounding.py` extracts deterministic numeric/entity/metric/mechanism anchors from free-form rationale/context.
  - `src/elenchus_core/actions.py` hardcodes SRE action alternatives and synonyms.
  - `src/elenchus_core/report.py` builds advisory reports and readiness metadata.
- Current gates:
  - `uv run ruff check .`: passed.
  - `uv run mypy`: passed for configured package scope.
  - `uv run pytest -q`: 40 passed with one dependency warning.
- `uv run mypy .` currently fails on test annotation strictness because pyproject config is package-scoped; the supported gate is `uv run mypy`.

## Plan-review adjustments incorporated

Opus and Grok both returned `ACCEPT_WITH_CHANGES`. The revised implementation rules are:

- Mechanical artifact validation and fuzzy support scoring are separate signals.
- Recommendation caps may use only mechanical facts: missing refs, duplicate artifact IDs, sha256 mismatch, hash supplied without content, pointer required but absent, or pointer-only artifacts that this slice cannot dereference.
- Fuzzy support/contradiction heuristics are advisory-only and cannot silently gate recommendations.
- The top evidence-resolution trust tier requires both matching local content hash and a content pointer. A self-consistent artifact with only invented inline content cannot claim top trust.
- Legacy free-text requests must keep current SRE behavior stable; v2 additive fields must not alter legacy subscores/recommendations.
- EvidenceBundle bounds are explicit: max 50 artifacts, max 20,000 characters per artifact content, max 200,000 total evidence characters per request. Requests above these bounds produce status-safe validation errors or capped evidence resolution; no unbounded tokenization on the FastAPI path.
- Dates are intentionally 2026 because the session date is 2026-06-01.

---

## Implementation tasks

### Task 1: Add structured rationale and task-local evidence models

**Objective:** Extend the public contract without breaking legacy callers.

**Files:**
- Modify: `src/elenchus_core/models.py`
- Test: `tests/test_evidence_contract.py`

**TDD RED:** Add tests that build a request with `structuredRationale`, `availableActions`, `evidenceBundle`, `domainHints`, and `domain="security"`, then assert Pydantic accepts it and legacy request shape still works.

**Implementation notes:**
Add new models:
- `EvidenceArtifact`
  - `id: str`
  - `type: str`
  - `contentPointer: str | None`
  - `content: str | None`
  - `sha256: str | None`
  - `metadata: dict[str, Any] | None`
- `RationaleGround`
  - `text: str`
  - `evidenceRefs: list[str]`
  - `loadBearing: bool = True`
- `RejectedAlternativeRationale`
  - `actionId: str | None`
  - `action: TypedAction | None`
  - `reason: str`
  - `evidenceRefs: list[str] = []`
- `StructuredRationale`
  - `claim: str`
  - `grounds: list[RationaleGround]`
  - `warrants: list[str] = []`
  - `assumptions: list[str] = []`
  - `rejectedAlternatives: list[RejectedAlternativeRationale] = []`
  - `uncertainty: list[str] = []`
  - `wouldChangeIf: list[str] = []`
- `MethodTrust`
  - `structural: Literal["deterministic", "legacy_free_text"]`
  - `evidenceResolution: Literal["self_consistent_artifact_hash", "resolved_artifact_refs", "weak_context_proxy", "missing_or_unresolved_refs", "not_available"]`
  - `counterfactualProbe: Literal["actual_reexecution", "self_report", "not_run"]`
  - `notes: list[str]`
- `EvidenceResolutionAssessment` and related item/summary models, split into:
  - mechanical status counts (`resolved`, `missingRef`, `hashVerified`, `hashMismatch`, `pointerMissing`, `pointerUnresolved`, `duplicateArtifactId`)
  - advisory support counts (`supported`, `unresolved`, `advisoryContradiction`)
  - separate `mechanicalScore`, `supportScore`, and conservative `score` fields

Validation/bounds:
- Max 50 evidence artifacts per request.
- Max 20,000 characters per artifact content and 200,000 total evidence characters per request.
- Duplicate artifact IDs are allowed through request parsing only if needed for status-safe reporting, but evidence resolution must flag them as mechanical failures and treat all colliding IDs as unresolved.

Extend:
- `DomainName` to include `tech`, `cloud`, `security`, `software`, `ai_ml`.
- `EvaluationRequest` with optional `availableActions`, `structuredRationale`, `evidenceBundle`, `domainHints`.
- `EvaluationSubscores` with optional v2-style fields if feasible without breaking existing tests: `evidenceResolution`, `evidenceCoverage`, `structuralCompleteness`.
- `EvaluationReport` with `evidenceResolution: EvidenceResolutionAssessment | None` and `methodTrust: MethodTrust`.

Compatibility: Existing tests must only need updates if the report constructor requires the new fields. Prefer defaulted/explicit fields in report builders.

### Task 2: Implement deterministic evidence resolution

**Objective:** Resolve structured grounds against evidenceBundle and return a score/report independent from old free-form context grounding.

**Files:**
- Create: `src/elenchus_core/evidence.py`
- Modify: `src/elenchus_core/evaluator.py`
- Modify: `src/elenchus_core/report.py`
- Test: `tests/test_evidence_resolution.py`

**TDD RED:** Tests:
1. A ground with a real ref, content pointer, content, and matching sha256 scores high mechanically and records advisory `supported` when the frozen rubric passes.
2. A missing ref records `missing_ref`, lowers mechanical score, and adds a top weakness/review reason.
3. A hash mismatch records `hash_mismatch`, lowers mechanical score, and prevents permissive recommendation.
4. A polished ground with no evidence refs remains structurally analyzable but evidence resolution is low/capped.
5. A keyword-stuffed ground that copies artifact tokens but states an unsupported relation is `unresolved`, not `supported`.
6. A valid negated fact such as “no error budget remaining” is not falsely marked as an advisory contradiction when the artifact says the same thing.
7. `sha256` present with `content=None` is `pointer_unresolved`/unverifiable, not hash-verified.
8. Duplicate/colliding artifact IDs are flagged and treated as unresolved.
9. A ground with mixed valid and missing refs reports both statuses and cannot get perfect mechanical score.

**Implementation notes:**
- Index bundle by artifact ID, but detect duplicates before indexing; duplicate IDs are mechanical failures.
- Hash check: if `artifact.sha256` is present and `artifact.content` is present, compute sha256 of UTF-8 content and compare. If sha256 is present but content is absent, do not verify the hash.
- Pointer trust: refs with no `contentPointer` can resolve content locally but cannot achieve highest method trust.
- Pointer-only artifacts with `contentPointer` and no `content` are `pointer_unresolved`; no fetcher exists in this slice.
- Mechanical score is based only on ref existence, pointer presence, hash validation, duplicate IDs, and local content availability.
- Advisory support rubric is frozen for this slice:
  - Extract ground tokens after stopword removal, numeric values, and entity-like tokens.
  - Require all numeric values in the ground to appear in cited artifact content for `supported`.
  - Require at least one entity/action token overlap and at least 0.45 weighted token coverage for `supported`.
  - If a ground has fewer than three meaningful tokens after stopword removal, default to `unresolved`.
  - Keyword stuffing guard: if the ground has many artifact-overlap tokens but lacks causal/action connective overlap with the claim/action, default to `unresolved`.
  - Simple contradiction/polarity detection is advisory only and must not cap recommendations.
  - If uncertain, mark `unresolved`, not supported.
- Do not leak raw artifact content into report/eval sanitized outputs; include IDs/status/counts only, not full evidence text.
- If no structuredRationale/evidenceBundle exists, return `None` and keep legacy `contextGrounding` behavior byte-stable except for additive report fields.

### Task 3: Add thin composable domain lenses

**Objective:** Replace the mental model of giant domain packs with small versioned lenses and use them for action terms/alternatives without disrupting SRE.

**Files:**
- Create: `src/elenchus_core/lenses.py`
- Modify: `src/elenchus_core/actions.py`
- Modify: `src/elenchus_core/policy.py` if needed
- Test: `tests/test_domain_lenses.py`

**TDD RED:** Tests:
1. `security` requests accept security/cloud actions and generate relevant alternatives such as `revoke_token`, `rotate_secret`, `investigate_more`, `page_human`.
2. `cloud` hints compose with `security` hints with deterministic priority: request domain first, then domainHints in request order, then generic fallback; duplicates are removed preserving first occurrence.
3. Unknown action types still get generic alternatives, not a crash.
4. SRE action synonyms and existing tests remain valid.
5. Lens isolation: enabling `cloud`, `security`, and `ai_ml` hints on a non-SRE request does not alter SRE-only legacy request outputs.

**Implementation notes:**
- `DomainLens` dataclass with `name`, `version`, `action_types`, `action_synonyms`, `artifact_types`, `risk_predicates`, `evidence_markers`, `perturbation_templates`.
- Built-in lenses: `sre`, `security`, `cloud`, `software`, `ai_ml`, `generic`.
- `selected_lenses(request)` from `domain` + `domainHints`.
- `action_terms()` should merge synonyms from all lenses, preserving existing SRE output.
- `generate_near_neighbor_alternatives()` should use selected lenses' action types, capped as today.

### Task 4: Integrate evidence resolution into scoring, recommendations, and readiness

**Objective:** Make evidence resolution load-bearing for v2 reports without overclaiming.

**Files:**
- Modify: `src/elenchus_core/evaluator.py`
- Modify: `src/elenchus_core/report.py`
- Modify: `src/elenchus_core/models.py`
- Test: `tests/test_evaluator_v2.py`

**TDD RED:** Tests:
1. A fully resolved structured rationale gets higher `evidenceResolution` and `contextGrounding` than an eloquent unresolved rationale.
2. Missing/hash-mismatched refs add readiness review reasons and cap recommendation to `reconsider` or stricter.
3. `methodTrust.counterfactualProbe == "not_run"` and report notes say no counterfactual measurement happened in this slice.
4. `productSemantics` uses evidence-resolving explanation-auditor language and refuses action correctness.
5. Error reports include method trust and no fake numeric evidence signal.
6. Legacy free-text requests keep identical legacy subscores/recommendations/support/grounding/readiness except for additive v2 fields.
7. A request with only partial structured fields but no evidence bundle degrades to weak/missing evidence trust rather than crashing.

**Implementation notes:**
- Add new review reasons if needed:
  - `unresolved_evidence_refs`
  - `evidence_hash_mismatch`
  - `counterfactual_probe_not_run`
- Use evidence score to influence `contextGrounding` for structured requests:
  - If evidence assessment exists, `subscores.contextGrounding = min(existing_context_grounding, evidence.score)`.
  - If existing legacy context grounding is absent, use `evidence.score`.
  - Legacy free-text requests with no evidence assessment keep the old context-grounding calculation unchanged.
  - Keep old grounding object for compatibility, but add `evidenceResolution` field to report.
- Recommendation caps:
  - Any mechanical hash mismatch, duplicate artifact ID, hash-without-content, or unresolvable pointer-only ref => cap at `reconsider` or stricter.
  - Missing refs / no evidence refs on load-bearing grounds => cap at `proceed_with_caveats` or `reconsider` depending severity.
  - Advisory fuzzy support and advisory contradiction flags must not cap recommendations by themselves.
- Keep `operatorReviewRequired=True` always.

### Task 5: Update eval/demo fixtures and artifact sanitization

**Objective:** Prove the v2 behavior with curated examples and prevent raw evidence leakage.

**Files:**
- Modify or create: `evaluation_cases/curated/smoke.jsonl` or add a small `evaluation_cases/curated/tech_v2_smoke.jsonl` if loader supports it; if not, keep v2 tests under `tests/` and document deferred eval-suite loader expansion.
- Modify: `src/elenchus_core/eval_suite.py`
- Test: `tests/test_eval_suite_runner.py` or new focused test.

**TDD RED:** Add a test that sanitized outcome contains evidence-resolution status/summary but not raw artifact `content` or sentinel strings such as `CTX_SENTINEL_DO_NOT_LEAK`.

**Implementation notes:**
- If extending eval-suite input discovery is small, load `*_smoke.jsonl` or specifically `tech_v2_smoke.jsonl`; otherwise keep only test fixtures and document why curated eval data remains on old loader.
- Sanitized output may include artifact IDs, statuses, counts, score, and method trust only.

### Task 6: Documentation update

**Objective:** Make the public product framing match the implementation.

**Files:**
- Modify: `README.md`
- Create: `docs/specs/2026-06-01-evidence-resolving-explanation-auditor-v2.md`
- Create: `docs/verification/2026-06-01-evidence-auditor-v2-plan-review.md`
- Create later: `docs/verification/2026-06-01-evidence-auditor-v2-implementation-verification.md`

**TDD/verification:** Documentation-only, but run `git diff --check` and scans for overclaiming phrases.

**Required wording:**
- “task-local evidence-resolving explanation-quality auditor”
- “public structured rationale”
- “advisory signal only”
- “counterfactual probing not run unless an operational-agent re-execution contract is supplied”
- “does not judge action correctness, objective truth, hidden CoT, or production allow/deny readiness”

### Task 7: Independent implementation review and fix loop

**Objective:** Use Opus and Grok after implementation to attack correctness, overclaiming, missing tests, and gaming surfaces.

**Files:**
- Create/update: `docs/verification/2026-06-01-evidence-auditor-v2-implementation-verification.md`

**Steps:**
1. Run all quality gates.
2. Build a review bundle from `git diff --stat`, `git diff --check`, relevant diffs, tests, and result artifacts.
3. Ask Opus for read-only adversarial implementation review.
4. Ask Grok for read-only adversarial implementation review.
5. Classify findings as confirmed/refuted/deferred.
6. For each confirmed blocker, write failing regression test first, fix, rerun targeted tests and full gates.
7. Re-review focused blocker fixes if either reviewer found high/critical issues.

---

## Verification commands

```bash
uv run ruff check .
uv run mypy
uv run pytest -q
uv run python scripts/run_eval_suite.py evaluation_cases/curated benchmark-output/eval-suite-v2
python3 - <<'PY'
from pathlib import Path
for path in Path('benchmark-output/eval-suite-v2').glob('*'):
    text = path.read_text(errors='ignore')
    assert 'CTX_SENTINEL_DO_NOT_LEAK' not in text, path
print('sentinel scan passed')
PY
git diff --check
```

## Review-gate prompt requirements

Ask reviewers to return:
- Verdict: `ACCEPT`, `ACCEPT_WITH_CHANGES`, or `REJECT`
- Blocking issues before implementation/finalization
- Overclaiming/product-semantics risks
- Missing tests
- Simpler architecture recommendations
- Any ways the implementation still rewards eloquence over resolved evidence
- Any evidence-leakage/privacy risks

## Expected final state

- Elenchus remains internal-alpha/advisory.
- Legacy behavior is preserved.
- New structured evidence-backed requests get a richer, more honest report.
- Unsupported or fabricated evidence is visibly penalized.
- Broad tech domains are represented through thin lenses rather than stale monolithic packs.
- Counterfactual probing is honestly marked as not yet measured instead of simulated.
