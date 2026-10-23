"""python -m triage import data/sample_tickets.csv [--engine openai] [--db triage.db]"""
import argparse
from collections import Counter
from pathlib import Path

from . import sources
from .pipeline import Pipeline
from .store import Store


def main():
    ap = argparse.ArgumentParser(prog="triage")
    sub = ap.add_subparsers(dest="cmd", required=True)
    imp = sub.add_parser("import", help="classify and store tickets from CSV, JSON or .eml files")
    imp.add_argument("paths", nargs="+", type=Path)
    imp.add_argument("--engine", choices=["rules", "openai", "anthropic"])
    imp.add_argument("--db", default="triage.db")
    imp.add_argument("--demo-dates", action="store_true", help="shift ticket dates so the newest is 'now'")
    args = ap.parse_args()

    tickets = []
    for p in args.paths:
        if p.suffix == ".csv":
            tickets += sources.from_csv(p)
        elif p.suffix == ".json":
            tickets += sources.from_json(p)
        elif p.suffix == ".eml":
            tickets.append(sources.from_eml(p.read_bytes()))
        else:
            ap.error(f"don't know how to read {p}")

    if args.demo_dates:
        tickets = sources.shift_to_now(tickets)
    pipe, store = Pipeline(args.engine), Store(args.db)
    stats = Counter()
    for t in tickets:
        r = pipe.run(t)
        stats["new" if store.save(r) else "already imported"] += 1
        stats[f"engine:{r.engine}"] += 1
        if r.needs_review:
            stats["needs review"] += 1
    for k, v in sorted(stats.items()):
        print(f"{k:<18} {v}")


if __name__ == "__main__":
    main()
