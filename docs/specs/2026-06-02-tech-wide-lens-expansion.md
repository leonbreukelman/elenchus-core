# Tech-Wide Lens Expansion Specification

Issue: https://github.com/leonbreukelman/elenchus-core/issues/3
Date: 2026-06-02
Status: Opus reviewed; required changes incorporated; ready for implementation planning

## Review status

Initial Opus review verdict: `ACCEPT_WITH_CHANGES`.

Review artifact: `docs/verification/2026-06-02-tech-wide-lens-spec-opus-review.md`.

Changes incorporated after review:

- Pinned lens-gated term/marker behavior so tech vocabulary cannot silently affect SRE/cloud/software/security/AI-ML scoring unless the tech lens is selected.
- Resolved near-neighbor behavior: explicit broad-action mappings are injected and ordered before generic fillers; they survive the five-alternative cap; unknown actions still use the existing fallback.
- Specified fallback behavior for a known broad tech action submitted under a non-tech domain.
- Required phrase/hyphen-aware marker matching for multi-word terms such as `feedback loop`, `second-order effect`, `decision rights`, `fail closed`, and `local patch`.
- Pruned/guarded over-generic synonyms so common words do not inflate action coupling.
- Clarified curated eval-suite expectations: generated outputs may change, but suite assertions must pass; no golden-output rebaseline is part of this feature.
- Added determinism, lens-isolation, synonym-collision, truncation-priority, and report-wording tests.

## Goal

Make the built-in `tech` lens first-class for broad technical/product-strategy proposals: architecture choices, design revisions, operating processes, methodologies, flywheels, mechanisms, governance/tradeoff decisions, and generalization-vs-local-patch choices.

The feature must improve Elenchus's advisory hard-to-vary public-rationale signal for Build Arena-style and tech-wide workflows without changing the product boundary: Elenchus remains an `uncalibrated_internal_alpha` explanation-quality signal requiring operator review. It must not become a truth oracle, architecture-correctness judge, optimality judge, hidden chain-of-thought detector, production allow/deny gate, or internet-scale fact checker.

## Current state confirmed

Current code facts from the repository:

- `src/elenchus_core/lenses.py` defines `LENSES["tech"]` with only:
  - `action_types=("investigate_more", "page_human", "no_action")`
  - `artifact_types=("log", "metric", "ticket", "diff")`
  - `evidence_markers=("log", "metric", "artifact", "ticket")`
- `selected_lenses(request)` already preserves deterministic ordering: request domain first, then deduped `domainHints`, then `generic` fallback.
- `src/elenchus_core/actions.py` generates alternatives from `availableActions` plus selected lens action types, with SRE legacy special-casing preserved for plain SRE requests.
- `generate_near_neighbor_alternatives()` currently truncates ordered candidates to five; it has no explicit semantic mapping for broad tech proposal types.
- `action_terms(action_type, lenses=None)` can consume lens-specific `action_synonyms`, but some scoring paths currently call it without selected lenses.
- `src/elenchus_core/toulmin.py` has hard-coded domain/evidence regexes biased toward SRE/operations terms.
- Evidence artifact `type` is accepted as free text; lens artifact types are metadata/hints, not validation requirements.

## Product framing

Elenchus evaluates whether a public rationale appears specific, contrastive, evidence-resolving, and hard to vary for a proposed typed action/proposal against near-neighbor alternatives.

For broad tech proposals, the proposed action may be an architecture, design, process, methodology, mechanism, flywheel, or generalization decision. The output must still be framed as advisory signal only:

- It can say the rationale is more or less specific to `choose_architecture` than to `investigate_more` or `select_tradeoff`.
- It can say load-bearing grounds cite task-local evidence that mechanically resolves.
- It can say the rationale names constraints, mechanisms, alternatives, uncertainty, and change conditions.
- It cannot say the architecture/design/process is objectively correct, optimal, or proven true.

## Target behavior

### 1. Expanded tech lens vocabulary

`LENSES["tech"]` should include first-class broad proposal action types:

- `choose_architecture`
- `revise_architecture`
- `propose_design`
- `revise_design`
- `adopt_methodology`
- `change_process`
- `define_mechanism`
- `tune_flywheel`
- `change_governance`
- `select_tradeoff`
- `add_invariant_check`
- `generalize_solution`
- `reject_local_patch`
- `investigate_more`
- `no_action`

`page_human` should remain available through the existing `generic` fallback and may also remain in `tech` if implementation prefers explicit escalation in all technical lenses. Tests should assert the mapped alternatives for broad action types, not the full raw lens order.

### 2. Tech action synonyms

The tech lens should provide action synonyms/term hints for broad proposals. Terms should be discriminative enough to support contrastive scoring. Avoid high-frequency single-word synonyms such as `decision`, `design`, `process`, `review`, `owner`, `cost`, `risk`, `quality`, `policy`, and `service` unless they appear as part of a more specific phrase or are already part of the normalized action name.

Minimum expected synonym families:

- `choose_architecture`: architecture decision record, adr, topology, service boundary, modularity, interface boundary, coupling
- `revise_architecture`: architecture revision, architecture refactor, boundary change, dependency inversion, coupling reduction, migration path
- `propose_design`: design proposal, interaction model, interface contract, component model, user flow
- `revise_design`: design revision, usability iteration, state flow, affordance change, interaction fix
- `adopt_methodology`: methodology adoption, practice cadence, review ritual, retro cadence, workflow discipline
- `change_process`: process change, handoff, queue, approval path, bottleneck, operating workflow
- `define_mechanism`: mechanism, causal loop, trigger, invariant, operating lever, policy mechanism
- `tune_flywheel`: flywheel, feedback loop, compounding loop, adoption loop, retention loop, leading indicator
- `change_governance`: governance model, decision rights, escalation path, authority boundary, approval model
- `select_tradeoff`: tradeoff, constraint, optimization target, accepted risk, reversibility, blast radius
- `add_invariant_check`: invariant check, guardrail, validation check, assertion, fail closed
- `generalize_solution`: generalization, reusable pattern, invariant-preserving abstraction, transfer scenario, generalized solution
- `reject_local_patch`: local patch, narrow fix, special case, brittle workaround, patch rejection

These terms are heuristic scoring support only. They must not be treated as proof of correctness.

### 3. Tech artifact/evidence vocabulary

`LENSES["tech"].artifact_types` should include at least:

- `architecture_decision_record`
- `design_doc`
- `process_map`
- `methodology_note`
- `mechanism_model`
- `flywheel_model`
- `strategy_memo`
- `spec`
- `constraint_list`
- `tradeoff_matrix`
- `incident_review`
- `metric_snapshot`
- `user_feedback`
- `diff`
- `test_log`
- `eval_report`

Artifact types should remain hints. The evaluator must not reject or down-rank custom artifact types solely because they are not listed in the lens.

### 4. Tech evidence markers / mechanism terms

The tech lens should include first-class evidence/mechanism markers for specificity heuristics and diagnostics:

- invariant
- constraint
- mechanism
- feedback loop
- bottleneck
- tradeoff
- assumption
- failure mode
- counterexample
- leading indicator
- lagging indicator
- second-order effect
- coupling
- dependency
- reversibility
- blast radius
- adoption friction

Implementation must consume these only through a lens-gated request term profile:

- Tech-specific markers contribute to `domainTerms` / `evidenceMarkers` only when `tech` is in `selected_lenses(request)`.
- Plain SRE requests with no `domainHints` must remain byte-identical to the current report output for the legacy SRE regression fixture.
- Cloud/security/software/AI-ML requests that happen to mention overlapping words such as `constraint`, `coupling`, `dependency`, or `tradeoff` must not receive tech-specific scoring unless `tech` is selected through `domain` or `domainHints`.

Phrase matching must handle multi-word and hyphenated variants. The matcher should recognize equivalent separator variants where reasonable, for example:

- `feedback loop`
- `second-order effect` / `second order effect`
- `leading indicator`
- `lagging indicator`
- `decision rights`
- `blast radius`
- `fail closed` / `fail-closed`
- `local patch` / `local-patch`

The method-trust caveat remains unchanged: this is a deterministic linguistic proxy, not a truth score.

### 5. Deterministic near-neighbor mapping

New broad tech actions should have deterministic, semantically meaningful near-neighbor alternatives instead of relying only on lens list order.

Add a module-level action-keyed mapping in `src/elenchus_core/actions.py`, for example `NEAR_NEIGHBORS_BY_ACTION`. Do not put this mapping on `DomainLens` unless implementation finds a clear reason; near-neighbor semantics are keyed by action type, not only by domain.

Minimum mappings:

- `choose_architecture` -> `revise_architecture`, `select_tradeoff`, `investigate_more`, `no_action`
- `revise_architecture` -> `choose_architecture`, `select_tradeoff`, `investigate_more`, `no_action`
- `propose_design` -> `revise_design`, `select_tradeoff`, `investigate_more`, `no_action`
- `revise_design` -> `propose_design`, `select_tradeoff`, `investigate_more`, `no_action`
- `adopt_methodology` -> `change_process`, `define_mechanism`, `investigate_more`, `no_action`
- `change_process` -> `adopt_methodology`, `define_mechanism`, `investigate_more`, `no_action`
- `define_mechanism` -> `change_process`, `select_tradeoff`, `investigate_more`, `no_action`
- `tune_flywheel` -> `define_mechanism`, `change_process`, `select_tradeoff`, `investigate_more`
- `change_governance` -> `change_process`, `select_tradeoff`, `page_human`, `no_action`
- `select_tradeoff` -> `choose_architecture`, `revise_design`, `investigate_more`, `no_action`
- `add_invariant_check` -> `generalize_solution`, `reject_local_patch`, `investigate_more`, `no_action`
- `generalize_solution` -> `reject_local_patch`, `add_invariant_check`, `investigate_more`, `no_action`
- `reject_local_patch` -> `generalize_solution`, `add_invariant_check`, `investigate_more`, `no_action`

Generation rules:

1. Normalize the proposed action type.
2. If the normalized action is in the explicit mapping, inject mapped neighbors first, even if they are not present in `availableActions`.
3. Then append remaining candidates from the existing candidate pool (`availableActions`, selected lens actions, and generic fallback) as fillers.
4. Dedupe while preserving order.
5. Exclude the proposed action itself.
6. Keep the existing maximum of five alternatives.
7. Unknown/custom actions with no explicit mapping use the existing safe fallback behavior.

Known broad tech actions should get mapped alternatives even if the request accidentally uses `domain="generic"` or another non-tech domain. However, tech-specific marker/synonym scoring remains lens-gated; if the request does not select the tech lens, the alternatives can be mapped while scoring stays conservative.

### 6. Lens-aware scoring path

The implementation should make lens vocabulary actually affect evaluator behavior where appropriate:

- Add a request-level helper, for example `term_profile_for_request(request)`, that derives selected lens terms once and keeps lens-gating explicit.
- `action_coupling(request)` should use `action_terms(request.proposedAction.type, selected_lenses(request))` or the term profile equivalent.
- Provider/local support scoring should use selected lenses or the term profile when computing action term support for the proposed action and alternatives.
- Toulmin/specificity scoring should accept the request-level term profile so selected-lens domain/evidence markers contribute to `domainTerms`, `evidenceMarkers`, and `actionTerms` without mutating shared global regexes.
- Existing SRE legacy outputs must remain stable for plain SRE requests.

Do not add tech terms to a global regex that runs for all domains.

The scoring changes are still deterministic heuristics and must not raise method trust beyond current advisory wording.

### 7. Documentation

README/spec wording should remain conservative:

- Good: "tech lens includes architecture/design/process/flywheel/mechanism vocabulary hints for hard-to-vary rationale evaluation."
- Bad: "Elenchus validates architectures" or "Elenchus determines optimal designs."

A small README update is acceptable if the implemented scope list or examples need to mention the expanded tech lens. Do not add sidecar/MCP/provider-live claims.

## Acceptance criteria

1. `LENSES["tech"]` contains first-class action types for architecture, design, process/methodology, flywheel, mechanism, governance, tradeoff, invariant, and generalization-vs-local-patch proposals.
2. `LENSES["tech"]` contains artifact/evidence types for ADRs, design docs, process maps, mechanism/flywheel models, specs, constraints, tradeoff matrices, metrics, feedback, diffs, tests, and eval reports.
3. `selected_lenses()` ordering remains request domain, deduped domain hints, then `generic` fallback.
4. `generate_near_neighbor_alternatives()` returns meaningful deterministic alternatives for the new broad tech action types.
5. Mapped neighbors are injected before generic fillers, survive the five-alternative cap, are deduped, and exclude the proposed action itself.
6. A known broad tech action submitted under a non-tech domain still receives the explicit mapped alternatives while keeping tech scoring terms lens-gated.
7. Unknown/custom action types still safely produce fallback alternatives and do not crash.
8. Existing SRE legacy action terms and near-neighbor ordering remain stable.
9. A plain SRE regression request produces byte-identical report output before and after the implementation.
10. Existing security/cloud/software/AI-ML lens behavior remains stable enough that their existing tests pass unchanged.
11. Tech markers and synonyms influence evaluator-level behavior only when the tech lens is selected, not only lens metadata inspection.
12. Multi-word and hyphenated tech markers are detected.
13. Vague polished rationales that repeat generic words do not earn high action coupling merely from over-generic synonyms.
14. Report/readme wording remains advisory: evaluated proposal/rationale specificity only, not Elenchus recommending the objectively right engineering choice.
15. Tests cover at least:
    - architecture/design proposal with task-local ADR/design evidence;
    - methodology/process proposal with meaningful alternatives;
    - flywheel/mechanism proposal with mechanism and feedback-loop terms;
    - generalization-vs-local-patch proposal;
    - unknown action safe fallback;
    - mapped-neighbor truncation with extra `availableActions`;
    - tech action under non-tech domain fallback;
    - SRE byte-identical report regression;
    - lens isolation for SRE/cloud/software/AI-ML requests containing tech-overlap words;
    - multi-word/hyphen marker detection;
    - synonym-collision/discrimination around `define_mechanism`, `add_invariant_check`, and `generalize_solution`;
    - conservative README wording if README changes.
16. Full verification passes:
    - targeted domain lens/evaluator tests;
    - `uv run pytest -q`;
    - `uv run ruff check .`;
    - `uv run mypy`;
    - `uv run python scripts/run_eval_suite.py evaluation_cases/curated benchmark-output/eval-suite`;
    - `git diff --check`;
    - a simple secret scan over changed source/docs for API keys or credentials.

## Eval-suite expectation

The curated evaluation suite writes generated outputs under `benchmark-output/eval-suite`, which is ignored by git. This feature does not require committed golden-output rebaselining. The pass/fail gate is that `scripts/run_eval_suite.py` completes successfully and its expectation assertions pass after the scoring changes.

If a scoring change legitimately affects an existing curated expectation, treat that as a test-design review point: either adjust the implementation to preserve intended behavior or update the curated expectation with a documented rationale in the implementation PR. Do not silently accept eval-suite drift.

## Non-goals

- No live paid LLM provider calls.
- No new external corpus or internet-scale fact checking.
- No production calibration claim.
- No making `overallSignal` machine-actionable.
- No objective validation of architecture/design/process correctness.
- No sidecar, MCP, or platform integration.
- No artifact correctness/generalization proof; this feature only improves the advisory explanation-quality signal.
- No breaking SRE legacy special-casing.

## Failure modes to guard against

- **Metadata-only implementation:** lens lists expand but scoring remains unaffected. Guard with evaluator-level tests.
- **Cross-lens scoring drift:** tech terms leak into SRE/cloud/software/security/AI-ML scoring. Guard with lens-gated term profiles and report-regression tests.
- **Overclaiming:** README/docs imply technical correctness or optimality. Guard with wording tests or manual scan.
- **Near-neighbor drift:** broad actions get only generic alternatives. Guard with direct `generate_near_neighbor_alternatives()` tests.
- **Truncation loss:** mapped neighbors are pushed out by `availableActions` or generic fillers. Guard with five-cap priority tests.
- **SRE regression:** changes to generic/lens scoring break legacy SRE action terms, alternative ordering, or report output. Guard with existing and new regression tests.
- **Phrase no-match:** multi-word/hyphenated markers silently fail. Guard with phrase matching tests.
- **Action synonym over-support:** a vague rationale earns high support merely because it repeats generic terms. Guard with paired tests comparing specific evidence-resolving rationale against vague polished rationale; use structural/relative assertions rather than calibrated absolute thresholds.
- **Artifact-type hard gate:** custom task-local evidence is rejected because it is not in the lens. Guard by keeping artifact types advisory and testing a custom artifact still resolves mechanically.
- **False authority in report:** stronger tech terms make reports sound more authoritative. Guard by preserving method-trust notes and `uncalibrated_internal_alpha` calibration.

## Suggested implementation shape

A minimal, cohesive implementation can be done without new dependencies:

1. Add a request-level selected-lens term profile helper rather than mutating global `toulmin.py` regexes.
2. Add a module-level action-keyed explicit near-neighbor map in `actions.py`.
3. Expand `LENSES["tech"]` data.
4. Update `generate_near_neighbor_alternatives()` to inject mapped neighbors first, then fallback candidates, while preserving unknown-action behavior.
5. Make scoring functions lens-aware through the term profile:
   - action coupling;
   - support scoring;
   - Toulmin specificity/domain/evidence markers.
6. Add focused tests before implementation.
7. Update README only if needed to accurately document the expanded tech lens.

## Open questions / decisions for implementation

These are implementation decisions, not blockers:

1. Whether to add `page_human` directly to `tech` action types or rely on `generic` fallback. Recommendation: generic fallback is enough unless implementation needs explicit tech-lens ordering.
2. Whether `DomainLens` should gain `domain_terms` explicitly or derive domain terms from `risk_predicates`, `evidence_markers`, `artifact_types`, and action synonyms. Recommendation: start with derived request-level terms plus discriminative synonyms; add `domain_terms` only if tests show derived terms are noisy.
3. Whether to make `availableActions` authoritative. Recommendation: preserve current behavior for this feature and defer stricter semantics to a separate issue if needed.
