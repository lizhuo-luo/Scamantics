"""Precompute results for the UI example messages so the demo works offline.

    python scripts/build_demo_cache.py            # uses the configured provider
    python scripts/build_demo_cache.py --all      # also cache the whole test set
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import EXAMPLES  # noqa: E402
from scamantics.analyzer import Analyzer  # noqa: E402
from scamantics.cache import DemoCache  # noqa: E402
from scamantics.config import load_settings  # noqa: E402
from scamantics.evaluation import load_dataset  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--provider", default=None)
    ap.add_argument("--force", action="store_true", help="recompute even if already cached")
    args = ap.parse_args()

    settings = load_settings(preset=args.provider, use_cache=False)
    analyzer = Analyzer(settings)
    cache = DemoCache(settings.cache_path)
    ok, status = analyzer.provider.healthcheck()
    print(status)
    if not ok:
        return 1

    messages = list(EXAMPLES)
    if args.all:
        messages += [e.message for e in load_dataset("data/test_set.jsonl")]
    seen = set()
    for m in messages:
        if m in seen:
            continue
        seen.add(m)
        if not args.force and cache.get(m) is not None:
            print("cached :", m[:60])
            continue
        res = analyzer.analyze(m)
        if res.error:
            print("ERROR  :", res.error)
            continue
        cache.put(res)
        print(f"ok ({res.attempts}x): {res.labels} {m[:50]}")
    cache.save()
    print(f"saved {len(cache)} entries to {cache.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
