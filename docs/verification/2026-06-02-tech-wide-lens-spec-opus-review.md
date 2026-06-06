# Opus Review: Tech-Wide Lens Expansion Spec

Date: 2026-06-02
Artifact reviewed: `docs/specs/2026-06-02-tech-wide-lens-expansion.md`
Reviewer: Claude Code Opus (`--model opus`)
Resolved model: `claude-opus-4-8`
Session: `d4131b73-de90-4a35-bb94-a965f4e01d25`
Cost: `0.55361275` USD

Note: Reviewer was intentionally run in no-tools/read-only mode from a prompt bundle, so repository facts were reviewed from the provided context rather than independently read by the reviewer.

---

I couldn't read the local source (no Python LSP server; GitHub file-read permission wasn't granted), so I'm treating the spec's "Current state confirmed" claims as asserted rather than independently verified. Where that matters, I've flagged it. The review below is on the spec's merits.

# Review: Tech-Wide Lens Expansion

**VERDICT: ACCEPT_WITH_CHANGES**

The spec is boundary-aware, has an explicit failure-mode section, and keeps the right "advisory / `uncalibrated_internal_alpha`" framing. It is not yet plan-ready: the highest-leverage risk (shared scoring/marker vocabulary perturbing existing lenses) is asserted-away rather than mechanically pinned, and the near-neighbor seam is ambiguous.

## CRITICAL_BLOCKERS
- None that force REJECT. The items below are resolvable in-spec before planning.

## REQUIRED_CHANGES_BEFORE_PLAN
- **Pin the lens-gating mechanism for markers/terms.** Acceptance criteria 6/7 ("SRE legacy stable", "other lenses' tests pass unchanged") and 8 ("markers influence scoring") are in tension if the new tech markers are added to a *shared* `toulmin.py` regex/counter. Terms like `constraint`, `dependency`, `coupling`, `tradeoff`, `assumption` are generic enough to also fire on SRE/cloud/software requests and silently shift legacy specificity/domain scores. Require explicitly: tech marker/term sets contribute **only when the tech lens is in `selected_lenses(request)`**, and SRE-only requests must produce byte-identical output. State this as the mechanism, not just a desired outcome.
- **Resolve the near-neighbor inject-vs-reorder ambiguity.** §5 says mappings "reorder/choose from the candidate pool generated from `availableActions` and selected lenses" (filter-only), but criterion 4 implies mapped neighbors are produced regardless. Specify: (a) are mapped neighbors *injected* even if absent from `availableActions`, or only surfaced when already in the pool? (b) For a tech action proposed under a *non-tech* selected lens, mapped neighbors (and `page_human` for `change_governance`) won't be in the pool — define the fallback. Without this, behavior is request-shape-dependent.
- **Specify truncation priority.** `generate_near_neighbor_alternatives()` truncates to five. Require mapped neighbors to be ordered *before* generic fillers so they survive the 5-cap when `availableActions` is large; add this as an acceptance criterion + test.
- **Define multi-word / hyphenated marker matching.** Markers include `feedback loop`, `second-order effect`, `leading indicator`, `decision rights`, `blast radius`, `fail closed`, `local patch`. The current toulmin regexes are single-word SRE-biased; phrase/hyphen matching is a real implementation detail that will silently no-match if treated as bare word tokens. Require explicit handling (and a test) for spaced and hyphenated markers.
- **Prune/guard over-generic synonyms.** `decision`, `design`, `process`, `review`, `owner`, `cost`, `risk`, `quality`, `policy`, `service` are common English and will inflate action-term support for almost any rationale — directly feeding the "action synonym over-support" and "false authority" failure modes. Either prune to discriminative terms or add a guard test that a generic-but-vague rationale does not earn high `action_coupling` from these alone.
- **Clarify eval-suite expectation.** Criterion 10 runs `run_eval_suite.py` on `evaluation_cases/curated`. State whether curated cases have snapshot/golden outputs that the scoring changes may move, and whether moving them is allowed or must be re-baselined. As written this is a hidden pass/fail gate.

## MISSING_TESTS
- Determinism/idempotency: identical request → byte-identical output (core to a deterministic-only product).
- Near-neighbor list invariants: deduped, excludes the proposed action itself, mapped neighbors survive the 5-cap with extra `availableActions`.
- Lens isolation: an SRE/cloud/software/AI-ML request containing tech-overlap words (`constraint`, `coupling`, `dependency`, `tradeoff`) shows **no** score change vs. baseline.
- Multi-word/hyphenated marker detection (`feedback loop`, `second-order effect`, `decision rights`, `fail closed`).
- Synonym-collision test: overlapping terms (e.g. `invariant` across three families) don't collapse `action_coupling` discrimination between `define_mechanism` / `add_invariant_check` / `generalize_solution`.
- Report-wording guard that the generalize-vs-local-patch and tradeoff actions are rendered as *the evaluated proposal*, never as an Elenchus recommendation of the "right" engineering choice.
- Tech action proposed under a non-tech selected lens (fallback path), not just the happy tech-lens path.

## UNSAFE_OR_UNCLEAR_ASSUMPTIONS
- Assumes expanding a shared marker/term layer leaves SRE + other lenses unchanged; only true if markers are lens-gated, which the spec never pins.
- Assumes the existing "evidence/domain marker" layer already handles phrases/hyphens; unstated and likely false.
- Assumes mapped near-neighbors are present in the `availableActions`-derived pool; false for tech actions under non-tech lenses, and for small/empty `availableActions`.
- Assumes `decision`/`design`/`process`-class synonyms are safe scoring support; they are high-frequency and undercut the contrastive signal the product depends on.
- Assumes the placement of the mapping is "in or reachable from the lens layer," but mappings are action-keyed while lenses are domain-keyed — putting per-action mappings on `DomainLens` is an awkward fit (same action in multiple lenses).

## IMPLEMENTATION_RISK_NOTES
- **Toulmin signature churn.** Making `toulmin.py` lens-aware changes its function signatures and all callers; this is the largest seam and the main regression surface. Prefer threading a precomputed request-level term profile over passing lens objects deep into scoring.
- **Mapping location.** Recommend a module-level `action_type -> neighbors` dict rather than `DomainLens.near_neighbors`, given the action-keyed nature. The open-question recommendation to start with derived `domain_terms` is reasonable.
- **Scope/YAGNI.** 15 action types + 13 synonym families + 16 artifact types + 17 markers + 13 mappings is a large speculative surface for internal-alpha. `tune_flywheel` and `change_governance` are the least obviously exercised; consider shipping a core subset (architecture/design/process/tradeoff/generalize/invariant) and deferring flywheel/governance until a real request needs them.
- **Boundary-language drift.** The normative-sounding `reject_local_patch` / `generalize_solution` / `select_tradeoff` action names raise the chance a reader infers Elenchus is judging the engineering decision. The contrastive mapping (patch ↔ generalize) is correct for the signal, but report rendering must stay strictly "specificity of the rationale for *the proposed* action." Keep this guarded by an explicit wording test, not just manual scan.
- **Criterion 9 paired test fragility.** Relative "specific ≥ vague" comparison is the right call (no absolute thresholds), but assert a clear ordering/margin so the test isn't flaky against small heuristic shifts.
