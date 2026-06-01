# Evidence Auditor v2 Plan Review

Date: 2026-06-01

## Scope

Reviewed `docs/plans/2026-06-01-evidence-resolving-explanation-auditor-v2.md` before implementation, using Opus and Grok as adversarial reviewers.

## Reviewer artifacts

- Opus raw wrapper: `/tmp/elenchus-v2-plan-opus-review-final.json`
- Opus parsed content: `/tmp/elenchus-v2-plan-opus-review-content.json`
- Grok raw wrapper: `/tmp/elenchus-v2-plan-grok-review-raw.json`
- Grok parsed content: `/tmp/elenchus-v2-plan-grok-review-content.json`

These files are outside the repo and are not committed. No secrets are included in the repo artifact.

## Verdicts

- Opus: `ACCEPT_WITH_CHANGES`
- Grok: `ACCEPT_WITH_CHANGES`

## Accepted plan changes

1. Split mechanical artifact validation from advisory fuzzy support scoring.
2. Allow recommendation caps only from mechanical evidence failures:
   - missing refs
   - duplicate artifact IDs
   - sha256 mismatch
   - sha256 supplied without local content
   - pointer required but absent
   - pointer-only artifacts that this slice cannot dereference
3. Keep advisory support/contradiction flags advisory-only; they cannot silently gate recommendations.
4. Rename top method-trust tier from `verified_artifact_hash` to `self_consistent_artifact_hash` to avoid provenance overclaiming.
5. Require both matching local content hash and a content pointer for the top evidence-resolution trust tier.
6. Use deterministic `contextGrounding` integration for structured requests: `min(existing_context_grounding, evidence.score)` when both exist; legacy free-text requests keep the old score unchanged.
7. Add explicit EvidenceBundle bounds: max 50 artifacts, max 20,000 chars per artifact, max 200,000 evidence chars per request.
8. Add tests for keyword stuffing, false-positive negation, hash-without-content, pointer-only artifacts, duplicate artifact IDs, mixed valid/missing refs, lens priority, lens isolation, and legacy stability.
9. Treat 2026 document dates as intentional because the session date is 2026-06-01.

## Deferred or deliberately constrained

- No live LLM calls from production code.
- No counterfactual probing implementation in this slice; reports must say `not_run` unless an operational-agent re-execution contract exists.
- No eval-suite loader broadening unless it remains small and fully sanitized; v2 behavior may be proven primarily through unit tests.
- No claim that hashes prove external authenticity, freshness, or objective truth; they only prove self-consistency of supplied local content.

## Implementation gate

Implementation may proceed after the patched plan because both reviewers accepted the plan with changes and the blockers were incorporated into the plan.
