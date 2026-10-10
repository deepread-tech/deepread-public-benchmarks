"""Grade saved outputs: `<runs>/<dataset>/<system>/*.json` → `<runs>/<dataset>/scores.json`.

Offline and deterministic: the same outputs always give the same scores. One
`scores.json` per label set (`scores.json` for the official labels,
`scores.corrected.json` for the errata-corrected ones).

Besides the dataset's metrics, every system gets its price per 1,000 pages on
the documents it completed: each document's cost under `drbench/systems.py`
(list price × pages, or the credits the vendor reported × the credit price),
summed and divided by the pages. Page counts are read from the PDFs and kept in
`<runs>/<dataset>/pages.json`.
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import logging

from pypdf import PdfReader

from . import envelope
from .datasets import Dataset, Doc
from .systems import SYSTEMS

logging.getLogger("pypdf").setLevel(logging.ERROR)  # malformed-but-readable PDFs are common


def score(dataset: Dataset, docs: list[Doc], runs_dir: Path, labels: str = "official",
          systems: list[str] | None = None) -> dict:
    base = runs_dir / dataset.name
    found = sorted(p.name for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
    pages = page_counts(docs, base / "pages.json")
    out: dict = {
        "dataset": dataset.name,
        "labels": labels,
        "documents": len(docs),
        "pages": sum(pages.values()),
        "graded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "systems": {},
    }
    for system in systems or found:
        per_doc: dict[str, dict] = {}
        for doc in docs:
            env = envelope.read(base / system / f"{doc.id}.json")
            state, reason = envelope.classify(env)
            grades = dataset.grade(env["result"] if state == "success" else {}, doc.ground_truth, doc.schema)
            meta = (env or {}).get("_meta") or {}
            usage = meta.get("usage") or {}
            grades.update(state=state, pages=pages[doc.id], latency_s=meta.get("latency_s"), credits=usage.get("credits"))
            if reason:
                grades["reason"] = reason
            per_doc[doc.id] = grades
        summary = dataset.aggregate(list(per_doc.values()))
        summary.update(_operations(system, per_doc))
        out["systems"][system] = {"summary": summary, "docs": per_doc}
    path = base / ("scores.json" if labels == "official" else f"scores.{labels}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"wrote {path}")
    return out


def _operations(system: str, per_doc: dict[str, dict]) -> dict:
    """Completed count, price per 1,000 pages and latency, over completed documents."""
    done = [d for d in per_doc.values() if d["state"] == "success"]
    price = SYSTEMS[system].price if system in SYSTEMS else None
    costed = [(price.cost(d["pages"], d["credits"]), d["pages"]) for d in done] if price else []
    costed = [(c, p) for c, p in costed if c is not None and p]
    latencies = [d["latency_s"] for d in done if d.get("latency_s")]
    cost, costed_pages = sum(c for c, _ in costed), sum(p for _, p in costed)
    return {
        "completed": len(done),
        "failed": len(per_doc) - len(done),
        "cost_usd": cost if costed else None,
        "costed_pages": costed_pages,
        "usd_per_1k_pages": 1000 * cost / costed_pages if costed else None,
        "latency_p50": statistics.median(latencies) if latencies else None,
        "failure_reasons": _tally(d.get("reason") for d in per_doc.values() if d["state"] == "failure"),
    }


def page_counts(docs: list[Doc], cache: Path) -> dict[str, int]:
    counts = json.loads(cache.read_text()) if cache.is_file() else {}
    missing = [d for d in docs if d.id not in counts]
    for doc in missing:
        counts[doc.id] = len(PdfReader(doc.pdf).pages)
    if missing:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(dict(sorted(counts.items())), indent=1))
    return {d.id: counts[d.id] for d in docs}


def _tally(reasons) -> dict[str, int]:
    counts: dict[str, int] = {}
    for reason in reasons:
        key = (reason or "unknown").split("\n")[0][:80]
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
