"""drbench — run document extraction APIs on public benchmarks and score them.

    drbench systems                              what is run: vendor, product, settings, price
    drbench fetch DATASET                        download a benchmark
    drbench run DATASET SYSTEM [SYSTEM ...]      call the APIs on every document (paid)
    drbench grade DATASET                        score the saved outputs (offline)
    drbench report [--readme README.md]          results tables (offline)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .datasets import DATASETS
from .systems import PRICES_CHECKED, SYSTEMS, get


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="drbench", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--data", type=Path, default=Path("data"), help="where benchmarks are downloaded (default: data/)")
    parser.add_argument("--runs", type=Path, default=Path("runs"), help="where outputs and scores go (default: runs/)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("systems", help="list the systems, their settings and prices")

    p = sub.add_parser("fetch", help="download a benchmark")
    p.add_argument("dataset", choices=list(DATASETS))
    p.add_argument("--token", help="docile: your token from https://docile.rossum.ai")
    p.add_argument("--source", type=Path, help="docile: an already downloaded annotated-trainval.zip or extracted directory")
    p.add_argument("--workers", type=int, default=8, help="charity: parallel downloads")

    p = sub.add_parser("run", help="call systems on every document of a benchmark (paid API calls)")
    p.add_argument("dataset", choices=list(DATASETS))
    p.add_argument("systems", nargs="+", metavar="SYSTEM", help=f"one or more of: {', '.join(SYSTEMS)}")
    p.add_argument("-j", "--concurrency", type=int, default=4, help="documents in flight at once (default: 4)")
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--limit", type=int, help="only the first N documents (a cheap smoke test)")
    p.add_argument("--retry-failures", action="store_true", help="also redo documents that failed")
    p.add_argument("--force", action="store_true", help="redo every document")

    p = sub.add_parser("grade", help="score the saved outputs (offline)")
    p.add_argument("dataset", choices=list(DATASETS))
    p.add_argument("--labels", default="official", choices=["official", "corrected"])

    p = sub.add_parser("report", help="print the results tables (offline)")
    p.add_argument("--labels", default="official", choices=["official", "corrected"])
    p.add_argument("--readme", type=Path, help="also write the summary table into this README")

    args = parser.parse_args(argv)
    if args.command == "systems":
        print(systems_table())
    elif args.command == "fetch":
        DATASETS[args.dataset].fetch(args.data, token=args.token, source=args.source, workers=args.workers)
    elif args.command == "run":
        from .providers import adapter
        from .runner import run

        dataset = DATASETS[args.dataset]
        docs = dataset.docs(args.data)[: args.limit]
        for system in map(get, args.systems):
            counts = run(dataset, system, adapter(system), docs, args.runs, concurrency=args.concurrency,
                         retries=args.retries, force=args.force, retry_failures=args.retry_failures)
            if counts.get("stopped"):
                return 1  # so a chain of commands halts here instead of running on
    elif args.command == "grade":
        from .report import detail
        from .score import score

        dataset = DATASETS[args.dataset]
        print("\n" + detail(dataset.name, score(dataset, dataset.docs(args.data, args.labels), args.runs, args.labels)))
    elif args.command == "report":
        from .report import detail, load, summary, write_readme

        scores = load(args.runs, args.labels)
        if not scores:
            print("no scores yet — run `drbench grade DATASET` first")
            return 1
        print(summary(scores) + "\n\n" + "\n\n".join(detail(d, s) for d, s in scores.items()))
        if args.readme:
            write_readme(args.readme, scores)
    return 0


def systems_table() -> str:
    lines = [
        "| System | Vendor | Product | Settings sent (all else default) | Price | API key |",
        "|---|---|---|---|---|---|",
    ]
    for s in SYSTEMS.values():
        settings = ", ".join(f"`{k}={v}`" for k, v in s.settings.items()) or "none"
        if s.price.per_1k_pages is not None:
            price = f"${s.price.per_1k_pages:g} per 1,000 pages"
        else:
            price = f"${s.price.per_credit:g} per credit, credits as reported"
        lines.append(f"| `{s.id}` | {s.vendor} | {s.product} | {settings} | {price} | `{s.key_env}` |")
    return "\n".join(lines) + f"\n\nList prices, pay as you go, checked {PRICES_CHECKED}."


if __name__ == "__main__":
    sys.exit(main())
