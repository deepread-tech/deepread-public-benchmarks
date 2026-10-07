"""Grade saved outputs: `<runs>/<dataset>/<system>/*.json` → `<runs>/<dataset>/scores.json`.

Offline and deterministic: the same outputs always give the same scores. One
`scores.json` per label set (`scores.json` for the official labels,
`scores.corrected.json` for the errata-corrected ones).
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from . import envelope
from .datasets import Dataset, Doc


def score(dataset: Dataset, docs: list[Doc], runs_dir: Path, labels: str = "official",
          systems: list[str] | None = None) -> dict:
    base = runs_dir / dataset.name
    found = sorted(p.name for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
    systems = systems or found
    out: dict = {
        "dataset": dataset.name,
        "labels": labels,
        "documents": len(docs),
        "graded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "systems": {},
    }
    for system in systems:
        per_doc: dict[str, dict] = {}
        for doc in docs:
            env = envelope.read(base / system / f"{doc.id}.json")
            state, reason = envelope.classify(env)
            pred = env["result"] if state == "success" else {}
            scores = dataset.grade(pred, doc.ground_truth, doc.schema)
            scores["state"] = state
            if reason:
                scores["reason"] = reason
            if env is not None:
                scores["latency_s"] = (env.get("_meta") or {}).get("latency_s")
            per_doc[doc.id] = scores
        summary = dataset.aggregate(list(per_doc.values()))
        summary["completed"] = sum(1 for d in per_doc.values() if d["state"] == "success")
        summary["failed"] = len(per_doc) - summary["completed"]
        latencies = [d["latency_s"] for d in per_doc.values() if d["state"] == "success" and d.get("latency_s")]
        summary["latency_p50"] = statistics.median(latencies) if latencies else None
        summary["latency_mean"] = statistics.fmean(latencies) if latencies else None
        summary["failure_reasons"] = _tally(d.get("reason") for d in per_doc.values() if d["state"] == "failure")
        out["systems"][system] = {"summary": summary, "docs": per_doc}
    path = base / ("scores.json" if labels == "official" else f"scores.{labels}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"wrote {path}")
    return out


def _tally(reasons) -> dict[str, int]:
    counts: dict[str, int] = {}
    for reason in reasons:
        key = (reason or "unknown").split("\n")[0][:80]
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
