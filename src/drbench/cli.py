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
    p.add_argument("--ids", type=Path, help="only the documents listed in this file, one id per line "
                   "(e.g. datasets/longextract/sample-20.txt)")
    p.add_argument("--force", action="store_true", help="redo documents that already have an output")
    p.add_argument("--retry-failures", action="store_true", help="redo only documents whose output is a failure")

    p = sub.add_parser("grade", help="score saved outputs (offline)")
    p.add_argument("--dataset", required=True, choices=list(DATASETS))
    p.add_argument("--labels", default="official", choices=["official", "corrected"])
    p.add_argument("--ids", type=Path, help="grade only the documents listed in this file (the file the run used)")
    p.add_argument("--system", action="append", help="only these systems (default: every run directory)")

    p = sub.add_parser("report", help="print leaderboard tables from the scores (offline)")
    p.add_argument("--dataset", action="append", choices=list(DATASETS))
    p.add_argument("--labels", default="official", choices=["official", "corrected"])

    from .suite import DEFAULT_SYSTEMS, SYSTEMS, pages

    for plan, blurb in (
        ("short", "the run behind our published numbers: all 500 DocILE documents, the first 40 "
                  "Kleister-Charity documents and the 20 shortest LongExtractBench documents"),
        ("full", "every document of the three benchmarks"),
    ):
        p = sub.add_parser(
            f"{plan}-run",
            help=f"{blurb} — {pages(plan):,} pages per system (paid API calls)",
            description=f"Reproduce our comparison end to end: {blurb}, {pages(plan):,} pages per system, "
                        f"through the {len(DEFAULT_SYSTEMS)} systems of the published table. Downloads the datasets, "
                        "sends every document, grades the outputs and prints the table. Prints the cost at list price "
                        "and asks before sending anything. Resumable: rerun the same command to continue.",
            epilog="Systems run by default: " + ", ".join(s.id for s in DEFAULT_SYSTEMS)
                   + (". Also available: " + ", ".join(s.id for s in SYSTEMS if not s.default)
                      if any(not s.default for s in SYSTEMS) else "")
                   + ". DeepRead extract runs on DeepRead's own "
                   "OCR engine (pipeline=extract-selfhost), the engine the published numbers come from. Keys are read "
                   "from the environment (DEEPREAD_API_KEY, REDUCTO_API_KEY, EXTEND_API_KEY, VISION_AGENT_API_KEY); "
                   "DocILE needs your own token from https://docile.rossum.ai (DOCILE_TOKEN or `drbench fetch docile "
                   "--token`).",
        )
        p.add_argument("--systems", help="comma-separated list, by id (reducto:extract) or provider (reducto); "
                       f"default: the {len(DEFAULT_SYSTEMS)} systems of the published table")
        p.add_argument("--yes", action="store_true", help="do not ask before spending")
        p.add_argument("--dry-run", action="store_true", help="print the plan and the cost estimate, send nothing")
        p.add_argument("-j", "--concurrency", type=int, default=4, help="documents in flight per system (default 4)")
        p.add_argument("--retries", type=int, default=3)
        p.add_argument("--labels", default="official", choices=["official", "corrected"],
                       help="answer keys to grade against (default: the benchmarks' official labels)")
        p.set_defaults(plan=plan)

    args = parser.parse_args(argv)
    if args.command in ("short-run", "full-run"):
        from .suite import sweep, systems_for

        return sweep(args.plan, systems_for(args.systems), args.data, args.runs, yes=args.yes,
                     dry_run=args.dry_run, concurrency=args.concurrency, retries=args.retries,
                     labels=args.labels)
    if args.command == "fetch":
        DATASETS[args.dataset].fetch(args.data, token=args.token, source=args.source, workers=args.workers)
    elif args.command == "run":
        from .runner import run

        dataset = DATASETS[args.dataset]
        docs = select(dataset.docs(args.data), args.ids)
        if args.limit:
            docs = docs[: args.limit]
        counts = run(dataset, make(args.system), docs, args.runs, concurrency=args.concurrency,
                     retries=args.retries, force=args.force, retry_failures=args.retry_failures)
        if counts.get("stopped"):
            return 1  # so a chain of commands halts here instead of running on
    elif args.command == "grade":
        from .score import score

        dataset = DATASETS[args.dataset]
        docs = select(dataset.docs(args.data, args.labels), args.ids)
        result = score(dataset, docs, args.runs, args.labels, args.system, sample=args.ids)
        from .report import table

        print()
        print(table(dataset, result))
    elif args.command == "report":
        from .report import report

        print(report(args.runs, args.dataset, args.labels))
    return 0


def select(docs: list, ids_file: Path | None) -> list:
    """The documents named in `ids_file` (one id per line, `#` comments), in that
    order; every document of the dataset when there is no file."""
    if ids_file is None:
        return docs
    wanted = [line.strip() for line in ids_file.read_text().splitlines()]
    wanted = [w for w in wanted if w and not w.startswith("#")]
    by_id = {doc.id: doc for doc in docs}
    missing = [w for w in wanted if w not in by_id]
    if missing:
        sys.exit(f"{ids_file}: {len(missing)} id(s) not in the dataset, e.g. {missing[0]!r}")
    return [by_id[w] for w in wanted]


if __name__ == "__main__":
    sys.exit(main())
