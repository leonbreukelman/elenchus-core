# Tech-Wide Lens Expansion Implementation Plan

Issue: https://github.com/leonbreukelman/elenchus-core/issues/3
Spec: `docs/specs/2026-06-02-tech-wide-lens-expansion.md`
Spec review: `docs/verification/2026-06-02-tech-wide-lens-spec-opus-review.md`
Date: 2026-06-02
Status: Opus reviewed; required changes incorporated; ready for implementation

> For Hermes: Use `disciplined-project-delivery` and strict `test-driven-development`. This is a session-sized vertical slice for deterministic Python code only. Write failing tests first, verify RED, implement minimal GREEN, then run targeted and full gates.

## Review status

Plan Opus review verdict: `ACCEPT_WITH_CHANGES`.

Review artifact: `docs/verification/2026-06-02-tech-wide-lens-plan-opus-review.md`.

Changes incorporated after review:

- Fixed the verification overclaiming scan so it targets product-facing positive claims rather than failing on negative examples inside the spec/plan.
- Confirmed `createdAt` is the current report's time-varying field and limited SRE report regression normalization to that field only.
- Changed the secret scan to inspect the full diff against `HEAD`, covering staged and unstaged changes.
- Made lens-isolation tests delta-based rather than absolute-zero assertions.
- Added missing tests for all multi-word markers, `change_governance`, `tune_flywheel`, the generalization/local-patch/invariant family, `page_human` reachability, and the combined non-tech-domain mapping/no-tech-boost case.
- Defined deterministic IDs/rationale text for injected mapped alternatives.
- Simplified the term-profile plan to start with a small derived helper, adding a dataclass/module only if tests justify it.

## Goal

Expand the actual built-in `tech` lens so broad technical/product-strategy proposals are first-class in Elenchus Core:

- architecture choices/revisions;
- design proposals/revisions;
- process and methodology changes;
- mechanism/flywheel explanations;
- governance/tradeoff proposals;
- invariant-check and generalization-vs-local-patch decisions.

The feature improves the advisory hard-to-vary public-rationale signal, not technical truth or optimality. Elenchus remains `uncalibrated_internal_alpha`, deterministic-only, and operator-review-required.

## Non-goals / safety boundaries

- Do not make Elenchus an architecture oracle, design judge, optimality judge, action-correctness judge, truth oracle, hidden-CoT detector, production allow/deny gate, or calibrated system.
- Do not call live paid LLM providers from production code.
- Do not add sidecar/MCP/platform integration.
- Do not require external corpora or internet fact checking.
- Do not make artifact type vocabulary a hard validation gate.
- Do not break SRE legacy special-casing or current non-tech lens behavior.
- Do not let broad tech terms leak into SRE/cloud/security/software/AI-ML scoring unless `tech` is explicitly selected by `domain` or `domainHints`.

## Current implementation seams

Current code facts relevant to this feature:

- `src/elenchus_core/lenses.py`
  - `DomainLens` already has `action_types`, `action_synonyms`, `artifact_types`, `risk_predicates`, `evidence_markers`, and `perturbation_templates`.
  - `LENSES["tech"]` is currently thin: `investigate_more`, `page_human`, `no_action`; artifacts `log`, `metric`, `ticket`, `diff`; markers `log`, `metric`, `artifact`, `ticket`.
  - `selected_lenses(request)` already preserves deterministic request-domain, deduped hints, generic fallback order.
- `src/elenchus_core/actions.py`
  - `action_terms(action_type, lenses=None)` can merge lens synonyms but current callers do not consistently pass selected lenses.
  - `generate_near_neighbor_alternatives()` currently uses candidates from `availableActions` plus selected lens actions and truncates to five.
  - Plain SRE requests with no hints and no `availableActions` use `SRE_ACTION_TYPES` legacy ordering.
- `src/elenchus_core/toulmin.py`
  - `score_specificity()` uses global regexes and `action_terms(action.type)` without selected lenses.
  - Domain/evidence regexes are SRE-oriented and are not lens-gated.
- `src/elenchus_core/providers.py`
  - `_term_support()` and `assess_support()` call `action_terms()` / `score_specificity()` without selected lenses.
- `src/elenchus_core/evaluator.py`
  - `action_coupling()` calls `action_terms()` without selected lenses.
  - `evaluate_request()` calls `extract_toulmin_argument()` before generating alternatives/support.
- `src/elenchus_core/report.py`
  - Product semantics already preserve advisory-only wording and should remain conservative.
- `tests/test_domain_lenses.py`
  - Existing tests protect selected-lens ordering, unknown fallback, SRE legacy action terms, and legacy SRE alternative order.

## Acceptance criteria

1. `LENSES["tech"]` includes first-class action types and vocabulary from the spec for architecture/design/process/methodology/flywheel/mechanism/governance/tradeoff/invariant/generalization proposals.
2. `LENSES["tech"]` includes the spec artifact and evidence-marker vocabulary, but these remain advisory hints and do not reject custom artifact types.
3. `selected_lenses()` ordering stays request domain, deduped hints, then `generic` fallback.
4. Known broad tech action types receive explicit deterministic mapped near-neighbor alternatives before generic fillers.
5. Mapped alternatives survive the five-alternative cap, are deduped, and exclude the proposed action.
6. Known broad tech actions submitted under a non-tech domain still receive explicit mapped alternatives; tech scoring terms remain lens-gated and conservative.
7. Unknown/custom actions keep the safe generic fallback and do not crash.
8. SRE legacy action terms and plain-SRE near-neighbor order remain stable.
9. A plain SRE regression request produces byte-identical deterministic report output before and after the implementation after normalizing only `createdAt`, which is currently generated by `report._now()`. Do not normalize scores, alternatives, findings, readiness, support, or product semantics.
10. Existing security/cloud/software/AI-ML behavior remains stable enough for existing tests to pass unchanged.
11. Tech markers/synonyms affect evaluator-level specificity/action-coupling/support only when `tech` is selected.
12. Multi-word and hyphenated markers are detected: `feedback loop`, `second-order effect` / `second order effect`, `decision rights`, `fail closed` / `fail-closed`, `local patch` / `local-patch`.
13. Vague polished rationales that repeat generic words do not earn high action coupling merely from over-generic synonyms.
14. Report/README wording remains advisory: it describes evaluating rationale specificity for the proposed action, not recommending the objectively right engineering choice.
15. Quality gates pass:
    - targeted tests for the changed files;
    - `uv run pytest -q`;
    - `uv run ruff check .`;
    - `uv run mypy`;
    - `uv run python scripts/run_eval_suite.py evaluation_cases/curated benchmark-output/eval-suite`;
    - `git diff --check`;
    - a simple secret/overclaiming scan over changed files.

## Architecture decisions

1. Use a module-level action-keyed map in `src/elenchus_core/actions.py`, not a `DomainLens.near_neighbors` field.
   - Reason: near-neighbor semantics are keyed by proposed action type and may need to work even when the request accidentally uses a non-tech domain.

2. Add a request-level derived term helper rather than mutating global regexes.
   - Preferred first shape: small functions in `src/elenchus_core/lenses.py` or `src/elenchus_core/toulmin.py`, for example `selected_lens_terms(request)` and `count_lens_terms(text, terms)`.
   - Add a frozen dataclass or a new `src/elenchus_core/terms.py` module only if tests show the tuple/dict helper becomes noisy or hard to thread.
   - The helper must derive tech terms only from `selected_lenses(request)`, so non-tech requests do not receive tech marker scoring.

3. Keep existing SRE behavior by default.
   - `action_terms(action_type)` without lenses must continue returning the legacy sorted terms for current SRE tests.
   - Plain SRE near-neighbor generation must continue using `SRE_ACTION_TYPES` legacy ordering.

4. Prefer explicit phrase matching over broad single-token global regexes.
   - Add a small utility such as `term_hit_count(text, terms)` that uses boundary-aware matching and normalizes spaces/hyphens for multi-word terms.
   - Reuse `affirmed_term_count()` where negation handling matters; extend only if tests force it.

5. Avoid brittle absolute score assertions where possible.
   - Use relative assertions: specific evidence-resolving tech rationale scores higher than vague polished rationale; tech-selected request has more tech marker/action hits than identical non-tech request; generic synonym stuffing stays below a conservative threshold.

## Implementation tasks

### Task 0: Baseline and fixtures

Objective: Capture current stable behavior before changing production code.

Files:
- Test: `tests/test_tech_wide_lens.py` or split between `tests/test_domain_lenses.py`, `tests/test_toulmin.py`, and `tests/test_evaluator.py` if that keeps scope clearer.
- Possibly add helper fixtures inside the test file only.

TDD RED / characterization:
1. Add one reusable plain SRE legacy report fixture/helper around `evaluate_request()` that serializes the report with only `createdAt` normalized. This may pass immediately as characterization; keep it as regression protection before changing scoring and reuse the same helper in later scoring tests rather than creating a second near-identical assertion.
2. Add helper builders for:
   - architecture/design tech request with ADR/design evidence;
   - methodology/process tech request;
   - flywheel/mechanism tech request;
   - generic-domain request with proposed action `choose_architecture`;
   - vague polished rationale using common generic words.

Verification:
- Run targeted characterization test:
  - `uv run pytest tests/test_tech_wide_lens.py::test_plain_sre_report_shape_remains_stable -q`
- If it fails due to `createdAt`, normalize only `createdAt` and rerun until it is a legitimate characterization test. If any other field differs before production changes, investigate instead of broadening normalization.

### Task 1: RED tests for expanded tech lens data and selected-lens isolation

Objective: Prove current `tech` lens is too thin before modifying `LENSES`.

Files:
- Test: `tests/test_tech_wide_lens.py` or `tests/test_domain_lenses.py`
- Later modify: `src/elenchus_core/lenses.py`

TDD RED tests:
1. `test_tech_lens_contains_broad_proposal_actions()` asserts the action types from the spec are present.
2. `test_tech_lens_contains_broad_artifacts_and_markers()` asserts ADR/design/process/mechanism/flywheel/tradeoff artifacts and markers exist.
3. `test_selected_lenses_still_domain_hints_generic_order()` extends the existing ordering test, if needed, with `tech` in hints and duplicate hints.
4. `test_custom_artifact_type_still_resolves_when_not_in_lens()` verifies artifact types remain hints, not validation gates. If existing evidence tests already cover this, link to that test rather than duplicating heavily.

Expected RED:
- The new tech action/artifact/marker assertions fail against the current thin lens.

GREEN implementation:
- Expand `LENSES["tech"]` in `src/elenchus_core/lenses.py`.
- Add discriminative `action_synonyms` from the spec.
- Avoid high-frequency single-word synonyms unless they are normalized action-name parts or phrase-bound.
- Consider version bump for tech lens, e.g. `2026-06-02.1`.

Verification:
- `uv run pytest tests/test_tech_wide_lens.py -q` or the exact targeted tests.

### Task 2: RED tests for explicit near-neighbor mapping

Objective: Make broad tech proposal alternatives meaningful and deterministic.

Files:
- Test: `tests/test_tech_wide_lens.py`
- Modify: `src/elenchus_core/actions.py`

TDD RED tests:
1. `test_choose_architecture_gets_mapped_neighbors_before_fillers()`:
   - Request domain `tech`, proposed `choose_architecture`, many distracting `availableActions`.
   - Assert first alternatives include `revise_architecture`, `select_tradeoff`, `investigate_more`, `no_action` before generic/distractor fillers.
2. `test_change_governance_and_tune_flywheel_get_required_mapped_neighbors()`:
   - Assert `change_governance` maps through `change_process`, `select_tradeoff`, `page_human`, `no_action`.
   - Assert `tune_flywheel` maps through `define_mechanism`, `change_process`, `select_tradeoff`, `investigate_more`.
3. `test_generalization_local_patch_invariant_family_gets_mapped_neighbors()`:
   - Assert `generalize_solution`, `reject_local_patch`, and `add_invariant_check` each produce the spec's mapped alternatives.
4. `test_page_human_remains_reachable_for_tech_proposals()`:
   - Assert at least one tech proposal path still includes `page_human`, either via explicit map (`change_governance`) or generic fallback filler.
5. `test_mapped_neighbors_are_deduped_exclude_original_and_survive_five_cap()`:
   - Include duplicates in `availableActions`, include proposed action in available actions, and extra fillers.
   - Assert no proposed action in alternatives, no duplicates, max length five, mapped neighbors still present.
6. `test_known_broad_action_under_generic_domain_gets_mapping_but_not_tech_scoring()`:
   - Domain `generic`, proposed `choose_architecture`.
   - Assert mapped alternatives appear.
   - Assert, in the same case, that tech lens marker/synonym boost is absent; the same rationale under `domain="tech"` should produce strictly higher tech-term feature/support counts.
7. `test_unknown_action_keeps_generic_fallback()`:
   - Existing unknown test should continue to pass; add a no-regression assertion if needed.
8. `test_sre_legacy_near_neighbor_order_unchanged()`:
   - Existing test remains; run it after mapping implementation.

Expected RED:
- Broad action tests fail because alternatives are generic/fallback only.

GREEN implementation:
- Add `NEAR_NEIGHBORS_BY_ACTION: dict[str, tuple[str, ...]]` in `actions.py`.
- Update `generate_near_neighbor_alternatives()`:
  1. normalize proposed action;
  2. collect explicit mapped neighbors first if present;
  3. append `_candidate_action_types(request)` fillers;
  4. dedupe, exclude original, cap at five;
  5. preserve the existing `AlternativeAction` ID shape `alt-{index}-{candidate}` after final ordering; injected neighbors use the same deterministic rationale text as other generated alternatives: `A near-neighbor alternative would {candidate words} instead of {original words}.`;
  6. do not alter `_candidate_action_types()` SRE legacy branch.

Verification:
- `uv run pytest tests/test_domain_lenses.py tests/test_tech_wide_lens.py -q`

### Task 3: RED tests for lens-gated term profile and phrase matching

Objective: Make tech vocabulary affect scoring only when the tech lens is selected.

Files:
- Test: `tests/test_tech_wide_lens.py`, optionally `tests/test_toulmin.py`
- Modify/create: `src/elenchus_core/lenses.py` or `src/elenchus_core/terms.py`
- Modify: `src/elenchus_core/actions.py`
- Modify: `src/elenchus_core/toulmin.py`

TDD RED tests:
1. `test_term_profile_includes_tech_terms_only_when_tech_selected()`:
   - Same rationale text containing `feedback loop`, `coupling`, `tradeoff`, and `decision rights`.
   - Request A: domain `tech`.
   - Request B: domain `generic` with no `tech` hint.
   - Assert the term profile / specificity feature counts differ only for tech-selected request.
2. `test_multi_word_and_hyphen_markers_are_detected()`:
   - Rationale contains all phrase variants from the spec: `feedback loop`, `second-order effect`, `second order effect`, `leading indicator`, `lagging indicator`, `decision rights`, `blast radius`, `fail-closed`, `fail closed`, `local-patch`, and `local patch`.
   - Assert `evidenceMarkers` or equivalent feature count reflects those markers for tech request.
3. `test_lens_isolation_for_sre_cloud_software_ai_ml_overlap_words()`:
   - Requests in non-tech domains mention `constraint`, `coupling`, `dependency`, and `tradeoff`.
   - Use delta assertions: compare each request without `tech` hint to the same request with `domainHints=["tech"]`. The tech-hinted version may gain tech marker/support counts; the no-tech version must match that domain's own baseline and must not gain the tech-only delta.
4. `test_sre_action_terms_without_lenses_remain_legacy_sorted()`:
   - Existing test should still pass.

Expected RED:
- Current `score_specificity()` has no selected-lens profile and misses phrase-specific tech markers.

GREEN implementation:
- Add a small request-derived term helper, for example:
  - `selected_lens_terms(request) -> tuple[str, ...]` for marker/domain terms;
  - `count_lens_terms(text, terms) -> int` for phrase/hyphen-aware matching.
- If threading raw tuples becomes unclear, promote this helper to a frozen `RequestTermProfile` dataclass; do not start with extra structure unless tests justify it.
- Include selected lens names only if needed for debugging/tests.
- Keep no-profile/default path identical to current SRE behavior.
- Do not add tech terms to global `DOMAIN_RE` / `EVIDENCE_RE`.
- Update or wrap `score_specificity()` to accept optional selected-lens terms/profile:
  - `score_specificity(rationale, action, term_profile: RequestTermProfile | None = None)` or a simpler optional tuple.
- Update `extract_toulmin_argument()` to accept the same optional profile/terms.

Verification:
- `uv run pytest tests/test_tech_wide_lens.py -q`
- `uv run pytest tests/test_domain_lenses.py -q`

### Task 4: RED tests for evaluator-level lens-aware scoring and anti-gaming

Objective: Ensure tech vocabulary is not metadata-only and does not reward generic eloquence.

Files:
- Test: `tests/test_tech_wide_lens.py` or `tests/test_evaluator_v2.py`
- Modify: `src/elenchus_core/evaluator.py`
- Modify: `src/elenchus_core/providers.py`
- Modify: `src/elenchus_core/toulmin.py`

TDD RED tests:
1. `test_tech_specific_evidence_resolving_rationale_scores_above_vague_polished_rationale()`:
   - Same proposed action `choose_architecture` or `define_mechanism`.
   - Rationale A names constraints/mechanism/alternative/evidence refs and resolves against task-local evidence.
   - Rationale B is polished but generic and repeats broad words.
   - Assert A has stronger structural evidence than B (resolved evidence refs, discriminative tech-term hits, and at least one of `rationaleSpecificity`, `actionCoupling`, or `alternativeResistance` higher by a documented margin). Do not rely only on aggregate `overallSignal`.
2. `test_tech_markers_do_not_affect_generic_domain_action_coupling()`:
   - Domain generic with broad tech action receives mapped alternatives but not tech marker/synonym scoring boost.
3. `test_synonym_collision_keeps_discrimination_between_mechanism_invariant_generalization()`:
   - Compare `define_mechanism`, `add_invariant_check`, `generalize_solution` requests with rationale terms specific to only one action family.
   - Assert the intended action gets higher term support/coupling than the near-collision action.
4. `test_report_wording_does_not_claim_architecture_correctness()`:
   - Evaluate `generalize_solution` or `select_tradeoff` request.
   - Assert `productSemantics` still includes advisory-only / does-not-judge wording and does not contain forbidden positive overclaiming phrases.
5. Reuse the Task 0 SRE report regression helper after scoring changes; do not maintain a second golden assertion.

Expected RED:
- Current scoring callers ignore selected lenses, so tech-specific scoring improvements are absent or weak.

GREEN implementation:
- In `evaluate_request()` compute selected lens terms once near the top:
  - start with `lens_terms = selected_lens_terms(request)` or equivalent;
  - promote to `term_profile = term_profile_for_request(request)` only if the tuple form becomes unclear.
- Thread it through:
  - `extract_toulmin_argument(request.rationale, request.proposedAction, term_profile=term_profile_or_terms)`
  - `assess_support(request, alternatives, term_profile=term_profile_or_terms)`
  - `action_coupling(request, term_profile=term_profile_or_terms)`
- Update `action_coupling()` to call `action_terms(..., selected_lenses(request))` or use `term_profile`.
- Update `providers._term_support()` and `assess_support()` to accept optional selected lenses/term profile.
- Preserve default signatures where possible with optional parameters to reduce churn.
- Keep support notes and method trust unchanged; do not imply calibration.

Verification:
- `uv run pytest tests/test_tech_wide_lens.py tests/test_evaluator.py tests/test_evaluator_v2.py -q`

### Task 5: Documentation wording update, only if needed

Objective: Keep public docs aligned without overclaiming.

Files:
- Modify: `README.md` only if current README does not mention the expanded tech lens accurately after implementation.
- Possibly add/update a short implementation verification doc later: `docs/verification/2026-06-02-tech-wide-lens-implementation.md`.

TDD/verification:
- If README changes, add or extend a test/manual scan that forbids phrases like:
  - `validates architectures`
  - `determines optimal designs`
  - `proves the correct architecture`
  - `production gate`
- Required safe wording:
  - `hard-to-vary`
  - `advisory signal only`
  - `uncalibrated_internal_alpha`
  - `operator review`
  - `tech lens` with architecture/design/process/flywheel/mechanism vocabulary hints.

Verification:
- `git diff --check`
- simple grep scan for forbidden overclaiming phrases.

### Task 6: Curated eval-suite verification and drift review

Objective: Ensure implementation does not silently break intended-use evaluation cases.

Files:
- Existing: `evaluation_cases/curated/`
- Existing: `scripts/run_eval_suite.py`
- Optional future work only: add curated tech-wide paired cases in a follow-up if this slice gets large.

Steps:
1. Run:
   - `uv run python scripts/run_eval_suite.py evaluation_cases/curated benchmark-output/eval-suite`
2. Inspect failures, if any:
   - If failures reveal a regression, fix implementation with a failing test first.
   - If failures reflect a legitimate expectation update, document why before updating any fixture.
3. Do not commit generated `benchmark-output` artifacts unless repo convention says otherwise; current plan treats them as ignored verification output.

## Full verification sequence

Run these before declaring implementation complete:

```bash
uv run pytest tests/test_tech_wide_lens.py -q
uv run pytest tests/test_domain_lenses.py tests/test_evaluator.py tests/test_evaluator_v2.py -q
uv run pytest -q
uv run ruff check .
uv run mypy
uv run python scripts/run_eval_suite.py evaluation_cases/curated benchmark-output/eval-suite
git diff --check
python3 - <<'PY'
import math
import re
import subprocess
import sys

diff = subprocess.check_output(['git', 'diff', '--unified=0', 'HEAD'], text=True, errors='replace')
sensitive_assignment_re = re.compile(
    r"(?i)(api[_-]?key|anthropic[_-]?api[_-]?key|xai[_-]?api[_-]?key|password|secret|token)"
    r"\s*[:=]\s*['\"]?([A-Za-z0-9_./:+-]{20,})['\"]?"
)

def entropy(value: str) -> float:
    counts = {ch: value.count(ch) for ch in set(value)}
    total = len(value)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())

hits = []
for line in diff.splitlines():
    if not line.startswith('+') or line.startswith('+++'):
        continue
    match = sensitive_assignment_re.search(line)
    if match and entropy(match.group(2)) >= 3.0:
        hits.append(line)
if hits:
    print('possible high-entropy credential assignments in added lines:', file=sys.stderr)
    for hit in hits:
        print(hit[:220], file=sys.stderr)
    raise SystemExit(1)
print('simple added-line credential scan passed')
PY
python3 - <<'PY'
from pathlib import Path
# Scan only product-facing docs/report text, not spec/plan negative examples or tests that quote forbidden phrases.
product_paths = [Path('README.md'), Path('src/elenchus_core/report.py')]
for path in product_paths:
    text = path.read_text(errors='ignore').lower()
    forbidden_positive_claims = [
        'validates architectures',
        'determines optimal designs',
        'proves the correct architecture',
        'is a production gate',
        'can be used as a production gate',
        'production-ready allow/deny',
    ]
    for phrase in forbidden_positive_claims:
        assert phrase not in text, f'{path}: forbidden positive overclaiming phrase {phrase!r}'
print('product-facing overclaiming scan passed')
PY
```

## Implementation review loop

After implementation and local gates:

1. Build an implementation review bundle containing:
   - spec and plan paths;
   - `git diff --stat`;
   - relevant diffs for `lenses.py`, `actions.py`, `toulmin.py`, `providers.py`, `evaluator.py`, tests, and README if changed;
   - verification command outputs.
2. Ask Opus for read-only adversarial implementation review.
3. Classify findings as confirmed / refuted / deferred.
4. For confirmed blockers, add a failing regression test first, then fix.
5. Re-run targeted and full gates.
6. Re-review if Opus found any critical/high issue.

## Expected final state

- Broad tech actions get meaningful alternatives instead of generic operational fallbacks.
- Tech-specific rationale terms and phrase markers influence evaluator-level advisory scores only when `tech` is selected.
- Known broad tech actions still get mapped alternatives under accidental non-tech domains, but without tech scoring boost.
- Existing SRE/security/cloud/software/AI-ML behavior remains stable.
- Report and README language remain conservative and advisory-only.
- No live provider calls or new dependencies are needed.

## Known risks / mitigations

- Risk: tech terms leak into other domains.
  - Mitigation: request-level term profile plus lens-isolation tests.
- Risk: multi-word terms silently do not match.
  - Mitigation: phrase/hyphen marker tests.
- Risk: `availableActions` semantics become confusing when mapped neighbors are injected.
  - Mitigation: document that this feature preserves current non-authoritative available-action behavior; stricter semantics are deferred.
- Risk: SRE byte-identical regression is brittle due to timestamps.
  - Mitigation: normalize `createdAt` and any intentionally dynamic fields only; do not normalize scores/alternatives/readiness.
- Risk: action synonym overlap inflates support.
  - Mitigation: prune generic synonyms and add vague-polished and synonym-collision tests.

## Blockers before implementation

No implementation blocker remains after incorporating the Opus plan-review findings. The only blocker Opus identified was an impossible overclaiming-scan gate; the plan now scopes that scan to product-facing positive claims rather than spec/plan negative examples.

Non-blocking decisions already made by the spec and plan:

- Mapped near-neighbor actions are injected before fillers and are not restricted to `availableActions`.
- Tech scoring terms are lens-gated.
- `page_human` can come from generic fallback unless implementation needs it directly in `tech`.
- Curated eval outputs are verification artifacts; fixture expectation changes require explicit rationale, not silent rebaseline.
