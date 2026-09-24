#!/usr/bin/env python3
"""Benchmark embedding request sizes using the same texts for every size."""

import argparse
import json
import random
import sqlite3
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from task_search import Config, RequestGate, embed, get_tokenizer, topic_text


def sample_texts(db, per_subject, seed):
    rng = random.Random(seed)
    source = sqlite3.connect(f"file:{Path(db).resolve()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        texts = []
        for subject in ("math", "physics"):
            rows = source.execute("""SELECT classifier,statement,solution FROM problems
                WHERE subject=? AND trim(statement)!='' AND trim(solution)!=''""", (subject,)).fetchall()
            if len(rows) < per_subject:
                raise ValueError(f"Недостаточно задач по предмету {subject}")
            for row in rng.sample(rows, per_subject):
                texts.extend((topic_text(row), row["solution"].strip()))
        rng.shuffle(texts)
        return texts
    finally:
        source.close()


def benchmark(texts, config, sizes, workers, rounds):
    rows = []
    for round_number in range(1, rounds + 1):
        order = sizes if round_number % 2 else list(reversed(sizes))
        for size in order:
            batches = [texts[i:i + size] for i in range(0, len(texts), size)]
            gate = RequestGate(workers)
            started = time.monotonic()
            tokens = vectors = 0
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(embed, batch, config, None, gate) for batch in batches]
                for future in as_completed(futures):
                    result, used = future.result()
                    tokens += used
                    vectors += len(result)
            seconds = time.monotonic() - started
            row = {"round": round_number, "batch_size": size, "requests": len(batches),
                   "vectors": vectors, "tokens": tokens, "seconds": round(seconds, 2),
                   "vectors_per_second": round(vectors / seconds, 2),
                   "tokens_per_second": round(tokens / seconds, 1),
                   "retries": gate.snapshot()[2]}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    summary = []
    for size in sizes:
        sample = [row for row in rows if row["batch_size"] == size]
        summary.append({"batch_size": size,
                        "median_vectors_per_second": round(statistics.median(row["vectors_per_second"] for row in sample), 2),
                        "median_tokens_per_second": round(statistics.median(row["tokens_per_second"] for row in sample), 1),
                        "total_retries": sum(row["retries"] for row in sample)})
    return {"runs": rows, "summary": summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Config().db)
    parser.add_argument("--api-key-file", type=Path, default=Path("olimpiads_data_v2/openrouter.key"))
    parser.add_argument("--sample-per-subject", type=int, default=64)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--sizes", type=int, nargs="+", default=[8, 16, 32, 64, 128])
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.sample_per_subject < 1 or args.workers < 1 or args.rounds < 1 or any(size < 1 for size in args.sizes):
        parser.error("Размеры выборки, пакета, число воркеров и повторов должны быть положительными")
    config = Config(db=args.db)
    texts = sample_texts(args.db, args.sample_per_subject, args.seed)
    tokenizer = get_tokenizer(config.tokenizer_path(), config.tokenizer_source())
    token_counts = [len(tokenizer.encode(value).ids) for value in texts]
    if max(token_counts) > config.max_tokens:
        parser.error("В выборке есть текст длиннее лимита модели")
    print(json.dumps({"texts": len(texts), "local_tokens_per_round": sum(token_counts),
                      "max_tokens_per_text": max(token_counts)}, ensure_ascii=False), flush=True)
    if args.dry_run:
        return
    config.api_key = args.api_key_file.read_text(encoding="utf-8").strip()
    result = benchmark(texts, config, args.sizes, args.workers, args.rounds)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
