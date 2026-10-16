"""`drbench short-run` and `drbench full-run`: our comparison, reproduced end to end.

One command downloads the datasets, sends the same documents through every
system of the published comparison, grades the outputs and prints the table.
The **short run** is exactly
the run behind our published numbers: all 500 DocILE validation documents, the
first 40 Kleister-Charity documents and the 20 shortest LongExtractBench
documents, 2,614 pages per system. The **full run** is every document of the
three benchmarks, 30,803 pages per system. Both print what they will cost at
list price and ask before spending anything.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from . import repo_root
from .datasets import DATASETS, Doc
from .providers import Provider, make


@dataclass(frozen=True)
class System:
    id: str  # `<provider>:<mode>`, what `drbench run --system` takes
    label: str  # how the table names it
    env_key: str
    price_per_page: float  # list price in USD, October 2026 (docs/providers.md)
    default: bool = True  # part of the published comparison, so run unless --systems says otherwise


# The systems of the published comparison, in table order, plus the ones a
# `--systems` can add. DeepRead extract runs on DeepRead's own OCR engine
# (`pipeline=extract-selfhost`), the engine the published numbers come from.
# Prices are what each vendor listed in October 2026; DeepRead's is its list
# price too, paid in credits.
SYSTEMS: tuple[System, ...] = (
    System("deepread:extract-selfhost", "DeepRead extract", "DEEPREAD_API_KEY", 0.015),
    System("deepread:deep-extract", "DeepRead deep-extract", "DEEPREAD_API_KEY", 0.035),
    System("reducto:extract", "Reducto Extract", "REDUCTO_API_KEY", 0.020),
    System("reducto:deep-extract", "Reducto Deep Extract", "REDUCTO_API_KEY", 0.040),
    System("extend:performance", "Extend Performance", "EXTEND_API_KEY", 0.0625),
    System("extend:operator", "Extend Operator", "EXTEND_API_KEY", 0.0875),
    System("landingai:dpt-3-pro", "LandingAI ADE", "VISION_AGENT_API_KEY", 0.061),
)
DEFAULT_SYSTEMS: tuple[System, ...] = tuple(s for s in SYSTEMS if s.default)

KEY_SOURCES = {
    "DEEPREAD_API_KEY": "https://app.deepread.tech (dashboard → API keys)",
    "REDUCTO_API_KEY": "https://studio.reducto.ai (API Keys)",
    "EXTEND_API_KEY": "https://dashboard.extend.ai (Settings → API keys)",
    "VISION_AGENT_API_KEY": "https://ade.landing.ai (Settings → API key)",
}


@dataclass(frozen=True)
class Part:
    """One benchmark's share of a run: which documents, and how many pages they are."""

    dataset: str
    ids: Path | None  # document list relative to the repository; None = every document
    documents: int
    pages: int  # counted from the PDFs (pypdf), so the estimate works before anything is downloaded

    @property
    def title(self) -> str:
        return DATASETS[self.dataset].title.split(" (")[0]


PLANS: dict[str, tuple[Part, ...]] = {
    # The run behind the published numbers: chosen before any system was run,
    # identical for every system. DocILE = the whole validation split; Charity =
    # the first 40 documents in the dataset's own order; LongExtract = the 20
    # shortest of the 50 by page count (the other 30 are 18,693 pages).
    "short": (
        Part("docile", None, 500, 636),
        Part("charity", Path("datasets/charity/sample-40.txt"), 40, 1_143),
        Part("longextract", Path("datasets/longextract/sample-20.txt"), 20, 835),
    ),
    # Every document of the three benchmarks.
    "full": (
        Part("docile", None, 500, 636),
        Part("charity", None, 440, 10_639),
        Part("longextract", None, 50, 19_528),
    ),
}


def pages(plan: str) -> int:
    return sum(part.pages for part in PLANS[plan])


def systems_for(spec: str | None) -> list[System]:
    """`--systems`: a comma-separated list by id (`reducto:extract`) or by
    provider (`reducto` = every Reducto mode, `deepread` = both DeepRead
    pipelines); the published six when not given."""
    if not spec:
        return list(DEFAULT_SYSTEMS)
    chosen: list[System] = []
    for token in (t.strip() for t in spec.split(",") if t.strip()):
        matches = [s for s in SYSTEMS if s.id == token or s.id.split(":")[0] == token]
        if not matches:
            sys.exit(f"unknown system {token!r}; choose from: " + ", ".join(s.id for s in SYSTEMS))
        chosen += [s for s in matches if s not in chosen]
    return chosen


def estimate(plan: str, systems: list[System]) -> list[tuple[System, float]]:
    """What each system costs at list price for every page of the plan."""
    total_pages = pages(plan)
    return [(s, s.price_per_page * total_pages) for s in systems]


def cost_table(plan: str, systems: list[System]) -> str:
    rows = estimate(plan, systems)
    total_pages = pages(plan)
    lines = [f"| System | $ / 1k pages | {total_pages:,} pages |", "|---|---:|---:|"]
    for s, cost in rows:
        per_1k = f"{1000 * s.price_per_page:.2f}".rstrip("0").rstrip(".")
        lines.append(f"| {s.label} | ${per_1k} | ${cost:,.0f} |")
    lines.append(f"| **Total** | | **${sum(c for _, c in rows):,.0f}** |")
    return "\n".join(lines)


def missing_keys(systems: list[System]) -> list[str]:
    return sorted({s.env_key for s in systems if not os.environ.get(s.env_key)})


def describe(plan: str, systems: list[System]) -> str:
    """The plan and its price, printed before anything is sent."""
    parts = PLANS[plan]
    lines = [f"{plan} run: {len(systems)} system(s) × {pages(plan):,} pages each", ""]
    for part in parts:
        which = f"the {part.documents} documents in {part.ids}" if part.ids else f"all {part.documents} documents"
        lines.append(f"  {part.title}: {which} ({part.pages:,} pages)")
    lines += ["", "Cost at list price, October 2026 (vendors bill their accounts; DeepRead uses your credits):", ""]
    lines.append(cost_table(plan, systems))
    return "\n".join(lines)


def sweep(
    plan: str,
    systems: list[System],
    data_dir: Path,
    runs_dir: Path,
    *,
    yes: bool = False,
    dry_run: bool = False,
    concurrency: int = 4,
    retries: int = 3,
    labels: str = "official",
    ask=input,
) -> int:
    """fetch → run → grade → report over every part of the plan and every system.

    Resumable: a document that already has an output under `runs/` is not sent
    again, so the same command continues an interrupted run. A system whose key
    is rejected or whose account runs out of credit is stopped and reported; the
    others carry on.
    """
    from .report import summary
    from .runner import run
    from .score import score

    print(describe(plan, systems))
    print()
    if dry_run:
        print("dry run: nothing was sent.")
        return 0
    missing = missing_keys(systems)
    if missing:
        wanted = "\n".join(f"  export {k}=...    # {KEY_SOURCES[k]}" for k in missing)
        sys.exit(f"missing API key(s) — set them in the environment, then rerun:\n{wanted}\n"
                 "(or pass --systems to run only the systems you have keys for)")
    if not yes:
        answer = ask("Send these documents to the systems above and spend the amounts listed? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("aborted: nothing was sent.")
            return 1

    skipped: list[str] = []
    stopped: list[str] = []
    graded: list[Part] = []
    for part in PLANS[plan]:
        dataset = DATASETS[part.dataset]
        docs = _documents(part, data_dir)
        if docs is None:
            skipped.append(part.title)
            continue
        providers = [make(s.id) for s in systems]
        for provider in providers:
            print()
            counts = run(dataset, provider, docs, runs_dir, concurrency=concurrency, retries=retries)
            if counts.get("stopped"):
                stopped.append(f"{part.title} × {provider.name}")
        print()
        score(dataset, _for_grading(part, data_dir, labels, docs), runs_dir, labels,
              [p.name for p in providers], sample=part.ids)
        graded.append(part)

    print()
    print(summary(runs_dir, graded, systems, labels))
    if skipped:
        print(f"\nnot run: {', '.join(skipped)} (see the message above)")
    if stopped:
        print("\nstopped before every document was sent (fix the account, then rerun the same command):")
        print("\n".join(f"  {s}" for s in stopped))
    return 1 if stopped else 0


def _documents(part: Part, data_dir: Path, labels: str = "official") -> list[Doc] | None:
    """The part's documents, downloading the dataset first when it is missing.
    DocILE cannot be downloaded for you (its terms forbid redistribution), so
    without a token it is explained and skipped rather than failing the run."""
    from .cli import select

    dataset = DATASETS[part.dataset]
    try:
        docs = dataset.docs(data_dir, labels)
    except FileNotFoundError:
        if part.dataset == "docile":
            token = os.environ.get("DOCILE_TOKEN")
            if not token:
                print(
                    "DocILE is not downloaded. Its terms (non-commercial research, no redistribution) mean\n"
                    "you fetch it yourself: request a free token at https://docile.rossum.ai, then either\n"
                    "  export DOCILE_TOKEN=<token>   and rerun this command, or\n"
                    "  drbench fetch docile --token <token>   first.\n"
                    "Continuing with the other benchmarks.",
                    file=sys.stderr,
                )
                return None
            dataset.fetch(data_dir, token=token)
        else:
            dataset.fetch(data_dir)
        docs = dataset.docs(data_dir, labels)
    ids = repo_root() / part.ids if part.ids else None
    docs = select(docs, ids)
    if len(docs) != part.documents:
        sys.exit(f"{part.title}: expected {part.documents} documents, found {len(docs)}")
    return docs


def _for_grading(part: Part, data_dir: Path, labels: str, docs: list[Doc]) -> list[Doc]:
    """The same documents with the chosen answer keys; a benchmark without a
    corrected label set (LongExtractBench) is graded on its official one."""
    if labels == "official":
        return docs
    try:
        return _documents(part, data_dir, labels) or docs
    except ValueError:
        return docs


def provider_name(system: System) -> str:
    """The run-directory name of a system, e.g. `reducto-deep-extract`."""
    provider: Provider = make(system.id)
    return provider.name
