"""Small metric helpers for reproducible, explicitly-labelled evaluations."""

from statistics import fmean, median
from typing import Callable, Iterable, Sequence


def retrieval_metrics(
    retrieved_ids: Sequence[str], relevant_ids: Iterable[str], *, k: int = 5
) -> dict[str, float]:
    """Calculate Precision@K, Recall@K, and reciprocal rank for one query."""
    if k < 1:
        raise ValueError("k must be positive.")
    relevant = set(relevant_ids)
    if not relevant:
        raise ValueError("At least one relevant item is required to calculate recall.")

    top_k = list(retrieved_ids[:k])
    relevant_hits = set(top_k) & relevant
    reciprocal_rank = next(
        (1.0 / rank for rank, item_id in enumerate(top_k, start=1) if item_id in relevant),
        0.0,
    )
    return {
        "precision_at_k": len(relevant_hits) / k,
        "recall_at_k": len(relevant_hits) / len(relevant),
        "mrr_at_k": reciprocal_rank,
    }


def evaluate_retrieval_cases(
    cases: Sequence[dict], retriever: Callable[[dict], Sequence[str]], *, k: int = 5
) -> dict[str, float]:
    """Average retrieval metrics over labelled cases without implying benchmark validity."""
    if not cases:
        raise ValueError("At least one evaluation case is required.")
    per_case = [
        retrieval_metrics(
            retriever(case),
            case["relevant_passage_ids"],
            k=k,
        )
        for case in cases
    ]
    return {
        name: fmean(metrics[name] for metrics in per_case)
        for name in per_case[0]
    }


def compare_retrievers(
    cases: Sequence[dict],
    baseline: Callable[[dict], Sequence[str]],
    candidate: Callable[[dict], Sequence[str]],
    *,
    k: int = 5,
) -> dict[str, dict[str, float]]:
    """Return measured metrics for both approaches without asserting superiority."""
    return {
        "baseline": evaluate_retrieval_cases(cases, baseline, k=k),
        "candidate": evaluate_retrieval_cases(cases, candidate, k=k),
    }


def citation_coverage(claims: Sequence[dict]) -> float | None:
    """Fraction of evaluated claims that include at least one citation identifier."""
    if not claims:
        return None
    return sum(bool(claim.get("citations")) for claim in claims) / len(claims)


def evidence_support_rate(claims: Sequence[dict]) -> float | None:
    """Fraction of explicitly annotated claims labelled supported by evidence."""
    annotated = [claim for claim in claims if claim.get("evidence_status") in {
        "supported", "unsupported", "uncertain",
    }]
    if not annotated:
        return None
    return sum(claim["evidence_status"] == "supported" for claim in annotated) / len(annotated)


def agent_task_completion(tasks: Sequence[dict]) -> float | None:
    if not tasks:
        return None
    return sum(task.get("completed") is True for task in tasks) / len(tasks)


def latency_summary(samples: Iterable[float]) -> dict[str, float | int] | None:
    values = [float(sample) for sample in samples]
    if not values:
        return None
    if any(value < 0 for value in values):
        raise ValueError("Latency samples cannot be negative.")
    return {
        "sample_count": len(values),
        "mean_seconds": fmean(values),
        "median_seconds": median(values),
    }


def failure_rate(results: Sequence[dict]) -> float | None:
    if not results:
        return None
    return sum(result.get("success") is not True for result in results) / len(results)