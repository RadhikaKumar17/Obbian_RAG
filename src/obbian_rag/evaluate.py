import json
import math
from collections import Counter
from pathlib import Path


def evaluate(pipeline, dataset: Path, report: Path, split: str):
    cases = [json.loads(line) for line in dataset.read_text().splitlines() if line.strip()]
    cases = [c for c in cases if split == "all" or c["split"] == split]
    if not cases:
        raise ValueError("No evaluation cases selected.")
    rows, totals = [], Counter()
    for case in cases:
        answer = pipeline.ask(case["question"])
        cited = {c.document_id for c in answer.citations}
        expected = set(case.get("document_ids", []))
        hits = pipeline.retrieve(case["question"]) if expected else []
        retrieved = [h["document_id"] for h in hits]
        recall = len(expected & set(retrieved)) / len(expected) if expected else None
        rank = next((i + 1 for i, doc in enumerate(retrieved) if doc in expected), None)
        grounded = all(
            c.quote in next(x["text"] for x in pipeline.index.chunks if x["chunk_id"] == c.chunk_id)
            for c in answer.citations
        )
        status_ok = answer.status == case["status"]
        facts_ok = all(term.lower() in answer.answer.lower() for term in case.get("must_include", []))
        citations_ok = expected <= cited if case["status"] == "answered" else not answer.citations
        passed = status_ok and facts_ok and citations_ok and grounded
        totals["passed"] += passed
        totals["status_correct"] += status_ok
        totals["grounded"] += grounded
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "passed": passed,
                "status": answer.status,
                "expected_status": case["status"],
                "facts_ok": facts_ok,
                "citations_ok": citations_ok,
                "retrieval_recall": recall,
                "reciprocal_rank": 1 / rank if rank else 0,
                "latency_ms": answer.latency_ms,
                "answer": answer.answer,
            }
        )
    recalls = [r["retrieval_recall"] for r in rows if r["retrieval_recall"] is not None]
    latencies = sorted(r["latency_ms"] for r in rows)
    summary = {
        "mode": pipeline.settings.provider,
        "split": split,
        "index_version": pipeline.index.version,
        "cases": len(rows),
        "pass_rate": totals["passed"] / len(rows),
        "status_accuracy": totals["status_correct"] / len(rows),
        "verbatim_grounding_rate": totals["grounded"] / len(rows),
        "retrieval_recall_at_k": sum(recalls) / len(recalls) if recalls else None,
        "mrr": sum(r["reciprocal_rank"] for r in rows if r["retrieval_recall"] is not None)
        / max(1, len(recalls)),
        "latency_p95_ms": latencies[math.ceil(len(latencies) * 0.95) - 1],
        "note": "Offline tests validate mechanics, not semantic model quality. Human review is required for relevance and completeness.",
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"summary": summary, "cases": rows}, indent=2, ensure_ascii=False))
    return summary
