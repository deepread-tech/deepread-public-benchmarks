"""LongExtractBench, public subset: 50 long, table-heavy documents (22 to 11,622
pages, median 86) with one JSON Schema and one answer key each.

Source: https://huggingface.co/datasets/micro1-inc/longextract-bench-50, labels
CC-BY-4.0 by micro1 (the PDFs are public documents that keep their own rights),
revision d4ca332f. `drbench fetch longextract` downloads DeepRead's byte-identical
mirror of that revision, https://huggingface.co/datasets/deepread-tech/longextract-bench-50
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

from ..graders.longextract_grading import _collapse, grade, unwrap
from .base import Column, Doc

HF_REPO = "deepread-tech/longextract-bench-50"
HF_REVISION: str | None = None  # pinned to a commit once the mirror is uploaded
UPSTREAM = "micro1-inc/longextract-bench-50"
UPSTREAM_REVISION = "d4ca332f72f6d3649ecd11b69445a8f4ef5fcb02"


class LongExtract:
    name = "longextract"
    title = "LongExtractBench (public subset, 50 documents)"
    columns = (
        Column("completed", "Completed", "int"),
        Column("row_precision", "Row precision"),
        Column("row_recall", "Row recall"),
        Column("leaf_accuracy", "Leaf accuracy"),
        Column("latency_p50", "Median latency", "seconds"),
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
        scores = grade(_collapse(pred), gt, schema)
        return {
            "row_precision": scores["precision"],
            "row_recall": scores["recall"],
            "leaf_accuracy": scores["leaf_accuracy"] / 100,
            "gt_rows": scores["gt_rows"],
            "pred_rows": scores["pred_rows"],
            "matched_rows": scores["matched"],
            "leaf_total": scores["leaf_total"],
            "leaf_match": scores["leaf_match"],
        }

    def aggregate(self, per_doc: list[dict]) -> dict:
        done = [d for d in per_doc if d.get("state") == "success"]
        mean = lambda key: sum(d[key] for d in done) / len(done) if done else 0.0  # noqa: E731
        return {
            "documents": len(per_doc),
            "row_precision": mean("row_precision"),
            "row_recall": mean("row_recall"),
            "leaf_accuracy": mean("leaf_accuracy"),
        }
