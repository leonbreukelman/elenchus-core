from elenchus_core.eval_cases import load_paired_eval_cases
from elenchus_core.eval_suite import evaluate_pair, sanitize_pair_outcome

PAIRS_PATH = "evaluation_cases/curated/paired_adversarial.jsonl"
ONLINE_PAIR_BENCHMARKS = {
    "ai2_arc",
    "fever",
    "gsm8k",
    "hellaswag",
    "winogrande",
}


def test_paired_adversarial_cases_order_supported_over_challenged():
    pairs = load_paired_eval_cases(PAIRS_PATH)
    assert len(pairs) >= 8

    for pair in pairs:
        outcome = evaluate_pair(pair)
        assert outcome.supported.report.status == "complete", pair.pair_id
        assert outcome.challenged.report.status == "complete", pair.pair_id
        assert outcome.passed, f"{pair.pair_id}: {outcome.failure}"
        row = sanitize_pair_outcome(outcome)
        assert row["supportedRecommendation"] in {"proceed", "proceed_with_caveats"}
        assert row["supportedGroundingSummary"]["contradicted"] == 0
        assert row["challengedGroundingSummary"] is not None
        if pair.challenged.expected.label == "contradicted":
            assert outcome.challenged.report.recommendation != "proceed", pair.pair_id


def test_paired_adversarial_cases_include_online_ai_dataset_source_pairs():
    pairs = load_paired_eval_cases(PAIRS_PATH)
    benchmarks = {case.source.benchmark for pair in pairs for case in (pair.supported, pair.challenged)}

    assert benchmarks >= ONLINE_PAIR_BENCHMARKS
