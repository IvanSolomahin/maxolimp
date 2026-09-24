#!/usr/bin/env python3
"""Compare vector and hybrid retrieval on manually labeled queries."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from search.task_search import Config, search


def evaluate(labels, config, k=10):
    summary = defaultdict(lambda: {"queries": 0, "recall_sum": 0.0, "reciprocal_rank": 0.0})
    details = []
    for case in labels:
        expected = set(case["relevant_ids"])
        if not expected:
            raise ValueError(f"Нет релевантных ID: {case['query']}")
        for method in ("fts", "vector", "hybrid"):
            results = search(case["query"], mode=case["mode"], subject=case["subject"],
                             grade=case.get("grade"), year=case.get("year"), k=k,
                             method=method, config=config)
            ranks = [rank for rank, row in enumerate(results, 1)
                     if expected.intersection([row["problem_id"], *row["duplicates"]])]
            found = set().union(*(expected.intersection([row["problem_id"], *row["duplicates"]])
                                  for row in results))
            rank = min(ranks) if ranks else None
            key = (case["subject"], case["mode"], method)
            summary[key]["queries"] += 1
            summary[key]["recall_sum"] += len(found) / len(expected)
            summary[key]["reciprocal_rank"] += 1 / rank if rank else 0
            details.append({"query": case["query"], "subject": case["subject"],
                            "mode": case["mode"], "method": method, "first_relevant_rank": rank})
    return {"k": k, "summary": [dict(subject=key[0], mode=key[1], method=key[2],
                                    queries=value["queries"], recall_at_k=round(value["recall_sum"] / value["queries"], 3),
                                    mrr_at_k=round(value["reciprocal_rank"] / value["queries"], 3))
                              for key, value in sorted(summary.items())], "details": details}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("labels", type=Path)
    parser.add_argument("--db", type=Path, default=Config().db)
    parser.add_argument("--index-dir", type=Path, default=Config().index_dir)
    parser.add_argument("--model", default=Config().model)
    parser.add_argument("--dimensions", type=int, default=Config().dimensions)
    parser.add_argument("--max-tokens", type=int, default=Config().max_tokens)
    parser.add_argument("--tokenizer", type=Path)
    parser.add_argument("--tokenizer-url")
    parser.add_argument("--api-key-file", type=Path)
    parser.add_argument("-k", type=int, default=10)
    args = parser.parse_args()
    key = args.api_key_file.read_text(encoding="utf-8").strip() if args.api_key_file else None
    config = Config(args.db, args.index_dir, args.model, args.dimensions, args.max_tokens,
                    args.tokenizer, args.tokenizer_url, key)
    cases = json.loads(args.labels.read_text(encoding="utf-8"))
    print(json.dumps(evaluate(cases, config, args.k), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
