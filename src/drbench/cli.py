from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .datasets import DATASETS
from .providers import PROVIDERS, make


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="drbench", description=__doc__ or "")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--data", type=Path, default=Path("data"), help="where datasets are stored (default: data/)")
    parser.add_argument("--runs", type=Path, default=Path("runs"), help="where outputs and scores go (default: runs/)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("fetch", help="download a dataset")
    p.add_argument("dataset", choices=list(DATASETS))
    p.add_argument("--token", help="docile: your token from https://docile.rossum.ai")
    p.add_argument("--source", type=Path, help="docile: an already downloaded annotated-trainval.zip or extracted directory")
    p.add_argument("--workers", type=int, default=8, help="charity: parallel downloads")

    p = sub.add_parser("run", help="call one system on every document of a dataset (paid API calls)")
    p.add_argument("--dataset", required=True, choices=list(DATASETS))
    p.add_argument("--system", required=True,
                   help=f"<provider>[:<mode>] — providers: {', '.join(PROVIDERS)}; e.g. deepread:extract, reducto:deep-extract")
    p.add_argument("-j", "--concurrency", type=int, default=4)
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--limit", type=int, help="only the first N documents (smoke test)")
    p.add_argument("--force", action="store_true", help="redo documents that already have an output")
    p.add_argument("--retry-failures", action="store_true", help="redo only documents whose output is a failure")

    p = sub.add_parser("grade", help="score saved outputs (offline)")
    p.add_argument("--dataset", required=True, choices=list(DATASETS))
    p.add_argument("--labels", default="official", choices=["official", "corrected"])
    p.add_argument("--system", action="append", help="only these systems (default: every run directory)")

    p = sub.add_parser("report", help="print leaderboard tables from the scores (offline)")
    p.add_argument("--dataset", action="append", choices=list(DATASETS))
    p.add_argument("--labels", default="official", choices=["official", "corrected"])

    args = parser.parse_args(argv)
    if args.command == "fetch":
        DATASETS[args.dataset].fetch(args.data, token=args.token, source=args.source, workers=args.workers)
    elif args.command == "run":
        from .runner import run

        dataset = DATASETS[args.dataset]
        docs = dataset.docs(args.data)
        if args.limit:
            docs = docs[: args.limit]
        run(dataset, make(args.system), docs, args.runs, concurrency=args.concurrency, retries=args.retries,
            force=args.force, retry_failures=args.retry_failures)
    elif args.command == "grade":
        from .score import score

        dataset = DATASETS[args.dataset]
        result = score(dataset, dataset.docs(args.data, args.labels), args.runs, args.labels, args.system)
        from .report import table

        print()
        print(table(dataset, result))
    elif args.command == "report":
        from .report import report

        print(report(args.runs, args.dataset, args.labels))
    return 0


if __name__ == "__main__":
    sys.exit(main())
