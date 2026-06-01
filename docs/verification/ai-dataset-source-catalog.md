# AI Dataset Source Catalog for Elenchus Core Fixtures

This catalog records online AI-evaluation datasets and corpora that are suitable as scenario seeds for Elenchus Core's curated internal-alpha evaluation suite.

Important boundary: scenario-provenance tags are not detector claims. A fixture tagged `truthfulqa`, `bbq`, or `anthropic_sycophancy` does not mean Elenchus measures truthfulness, bias, or sycophancy. It means the fixture borrows a public benchmark's scenario shape to test Elenchus Core's narrower contract: whether a public rationale is grounded in supplied context and specifically coupled to the proposed action.

These fixtures are not a benchmark submission, not leaderboard evidence, not calibration evidence, and not production allow/deny validation. They use no hidden chain-of-thought. They commit only small transformed synthetic fixtures and do not vendor full datasets.

## Source policy

- Do not vendor full datasets in this repository.
- Do not copy raw benchmark items into fixtures until license and redistribution terms are explicitly reviewed.
- Use public dataset URLs, source IDs, and transformations as provenance metadata.
- Keep expected labels about Elenchus behavior only: supported, unsupported, contradicted, action_mismatch, policy_blocked, or error_path.
- Treat all outputs as `uncalibrated_internal_alpha` advisory diagnostics requiring operator review.

## Curated online sources used as initial fixture seeds

| Key | Online source | Useful scenario shape | Current transformation |
| --- | --- | --- | --- |
| `anthropic_sycophancy` | https://github.com/anthropics/evals/tree/main/sycophancy | User-pressure / agreement-with-user cases | Evidence-vs-user-preference action fixtures. The tag is not a sycophancy detector claim. |
| `truthfulqa` | https://github.com/sylinrl/TruthfulQA | False premise / misconception correction | Supplied-context correction fixtures where rationale repeats a contradicted premise. |
| `big_bench_hard` | https://github.com/suzgunmirac/BIG-Bench-Hard | Multi-step logic, boolean/deduction style | Release/error and dependency fixtures that test absent or contradicted load-bearing anchors. |
| `bbq` | https://github.com/nyu-mll/BBQ | Ambiguous QA and unsupported demographic assumptions | Unsupported-assumption fixtures. The tag is not a bias detector claim. |
| `gsm8k` | https://github.com/openai/grade-school-math | Numeric word-problem reasoning | Numeric-anchor capacity and absent-number fixtures. These do not validate arithmetic correctness. |
| `ai2_arc` | https://huggingface.co/datasets/allenai/ai2_arc | Science cause/effect QA | Storage-bottleneck and resource-causality action fixtures. |
| `fever` | https://huggingface.co/datasets/mteb/fever | Supported/refuted/not-enough-info fact verification | Release-regression claim fixtures with support/refute context flips. |
| `hellaswag` | https://github.com/rowanz/hellaswag | Commonsense continuation selection | Runbook next-step fixtures with grounded continuation/action selection. |
| `mmlu` | https://github.com/EleutherAI/lm-evaluation-harness/blob/main/lm_eval/tasks/mmlu/README.md | Expert-domain multiple-choice QA | Database/SRE expert-action fixtures with explicit context anchors. |
| `winogrande` | https://winogrande.allenai.org/ | Coreference and commonsense contrast | Service/action target disambiguation fixtures. |

## Why transformed fixtures instead of raw benchmark rows?

Elenchus Core does not answer benchmark questions. It evaluates a proposed action, supplied context, and public rationale. Raw benchmark rows would often test answer accuracy rather than the intended Elenchus contract. The transformation step makes each source useful while keeping the claim narrow:

1. Identify the benchmark's stress shape: numeric reasoning, contradiction, ambiguity, continuation, coreference, or user pressure.
2. Create an operational or generic context with explicit anchors.
3. Create a proposed action and public rationale.
4. Label only the Elenchus-relevant behavior: support, absence, contradiction, action mismatch, or policy block.
5. Assert advisory invariants and artifact-sanitization rules.

## Expansion backlog

Potential next source families after this first expansion:

- StrategyQA / CommonsenseQA for multi-hop implicit support.
- WSC / SuperGLUE-WSC for additional target disambiguation fixtures.
- SciFact for scientific claim-support/refute cases.
- MATH / SVAMP for more numeric-anchor stress tests, without claiming math verification.
- MACHIAVELLI only for scenario/action-tradeoff grounding, not ethical scoring.

Before adding any raw-derived fixture, record its source URL, source ID, license status, and transformation note in the fixture metadata and update this catalog.
