# Project Model v1 Plan Opus Review

I could not load the actual source (no Python LSP here; GitHub read permission not granted), so this review is of the plan text on its own terms, with that caveat called out where it matters.

---

REVIEWER: claude model=opus opus_confirmed=yes

## Verdict: ACCEPT_WITH_CHANGES

The plan is advisory-safe, correctly scoped, preserves v0, and maps cleanly onto the acceptance criteria. One near-blocking risk (fixture/implementation circularity against an unverified schema) must be fixed before coding, plus several test gaps. None are fundamental design flaws, so this is not a REJECT.

## Critical blockers (fix in plan before implementation)

1. **Fixture↔implementation circularity defeats the core issue (AC2).** Task 1's `_project_model_v1()` fixture is author-written, and Task 2–5 implement the adapter against that same fixture. If the fixture's field names/casing diverge from the authoritative `project-model-v1.schema.json`, the fixture and code will agree with each other, tests go GREEN, and *real* Build Arena v1 payloads still fail — the exact thing the issue exists to prevent. There must be an objective anchor: either (a) validate the fixture against the real Build Arena JSON Schema inside a test, or (b) vendor a real Build Arena example payload as the fixture and pin its provenance. "Build Arena-shaped" must mean "schema-validated," not "shaped by the plan author."

2. **Unverified, internally inconsistent field naming.** The consumed-field list mixes camelCase (`schemaVersion`, `gateReport`, `projectGraph`, `dirtyStateFingerprint`) with snake_case (`provenance_refs`, `held_out_probes`, `verification_gaps`, `observable_checks`, `supporting_edge_ids`). Mixed casing in one schema is plausible but suspicious; a single wrong guess silently emits false "missing/fabricated provenance" findings. The plan must quote the exact keys/casing from the schema file (it claims to have inspected it) rather than asserting them. Same for the asymmetry the plan assumes: graph `provenance_refs[*]` are **objects with `.id`** while snapshot `provenance_refs[*]` are **bare strings** — confirm against schema; if wrong, every snapshot ref is flagged fabricated.

## Required plan changes

3. **Contract-ownership sync mechanism.** The plan rightly says Build Arena owns the schema, but the authoritative file lives at `/home/leonb/projects/build-arena/...` — unavailable to Elenchus CI. Add a committed, version-pinned snapshot/checksum of the consumed-field contract (or a vendored schema copy) plus a documented re-sync step, so schema drift is *detected* rather than silently passing. Without this, "Build Arena owns the contract" is aspirational.

4. **Don't overload `status="invalid"` for gate failure.** Routing `gateReport.passed=false` through the same `invalid` status as parse/shape errors conflates "Elenchus couldn't parse the model" with "Build Arena's own gate failed." A consumer can't distinguish them from `status` alone. Keep the distinct finding code `project_model_v1_gate_failed` (good) but either keep `status="valid"` with a separate readiness reason, or explicitly document the overload and assert the distinguishing code in tests. AC4 permits the cap; it does not require collapsing the two failure meanings.

5. **`dependencyViolations` bucket reuse for contract/edge problems** is semantic overloading. Acceptable for report-shape stability, but require v1-specific finding codes within the bucket so downstream consumers aren't misled into reading them as dependency-graph violations.

6. **Verify helper internals before Task 2, not assume them.** `_failure_mode_hint()`, `_project_model_has_alignment_gaps()`, and `readiness()` are reused on faith. Add an explicit step to confirm which report fields `_project_model_has_alignment_gaps()` actually inspects — otherwise reusing buckets may not trigger `project_model_alignment_gap` as ACs 5/6 require.

7. **Promote the v0 regression assertion from "if needed" to required** (AC1). Task 6 also edits the shared notes string ("v0" → "v0/v1"); existing v0 tests may assert the literal string. Add a guard/check before changing it. Consider deferring the wording change — it's the only scope creep and carries the highest regression risk for the least value.

## Missing tests

- **Schema-conformance test** for the fixture (blocker #1) — the single most important addition.
- **Unknown `schemaVersion` still returns `unsupported_version`** — dispatcher regression guard; ACs cover v0/v1 but not that the `else` branch survived.
- **Clean v1 happy path is NOT over-gated** — positive control asserting recommendation is *uncapped* when `gateReport.passed=true` and no gaps. The plan only tests the failing direction; over-gating risk is untested.
- **Malformed v1 as RED in Task 1** — missing required top-level object and missing/invalid `dirtyStateFingerprint` → `status=invalid` shape error. Task 3 implements this but Task 1 enumerates no failing test for it.
- **Unknown / sub-threshold `verification_gaps` severity** (e.g. `medium`, or an unrecognized string) → no crash and no error finding. Boundary behavior is unspecified.
- **Dirty-git distinctions:** `dirty=true` with valid fingerprint → warning; `dirty=true` missing fingerprint → invalid-shape error. Two separate assertions.
- **`near_neighbor_alternatives` absent → `not_available`** (don't let a missing optional field become a false gap).

## Notes on advisory-only semantics

The plan is disciplined here: recommendation *caps* rather than allow/deny, no model mutation, no live provider calls, and the explicit non-goal that v1 is not objective truth or a production gate. Keep the "provenance-id matching proves internal consistency only, not external/git authenticity" caveat in the emitted finding messages, not just the plan — otherwise a consumer may over-trust a "provenance grounded" result. Recommend one test asserting that even with all gaps present, the output never escalates beyond a recommendation cap (no allow/deny field is set).

## Notes on Build Arena contract ownership

Ownership is asserted correctly but not yet *enforced* (blocker #3). The risk-controls section claims "tests use Build Arena-shaped fixtures rather than a local competing schema," yet a hand-authored fixture with no link back to the source schema **is** a local competing definition in practice. The fix in #1/#3 is what actually makes the ownership claim true. As written, Elenchus could drift from Build Arena v1 and never notice — which is the precise failure mode this issue is meant to close.
