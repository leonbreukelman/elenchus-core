# Project Model v1 Advisory Input Support Implementation Plan

> **For Hermes:** Use disciplined-project-delivery and test-driven-development to execute this plan task-by-task. This issue is implementation, not plan-only; completion means verified working code, bugs fixed, and reviewed/committed changes.

**Goal:** Add Build Arena `schemaVersion: project-model/v1` support to Elenchus Core’s existing advisory Project Model alignment path while preserving all Project Model v0 behavior.

**Architecture:** Keep Build Arena as the owner of the v1 contract. Elenchus Core will add a narrow v1 adapter that consumes the fields it evaluates, maps them into the existing `ProjectModelAlignment` report shape, and treats all findings as advisory input-quality/alignment signals. It will not redefine the full v1 schema, mutate supplied models, call live providers, or use v1 as an autonomous allow/deny gate.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, ruff, mypy, FastAPI request/report serialization.

---

## Source issue and contract references

- Elenchus Core issue: `https://github.com/leonbreukelman/elenchus-core/issues/5`
- Build Arena parent issue: `https://github.com/leonbreukelman/build-arena/issues/4`
- Build Arena authoritative v1 sources inspected locally:
  - `/home/leonb/projects/build-arena/docs/schemas/project-model-v1.schema.json`
  - `/home/leonb/projects/build-arena/docs/specs/2026-06-05-project-model-v1-shared-contract-spec.md`
  - `/home/leonb/projects/build-arena/docs/verification/2026-06-05-pre-live-readiness-register.json`

## Preflight evidence

- Branch: `feat/project-model-v1-support`
- Baseline before implementation:
  - `uv run pytest -q` passed: 90 tests
  - `uv run ruff check .` passed
  - `uv run mypy` passed: 18 source files
- Dirty-tree note: unrelated untracked docs from a prior tech-wide plan exist and must not be staged for this issue:
  - `docs/plans/2026-06-02-tech-wide-lens-expansion.md`
  - `docs/specs/2026-06-02-tech-wide-lens-expansion.md`
  - `docs/verification/2026-06-02-tech-wide-lens-plan-opus-review.md`
  - `docs/verification/2026-06-02-tech-wide-lens-spec-opus-review.md`

## Acceptance criteria

1. Existing v0 tests still pass; `project-model/v0` remains accepted.
2. A Build Arena-shaped `project-model/v1` fixture is accepted as v1, not `unsupported_version`.
3. Missing or fabricated provenance is surfaced as a provenance/grounding gap.
4. `gateReport.passed: false` caps recommendation strength and creates an invalid/gate-failing Project Model review reason/finding.
5. Weak or absent held-out probes produce advisory gaps.
6. High/blocker/critical verification gaps are surfaced as review-blocking advisory findings.
7. Verification passes:
   - `uv run pytest -q`
   - `uv run ruff check .`
   - `uv run mypy`
   - `git diff --check`

## Non-goals and boundaries

- Do not remove or reinterpret Project Model v0.
- Do not paste Build Arena’s full schema into Elenchus as a competing source of truth.
- Do not run paid/live model calls; deterministic local implementation only.
- Do not treat Project Model v1 as production allow/deny or objective truth.
- Do not stage or commit unrelated untracked tech-wide docs.

## Implementation design

### Existing flow

Current path in `src/elenchus_core/project_model.py`:

1. `assess_project_model_alignment()` returns absent/invalid/valid ProjectModelAlignment.
2. `evaluate_quality_gate()` validates only `ProjectModelV0` and flags any other `schemaVersion` as `unsupported_schema_version`.
3. Valid v0 models flow through deterministic helpers:
   - `_component_alignment()`
   - `_goal_alignment()`
   - `_invariant_violations()`
   - `_dependency_violations()`
   - `_unsupported_assumptions()`
   - `_evidence_grounding_gaps()`
   - `_near_neighbor_resistance()`
   - `_held_out_probe_failures()`
   - `_failure_mode_hint()`
4. `report.py` caps recommendations when model validity is invalid/unsupported or when advisory alignment gaps exist.

### New v1 path

Add a sibling v1 path rather than contorting v1 into v0:

- Constants:
  - `PROJECT_MODEL_V1_SCHEMA_VERSION = "project-model/v1"`
- Minimal typed adapter models or dict helpers for consumed v1 fields only:
  - top-level: `schemaVersion`, `id`, `project`, `snapshot`, `projectGraph`, `gateReport`, `provenance`
  - graph: `nodes[*].provenance_refs`, `edges[*].id`, `edges[*].provenance_refs`
  - snapshot: `components[*]`, `contracts[*]`, `observable_checks[*]`, `held_out_probes[*]`, `verification_gaps[*]`
  - provenance: `git.dirty`, `git.dirtyPaths`, `git.dirtyStateFingerprint`
- Dispatcher:
  - if `schemaVersion == project-model/v0`: run the existing v0 code unchanged.
  - if `schemaVersion == project-model/v1`: run `_assess_project_model_v1_alignment()`.
  - otherwise: keep current unsupported-version behavior.

### V1 report mapping

Map v1 findings into the existing report model so API shape stays additive/compatible:

- `ProjectModelValidity`
  - `status="valid"`, `schemaVersion="project-model/v1"`, `qualityGatePassed=True` when the v1 adapter can parse the model and `gateReport.passed` is true.
  - `status="invalid"`, `qualityGatePassed=False`, findings containing `project_model_v1_gate_failed` when `gateReport.passed` is false. This caps recommendation via existing `invalid_project_model` readiness reason without making an autonomous allow/deny decision.
  - schema/shape parse errors stay `status="invalid"`.
- `goalAlignment`
  - Use the same term-match style as v0, but source text from `project.goal`, `snapshot.goal`, component names/responsibilities, and contract names.
- `componentAlignment`
  - Match proposed action target/rationale to `snapshot.components[*].id/name/responsibility`.
- `dependencyViolations`
  - Reuse this bucket for contract edge-support problems: missing `supporting_edge_ids`, unknown edge ids, or contracts pointing to components that do not exist.
- `evidenceGroundingGaps`
  - Missing graph node/edge provenance refs.
  - Snapshot components/contracts/checks/probes/gaps with empty `provenance_refs`.
  - Snapshot string refs not found in the provenance ids emitted by `projectGraph.nodes/edges[*].provenance_refs[*].id`.
  - dirty git provenance (`provenance.git.dirty: true`) as a warning with the fingerprint in the message.
  - missing/invalid `dirtyStateFingerprint` as an error/invalid shape finding.
- `heldOutProbeFailures`
  - no probes => `missing_held_out_probe` warning.
  - any false `builder_independent_from_decomposer`, `hidden_from_primary_decomposer`, `discrimination_passed`, or `golden_control_passed` => warning/error finding keyed to the probe id.
- `unsupportedAssumptions`
  - high/blocker/critical `verification_gaps` become error findings here or in `evidenceGroundingGaps` with clear messages. Existing `readiness()` will mark `project_model_alignment_gap`; tests should assert this review reason and top weakness are present.
- `nearNeighborResistance`
  - v1 has `near_neighbor_alternatives`; evaluate similarly to v0 where present, otherwise `not_available`.
- `failureModeHint`
  - use existing `_failure_mode_hint()` with v1-derived component/goal/gaps/probe findings. Concrete misalignment remains F3; weak gaps can be F4; clean local pass can be F1.
- `notes`
  - Update product wording from “Project Model v0” to “Project Model v0/v1” where applicable.

## Bite-sized tasks

### Task 1: Add v1 fixtures and RED tests

**Objective:** Prove current code rejects v1 and define all required v1 behavior before production changes.

**Files:**
- Create/modify: `tests/test_project_model_v1.py`
- Do not modify production code in this task.

**Steps:**
1. Create a compact `_project_model_v1()` fixture matching the Build Arena v1 contract shape for consumed fields.
2. Add `test_project_model_v1_is_accepted_not_unsupported()`:
   - Build a tech-domain request with `projectModel=_project_model_v1()`.
   - Assert `projectModelValidity.status == "valid"` and `schemaVersion == "project-model/v1"`.
   - RED expectation today: fails because status is `unsupported_version`.
3. Add `test_project_model_v1_provenance_gaps_are_reported()`:
   - Remove graph node provenance and add a fabricated component provenance ref.
   - Assert `evidenceGroundingGaps` includes codes for missing and unknown provenance.
4. Add `test_project_model_v1_gate_failure_caps_recommendation()`:
   - Set `gateReport.passed = false` with one violation.
   - Evaluate full request and assert recommendation is capped to at most `reconsider`, readiness includes `invalid_project_model`, and validity findings include gate failure.
5. Add `test_project_model_v1_held_out_probe_and_verification_gaps_are_review_gaps()`:
   - Empty probes or mark a probe non-independent/failed.
   - Add a `verification_gaps` item with severity `high` or `blocker`.
   - Assert held-out probe findings and review reasons/top weaknesses expose the gap.
6. Run each new test or the whole new file and verify RED failures are specifically v1 unsupported/missing behavior, not fixture syntax errors.

### Task 2: Add v1 dispatcher and adapter skeleton

**Objective:** Route `project-model/v1` to a v1 assessor while leaving v0 behavior untouched.

**Files:**
- Modify: `src/elenchus_core/project_model.py`
- Test: `tests/test_project_model_v1.py`

**Steps:**
1. Add `PROJECT_MODEL_V1_SCHEMA_VERSION` constant.
2. Split existing valid-v0 logic into `_assess_project_model_v0_alignment(request, raw_model)` without changing helper behavior.
3. Add dispatcher in `assess_project_model_alignment()`:
   - v0 -> existing v0 helper.
   - v1 -> `_assess_project_model_v1_alignment(request, raw_model)`.
   - unknown -> existing invalid unsupported path.
4. Add `_assess_project_model_v1_alignment()` returning a valid minimal alignment for the happy-path fixture.
5. Run `tests/test_project_model_v1.py::test_project_model_v1_is_accepted_not_unsupported` and then existing v0 tests.

### Task 3: Implement v1 structural/gate validation

**Objective:** Parse consumed v1 fields and expose gate failures as advisory invalid model quality.

**Files:**
- Modify: `src/elenchus_core/project_model.py`
- Test: `tests/test_project_model_v1.py`

**Steps:**
1. Add small helper functions to safely extract dict/list/scalar fields from v1.
2. Validate required consumed top-level objects and `provenance.git.dirtyStateFingerprint`.
3. Convert `gateReport.violations[*]` into `ProjectModelFinding(code="project_model_v1_gate_failed", severity="error", location=...)` when `passed` is false.
4. Return `_invalid_alignment(status="invalid")` for gate failure and parse errors, preserving advisory note.
5. Run the gate-failure test and verify recommendation/readiness cap through `evaluate_request()`.

### Task 4: Implement provenance and contract support checks

**Objective:** Surface missing/fabricated provenance and contract edge-support problems.

**Files:**
- Modify: `src/elenchus_core/project_model.py`
- Test: `tests/test_project_model_v1.py`

**Steps:**
1. Build a set of provenance ids from every graph node/edge provenance ref object id.
2. For each graph node/edge, add a gap if `provenance_refs` is empty.
3. For each component/contract/check/probe/verification gap, add a gap if string `provenance_refs` is empty or references an id absent from the graph provenance id set.
4. Build graph edge ids and component ids.
5. For contracts, add dependency findings for missing/unknown `supporting_edge_ids` or unknown component endpoints.
6. Add dirty-state warning when `provenance.git.dirty` is true.
7. Run provenance/contract-focused tests.

### Task 5: Implement v1 held-out probe and verification-gap policy checks

**Objective:** Make v1 probes and verification gaps visible as advisory review blockers/gaps.

**Files:**
- Modify: `src/elenchus_core/project_model.py`
- Test: `tests/test_project_model_v1.py`

**Steps:**
1. Add `missing_held_out_probe` warning for empty v1 probes.
2. Add probe weakness findings for false independence, hiddenness, discrimination, or golden-control booleans.
3. Add verification-gap findings for severities `high`, `blocker`, and `critical`; severity maps to `error` in Elenchus ProjectModelFinding.
4. Ensure `_project_model_has_alignment_gaps()` already treats `evidenceGroundingGaps`, `heldOutProbeFailures`, and `unsupportedAssumptions` as gaps; adjust only if tests show a missing review reason.
5. Run held-out/verification-gap tests.

### Task 6: Refresh wording and v0 regression coverage

**Objective:** Avoid stale “v0 only” language and prove v0 behavior is preserved.

**Files:**
- Modify: `src/elenchus_core/models.py` if default notes are version-specific.
- Modify: `src/elenchus_core/report.py` if top weaknesses mention v0 only.
- Test: existing v0 tests and one explicit v0 regression assertion if needed.

**Steps:**
1. Change user-facing notes from “Project Model v0” to “Project Model v0/v1” or schema-specific text where appropriate.
2. Keep `evaluate_quality_gate()` behavior for v0 unchanged unless adding a wrapper; do not make it validate v1 if that would confuse v0-specific gate tests.
3. Run `uv run pytest tests/test_project_model_v0.py tests/test_project_model_v1.py -q` or the closest actual v0/v1 test set.

### Task 7: Full verification, review, and commit

**Objective:** Complete the implementation with proof and a rollback handle.

**Files:**
- Review all changed source/tests/docs.

**Steps:**
1. Run:
   - `uv run pytest -q`
   - `uv run ruff check .`
   - `uv run mypy`
   - `git diff --check`
2. Run an independent read-only implementation review (Opus if available; otherwise label fallback) over the final diff.
3. Fix any review blockers and rerun targeted/full verification.
4. Inspect `git status --short` and stage only issue-scoped paths:
   - `src/elenchus_core/project_model.py`
   - `src/elenchus_core/models.py` if changed
   - `src/elenchus_core/report.py` if changed
   - `tests/test_project_model_v1.py`
   - this plan and Opus review artifact
5. Commit on `feat/project-model-v1-support` with a message like `feat: add project model v1 advisory support`.
6. Do not stage unrelated untracked tech-wide docs.

## Risk controls

- **Schema divergence risk:** The adapter only evaluates consumed fields and says Build Arena owns the full schema. Tests use Build Arena-shaped fixtures rather than a local competing schema.
- **Over-gating risk:** Recommendation caps/readiness reasons remain advisory; blocked uses already include production allow/deny and machine-actionable consumption.
- **v0 regression risk:** Keep v0 helpers and tests intact; dispatcher isolates v1.
- **False provenance confidence risk:** Matching provenance ids proves internal consistency only. Notes/findings should not claim external truth or git authenticity.
- **Dirty tree risk:** Stage explicit pathspecs only.

## Review status

Opus plan review saved at `docs/verification/2026-06-06-project-model-v1-plan-opus-review.md`.

- REVIEWER: `claude model=opus opus_confirmed=yes`
- Verdict: `ACCEPT_WITH_CHANGES`
- Required changes incorporated before implementation:
  - Add a committed copy of Build Arena’s v1 JSON Schema under `docs/schemas/project-model-v1.schema.json` as a version-pinned contract snapshot, plus a sha256/provenance note. Build Arena remains the owner; Elenchus uses this copy only to validate tests/fixtures and detect drift.
  - Validate the v1 test fixture against that schema before using it for adapter tests, preventing fixture/code circularity.
  - Quote and preserve the exact mixed key casing from the schema: top-level camelCase (`schemaVersion`, `projectGraph`, `gateReport`, `dirtyStateFingerprint`) and snapshot snake_case (`provenance_refs`, `observable_checks`, `held_out_probes`, `verification_gaps`, `supporting_edge_ids`). Graph provenance refs are objects with `id`; snapshot provenance refs are string ids.
  - Keep gate-failing v1 parseable and schema-valid, but distinguish it with `project_model_v1_gate_failed` findings. Recommendation/readiness capping may reuse existing invalid/alignment-cap plumbing only if tests assert the v1-specific finding code.
  - Use v1-specific finding codes when reusing existing report buckets such as `dependencyViolations`.
  - Make v0 regression and unknown-schema-version tests required, not optional.
  - Add positive controls for clean v1 not being over-gated, malformed v1, dirty provenance distinction, medium verification gaps, and optional near-neighbor absence.

Implementation must not begin until the schema snapshot and schema-validation test are in place.
