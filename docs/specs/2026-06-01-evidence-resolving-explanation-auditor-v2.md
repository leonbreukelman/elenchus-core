# Evidence-Resolving Explanation Auditor v2 Spec

Date: 2026-06-01

## Product boundary

Elenchus Core v2 is an internal-alpha, task-local evidence-resolving explanation-quality auditor for public structured rationale. It is an advisory signal only. It does not judge action correctness, objective truth, hidden CoT, external artifact provenance, production allow/deny readiness, or autonomous execution safety.

Counterfactual probing is not run unless an operational-agent re-execution contract is supplied. In this slice, reports expose `methodTrust.counterfactualProbe = "not_run"`.

## Request contract

Legacy requests remain valid:

- `traceId`
- `domain`
- `context`
- `proposedAction`
- `rationale`
- optional `metadata`

Structured v2 requests may additionally include:

- `availableActions`: typed actions available to the actor
- `structuredRationale`: public rationale sections
  - `claim`
  - `grounds[]` with `text`, `evidenceRefs[]`, and `loadBearing`
  - `warrants[]`
  - `assumptions[]`
  - `rejectedAlternatives[]`
  - `uncertainty[]`
  - `wouldChangeIf[]`
- `evidenceBundle[]`: task-local artifacts
  - `id`
  - `type`
  - `contentPointer`
  - `content`
  - optional `sha256`
  - optional `metadata`
- `domainHints[]`: composable lens hints

Evidence bundle bounds:

- max 50 artifacts
- max 20,000 characters per artifact content
- max 200,000 total local evidence characters per request

## Evidence resolution semantics

Evidence resolution has two distinct layers.

### Mechanical artifact validation

Mechanical checks are the only v2 evidence facts allowed to cap recommendations:

- referenced artifact ID exists
- duplicate artifact IDs are detected and treated as unresolved
- local content is available
- `contentPointer` is present for higher trust
- supplied `sha256` matches supplied UTF-8 content when both are present
- pointer-only artifacts are `pointer_unresolved` because this slice has no dereferencer
- `sha256` without local content is `hash_unverifiable`, not verified

A matching `sha256` only proves self-consistency of the supplied local content and supplied hash. It does not prove external authenticity, freshness, or provenance.

### Advisory support scoring

Support scoring is a conservative lexical proxy, not entailment. It:

- removes stopwords and checks meaningful token overlap
- requires numeric values in the ground to appear in cited artifact content
- requires at least three meaningful ground tokens
- requires at least 0.45 token coverage
- requires proposed-action or target vocabulary to appear in cited content to reduce keyword-stuffing wins
- defaults to `unresolved` when uncertain

Advisory support and advisory contradiction flags do not cap recommendations by themselves.

## Report additions

Structured reports add:

- `evidenceResolution`
  - `score`
  - `mechanicalScore`
  - `supportScore`
  - `summary` counts
  - safe ref statuses by artifact ID
  - ground hashes and statuses, never raw artifact content
- `methodTrust`
  - `structural`: `deterministic` or `legacy_free_text`
  - `evidenceResolution`: `self_consistent_artifact_hash`, `resolved_artifact_refs`, `weak_context_proxy`, `missing_or_unresolved_refs`, or `not_available`
  - `counterfactualProbe`: `not_run` in this slice
  - notes describing limitations
- additive subscores:
  - `evidenceResolution`
  - `evidenceCoverage`
  - `structuralCompleteness`

Legacy free-text requests keep the existing path and get additive `evidenceResolution = null` and `methodTrust.evidenceResolution = "not_available"`.

## Domain lenses

Thin domain lenses provide vocabulary hints only. They are not domain assurance packs. Built-in lenses:

- `sre`
- `tech`
- `cloud`
- `security`
- `software`
- `ai_ml`
- `generic`

Lens selection order is deterministic: request domain first, then `domainHints` order, then generic fallback, with duplicates removed preserving first occurrence.

## Recommendation caps

Mechanical evidence failures can cap recommendations:

- hash mismatch, hash unverifiable, pointer unresolved, or duplicate artifact ID: cap at `reconsider` or stricter
- missing evidence refs, pointer missing, or unreferenced load-bearing grounds: cap at `proceed_with_caveats` or `reconsider` depending severity

Operator review remains required for every complete report.

## Sanitization

Sanitized eval outputs may include artifact IDs, statuses, counts, scores, and method trust. They must not include raw context, raw rationale, raw evidence artifact content, grounding evidence snippets, Toulmin text, or anchor text.
