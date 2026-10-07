"""Run the labelled test set through the analyzer and report metrics.

Usage:
    python evaluate.py                       # uses provider from env (default: ollama)
    python evaluate.py --provider groq       # any preset name from scamantics.config.PRESETS
    python evaluate.py --limit 10 --out results/eval_groq.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from scamantics.analyzer import Analyzer
from scamantics.config import load_settings
from scamantics.evaluation import check_dataset, evaluate, format_report, load_dataset


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data/test_set.jsonl")
    ap.add_argument("--provider", default=None, help="preset name, e.g. ollama, groq, openai, gemini, mock")
    ap.add_argument("--model", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--category", default=None, help="only evaluate one category (familiar/paraphrased/benign)")
    ap.add_argument("--out", default=None, help="write per-example predictions and metrics to this JSON file")
    ap.add_argument("--no-cache", action="store_true", help="ignore the demo cache and always call the model")
    args = ap.parse_args(argv)

    examples = load_dataset(args.data)
    problems = check_dataset(examples)
    if problems:
        print("dataset problems:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 2
    if args.category:
        examples = [e for e in examples if e.category == args.category]
    if args.limit:
        examples = examples[: args.limit]

    settings = load_settings(preset=args.provider, model=args.model, use_cache=False if args.no_cache else None)
    analyzer = Analyzer(settings)
    ok, status = analyzer.provider.healthcheck()
    print(f"provider: {status}")
    if not ok:
        print("provider unavailable; aborting", file=sys.stderr)
        return 1

    results = []
    t0 = time.time()
    for i, ex in enumerate(examples, 1):
        t = time.time()
        res = analyzer.analyze(ex.message)
        results.append(res)
        flag = "" if set(res.labels) == set(ex.labels) else "  <- mismatch"
        print(f"[{i:2d}/{len(examples)}] {ex.id} {time.time() - t:5.1f}s gold={ex.labels} pred={res.labels}{flag}")
    total = time.time() - t0

    report = evaluate(examples, results)
    print()
    print(format_report(report))
    print(f"\nmodel: {settings.describe}   total time: {total:.1f}s   avg: {total / max(1, len(examples)):.1f}s/msg")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "model": settings.describe,
                    "metrics": report,
                    "predictions": [
                        {"id": e.id, "category": e.category, "gold": e.labels, "gold_evidence": e.evidence, "result": r.model_dump()}
                        for e, r in zip(examples, results)
                    ],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
