"""LongExtractBench, public subset: 50 long, table-heavy documents (22 to 11,622
pages, median 86) with one JSON Schema and one answer key each.

Source: https://huggingface.co/datasets/micro1-inc/longextract-bench-50, labels
CC-BY-4.0 by micro1 (the PDFs are public documents that keep their own rights),
revision d4ca332f. `drbench fetch longextract` downloads DeepRead's byte-identical
mirror of that revision, https://huggingface.co/datasets/DeepRead/longextract-bench-50
(built by `scripts/build_hf_datasets.py`). Benchmark and grader:
https://github.com/micro1-research/longextract-bench (MIT). The benchmark was
commissioned by Reducto and audited by micro1; the ground truth is model-drafted
and human-reconciled.

Metrics: micro1's grader, vendored unmodified, pairs the rows of each table with
the answer key and checks every value. The headline score is F1 over values:
2 × correct values ÷ (values the system returned + values in the answer key),
per document, averaged over all 50 documents with a failed document scoring 0.
micro1's own three numbers (row precision, row recall, leaf accuracy over
matched rows) are reported beside it, over completed documents as on micro1's
leaderboard.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from collections import Counter

from ..graders.longextract_grading import _arrays, _collapse, _match_rows, canonical, grade, infer_row_key, unwrap
from .base import Doc

HF_REPO = "DeepRead/longextract-bench-50"
HF_REVISION = "49e8894fb9409ed7ba0b6fd97c35cf0d26819839"  # mirror uploaded 2026-10-07
UPSTREAM = "micro1-inc/longextract-bench-50"
UPSTREAM_REVISION = "d4ca332f72f6d3649ecd11b69445a8f4ef5fcb02"


class LongExtract:
    name = "longextract"
    title = "LongExtractBench (public subset, 50 documents)"
    short = "LongExtractBench"

    def fetch(self, data_dir: Path, **_: Any) -> None:
        from huggingface_hub import snapshot_download

        local = data_dir / self.name
        print(f"downloading {HF_REPO} (mirror of {UPSTREAM} @ {UPSTREAM_REVISION[:8]}, ~360 MB)")
        snapshot_download(repo_id=HF_REPO, repo_type="dataset", revision=HF_REVISION, local_dir=str(local))
        print(f"ready: {local}")

    def docs(self, data_dir: Path, labels: str = "official") -> list[Doc]:
        if labels != "official":
            raise ValueError("longextract has no corrected label set")
        local = data_dir / self.name
        docs = []
        for folder in sorted(p for p in local.iterdir() if p.is_dir() and (p / "document.pdf").is_file()):
            docs.append(
                Doc(
                    id=folder.name,
                    pdf=folder / "document.pdf",
                    schema=json.loads((folder / "schema.json").read_text()),
                    ground_truth=json.loads((folder / "ground_truth.json").read_text()),
                )
            )
        if not docs:
            raise FileNotFoundError(f"no documents under {local} — run `drbench fetch longextract` first")
        return docs

    def grade(self, pred: dict, ground_truth: Any, schema: dict) -> dict:
        gt = _collapse(unwrap(ground_truth))
        gt = gt.get("result", gt) if isinstance(gt, dict) and "result" in gt and len(gt) == 1 else gt
        pred = _collapse(pred)
        pred = pred if isinstance(pred, dict) else {}
        micro1 = grade(pred, gt, schema)
        fields = set(_arrays(schema)) | set(gt) | set(pred)
        correct, returned, expected = _count({k: pred.get(k) for k in fields}, {k: gt.get(k) for k in fields})
        return {
            "score": 2 * correct / (returned + expected) if returned + expected else 0.0,
            "precision": correct / returned if returned else 0.0,
            "recall": correct / expected if expected else 0.0,
            "correct": correct,
            "returned": returned,
            "expected": expected,
            "row_precision": micro1["precision"],
            "row_recall": micro1["recall"],
            "leaf_accuracy": micro1["leaf_accuracy"] / 100,
        }

    def aggregate(self, per_doc: list[dict]) -> dict:
        done = [d for d in per_doc if d.get("state") == "success"]

        def mean(key: str, docs: list[dict]) -> float:
            return sum(d[key] for d in docs) / len(docs) if docs else 0.0

        return {
            "documents": len(per_doc),
            "score": mean("score", per_doc),  # the headline: every document counts, a failed one as 0
            "precision": mean("precision", per_doc),
            "recall": mean("recall", per_doc),
            "row_precision": mean("row_precision", done),  # micro1's numbers: completed documents only
            "row_recall": mean("row_recall", done),
            "leaf_accuracy": mean("leaf_accuracy", done),
        }


def _count(pv: Any, gv: Any) -> tuple[int, int, int]:
    """(correct, returned, expected) values, pairing rows exactly as micro1's grader
    does and comparing with its `canonical()`. A value counts only when it is not
    empty (None, "", or a placeholder such as "n/a"), so leaving a field empty is
    neither returned nor correct."""
    if isinstance(pv, dict) or isinstance(gv, dict):
        pv, gv = (pv if isinstance(pv, dict) else {}), (gv if isinstance(gv, dict) else {})
        return _sum(_count(pv.get(k), gv.get(k)) for k in set(pv) | set(gv))
    if isinstance(pv, list) or isinstance(gv, list):
        pv, gv = (pv if isinstance(pv, list) else []), (gv if isinstance(gv, list) else [])
        prows, grows = [x for x in pv if isinstance(x, dict)], [x for x in gv if isinstance(x, dict)]
        if prows or grows:
            pairs, extra, missed = _match_rows(prows, grows, infer_row_key(prows, grows))
            c, r, e = _sum(_count(p, g) for p, g in pairs)
            return c, r + sum(_count(row, None)[1] for row in extra), e + sum(_count(None, row)[2] for row in missed)
        cp = Counter(x for x in map(canonical, pv) if x)
        cg = Counter(x for x in map(canonical, gv) if x)
        return sum((cp & cg).values()), sum(cp.values()), sum(cg.values())
    p, g = canonical(pv), canonical(gv)
    return int(bool(p) and p == g), int(bool(p)), int(bool(g))


def _sum(triples) -> tuple[int, int, int]:
    c = r = e = 0
    for tc, tr, te in triples:
        c, r, e = c + tc, r + tr, e + te
    return c, r, e
