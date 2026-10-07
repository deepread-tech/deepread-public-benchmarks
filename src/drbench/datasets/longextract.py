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

Metric: the benchmark's own grader, vendored unmodified. Rows of the schema's
top-level arrays are paired by an inferred key, then precision and recall count
matched rows; leaf accuracy is the share of exactly-right values on matched rows
and document-level fields. As on micro1's leaderboard, these are averaged over
the documents a system completed, with the completed count shown beside them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..graders.longextract_grading import _arrays, _collapse, _count_leaves, _match_rows, grade, infer_row_key, unwrap
from .base import Column, Doc

HF_REPO = "DeepRead/longextract-bench-50"
HF_REVISION = "49e8894fb9409ed7ba0b6fd97c35cf0d26819839"  # mirror uploaded 2026-10-07
UPSTREAM = "micro1-inc/longextract-bench-50"
UPSTREAM_REVISION = "d4ca332f72f6d3649ecd11b69445a8f4ef5fcb02"


class LongExtract:
    name = "longextract"
    title = "LongExtractBench (public subset, 50 documents)"
    columns = (
        Column("accuracy", "Accuracy"),
        Column("completed", "Documents completed", "int"),
    )

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
        scores = grade(pred, gt, schema)
        # micro1's leaf accuracy covers only the rows the system matched; the headline
        # also charges every value of the answer-key rows it missed, so it reads as
        # "answer-key values the system got right" like the other two benchmarks.
        missed = 0
        for arr in _arrays(schema):
            g = [r for r in (gt.get(arr, []) or []) if isinstance(r, dict)]
            p = [r for r in (pred.get(arr, []) or []) if isinstance(r, dict)]
            if g:
                _pairs, _unmatched_pred, unmatched_gt = _match_rows(p, g, infer_row_key(p, g))
                missed += sum(_count_leaves(row) for row in unmatched_gt)
        total = scores["leaf_total"] + missed
        return {
            "accuracy": scores["leaf_match"] / total if total else 0.0,
            "row_precision": scores["precision"],
            "row_recall": scores["recall"],
            "leaf_accuracy": scores["leaf_accuracy"] / 100,
            "gt_rows": scores["gt_rows"],
            "pred_rows": scores["pred_rows"],
            "matched_rows": scores["matched"],
            "leaf_total": scores["leaf_total"],
            "leaf_match": scores["leaf_match"],
            "missed_row_leaves": missed,
        }

    def aggregate(self, per_doc: list[dict]) -> dict:
        done = [d for d in per_doc if d.get("state") == "success"]
        mean_done = lambda key: sum(d[key] for d in done) / len(done) if done else 0.0  # noqa: E731
        return {
            "documents": len(per_doc),
            # the headline: per-document accuracy averaged over all 50 documents, a failed one counting 0
            "accuracy": sum(d["accuracy"] for d in per_doc) / len(per_doc) if per_doc else 0.0,
            # micro1's three numbers, over completed documents as on their leaderboard
            "row_precision": mean_done("row_precision"),
            "row_recall": mean_done("row_recall"),
            "leaf_accuracy": mean_done("leaf_accuracy"),
        }
