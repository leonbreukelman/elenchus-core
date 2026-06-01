# Benchmark Curation Notes

These fixtures are small, synthetic, and author-visible. They are regression and demonstration cases for Elenchus Core's internal-alpha advisory signal; they are not benchmark submissions, calibration evidence, truth-validation proof, safety certification, or production allow/deny evidence.

## What is curated

Committed CI-facing fixtures live under `evaluation_cases/curated/`:

- `smoke.jsonl`: single-case examples covering supported, unsupported, contradicted, action-mismatch, and policy-blocked rationale/action pairs.
- `paired_adversarial.jsonl`: pairs that hold action/domain structure stable while flipping support in the supplied context, then assert the supported case ranks above the challenged case on a targeted metric.

Each fixture records:

- `id`
- `split`
- transformed `source` metadata
- provenance/stress `scenarioTags`
- the actual `EvaluationRequest`
- expected advisory behavior

Scenario tags such as `truthfulqa_style_misconception`, `sycophancy_seed`, `bbq_style_ambiguity`, `bbh_style_logic`, and `gsm8k_style_numeric` are provenance/stress tags only. They do not mean Elenchus detects truthfulness, sycophancy, bias, alignment, or arithmetic correctness.

## Data safety rules

- Do not vendor full benchmark datasets.
- Do not include customer incidents, credentials, hidden chain-of-thought, or sensitive operational details.
- Use public rationales only.
- Do not copy expected labels or source metadata into request metadata.
- Generated artifacts must be allowlist-sanitized and must omit raw context, raw rationale, raw anchors, normalized anchors, evidence snippets, contradiction snippets, Toulmin prose, and alternative rationales.
- Sentinel strings in fixtures are intentional leak tests and must never appear in generated runner artifacts.

## Current intended-use wedge

The first domain wedge is SRE/incident response because typed actions and near-neighbor alternatives are concrete:

- `terminate_idle_sessions`
- `rollback_deployment`
- `increase_iops`
- `restart_service`
- `scale_service`
- `page_human`
- `investigate_more`
- irreversible policy-blocked actions such as `drop_database`

The evaluator returns a structured review signal to help an operator or orchestrator decide whether the proposed action's public rationale is sufficiently coupled and grounded for further human review. A `proceed` recommendation is still advisory in `uncalibrated_internal_alpha` mode and does not authorize automatic execution.

## Promotion policy

Before adding more cases:

1. Keep CI fixtures small and author-auditable.
2. Put exploratory or known-weakness cases in an exploratory split rather than silently dropping failures.
3. Use paired cases where the proposed action/domain remains stable and the support in context flips.
4. Prefer ordering and targeted subscore assertions over brittle absolute score thresholds.
5. If lockbox cases are added later, document the human blindness protocol outside the harness; the harness itself must not self-attest lockbox validity.
