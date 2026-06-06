# Opus Review: Tech-Wide Lens Expansion Implementation Plan

Date: 2026-06-02
Artifact reviewed: `docs/plans/2026-06-02-tech-wide-lens-expansion.md`
Reviewer: Claude Code Opus (`--model opus`)
Resolved model: `claude-opus-4-8`
Session: `e3e4c7c2-7424-4589-8765-e4020bc04204`
Cost: `0.465362` USD

Note: Reviewer was intentionally run in no-tools/read-only mode from a prompt bundle, so repository facts were reviewed from the provided context rather than independently read by the reviewer.

---

I attempted to verify the plan's code claims via LSP, but no Python LSP server is available and I have no file-read/shell access in this review context, so I assessed the plan against the spec and the plan's own stated code seams (which are internally consistent with the spec's "Current state confirmed" section).

VERDICT: ACCEPT_WITH_CHANGES

CRITICAL_BLOCKERS:
- The overclaiming scan in the "Full verification sequence" is self-defeating. It iterates over `docs/specs/2026-06-02-tech-wide-lens-expansion.md` and asserts the forbidden phrases are absent — but the spec itself quotes `"Elenchus validates architectures"` and `"Elenchus determines optimal designs"` as explicit *Bad:* examples (spec §7). As written, this gate will always fail, making the mandatory verification sequence impossible to pass. The scan must scope to net-added lines (e.g. `git diff` additions) or exclude quoted negative-example lines, not scan whole spec/README files.

REQUIRED_PLAN_CHANGES:
- Fix the overclaiming scan as above (scan diffs/added lines, not full doc bodies that legitimately contain anti-pattern quotes). The same risk applies to README if it documents "don't say X" examples.
- AC 9 silently weakens the spec's "byte-identical" requirement to "ignoring fields that are inherently time-varying if the current report includes them." First determine whether the SRE report actually contains time-varying fields; if it does not, assert true byte-identity. Make normalization conditional and documented, not a pre-emptive escape hatch that could mask real scoring drift.
- The secret scan uses `git diff --name-only` (working tree only); staged/committed changes are missed. Add `--cached` (or scan both) so the gate matches the spec's "changed source/docs."
- Lens-isolation tests (Task 3 test 3) assert "no tech-specific marker count/support is added" for cloud/security/software/AI-ML. Specify these as *delta* assertions against a baseline, because words like `coupling`, `constraint`, `tradeoff`, `dependency` may already be scored independently by other lenses; an absolute-zero assertion would be wrong or flaky.

MISSING_TESTS:
- Phrase-marker detection for `decision rights`, `leading indicator` / `lagging indicator`, and `blast radius` — spec §4 lists these but Task 3 test 2 only covers second-order/fail-closed/local-patch/feedback-loop.
- Near-neighbor mapping for `change_governance` (verifying `page_human` appears in mapped neighbors, the only map that injects an escalation action) and for `tune_flywheel`.
- Explicit near-neighbor mapping assertions for `generalize_solution` / `reject_local_patch` / `add_invariant_check` (the generalization-vs-local-patch family) — Task 4 tests their synonym discrimination but not their mapped alternatives, despite spec AC 15 calling out the generalization-vs-local-patch proposal case.
- A test asserting `page_human` remains reachable for tech proposals (spec §1) regardless of whether it lives in `tech` or `generic`.
- A test that a known broad tech action under a non-tech domain produces mapped alternatives AND demonstrably *no* tech scoring boost in the same case (AC 6 combines both; Task 2 test 3 defers scoring to Task 4 test 2, but no single case proves the conjunction).

UNSAFE_OR_UNCLEAR_ASSUMPTIONS:
- Assumes the SRE report may contain time-varying fields (`createdAt`) without confirming it; this drives the AC 9 weakening and should be verified, not assumed.
- Assumes helpers `_candidate_action_types(request)`, `affirmed_term_count()`, and global `DOMAIN_RE`/`EVIDENCE_RE` exist with the described shapes; if names differ the threading tasks need adjustment (low risk, but unverified here).
- Task 2 GREEN "preserve current `AlternativeAction` IDs/rationale text style" is underspecified — injected mapped neighbors that are not in `availableActions` need a defined rationale/ID derivation; leaving it as "style" risks inconsistent or test-breaking output.

IMPLEMENTATION_RISK_NOTES:
- The secret-scan regex matches generic assignments to `token`/`secret`; legitimate Python like `token = parse(...)` in changed source could false-positive and block the gate. Constrain to high-entropy literal values or allowlist.
- Threading an optional `term_profile=None` through `score_specificity`, `extract_toulmin_argument`, `assess_support`, `_term_support`, and `action_coupling` is broad surface area; the "preserve default signatures" goal is good but each default path must be regression-covered, or SRE byte-identity will catch it late rather than per-function.
- Anti-gaming relative assertions (specific > vague "by a meaningful margin") risk being either too loose (no real guard) or flaky; pin to a structural relation (count of resolved evidence refs, distinct discriminative terms) rather than aggregate score deltas.

SIMPLIFICATIONS:
- Per spec open question 2, prefer a single derived term-count helper over a multi-field `RequestTermProfile` frozen dataclass + possible new `terms.py` module until tests show derived terms are noisy; the dataclass is more structure than this slice needs.
- The SRE byte-identity guard can be a single serialized golden string compared inline, rather than field-by-field normalization plumbing.
- Task 0's separate characterization test plus Task 4 test 5's regression test overlap; one maintained regression fixture reused in both places avoids drift between two near-identical assertions.
