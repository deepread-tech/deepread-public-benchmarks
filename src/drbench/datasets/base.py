from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class Doc:
    id: str  # stable identifier; also the stem of the output file
    pdf: Path
    schema: dict
    ground_truth: Any  # dataset-specific; only that dataset's grader reads it


class Dataset(Protocol):
    name: str  # used on the command line and as the run directory name
    title: str  # heading of the dataset's results table
    short: str  # column header in the summary table

    def fetch(self, data_dir: Path, **opts: Any) -> None: ...

    def docs(self, data_dir: Path, labels: str = "official") -> list[Doc]: ...

    def grade(self, pred: dict, ground_truth: Any, schema: dict) -> dict: ...

    def aggregate(self, per_doc: list[dict]) -> dict:
        """Per-document grades → the dataset's metrics; `score` is the headline (0..1)."""
