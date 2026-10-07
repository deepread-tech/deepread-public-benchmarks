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


@dataclass(frozen=True)
class Column:
    key: str  # key in the aggregate dict
    label: str  # table header
    kind: str = "pct"  # pct | int | seconds


class Dataset(Protocol):
    name: str
    title: str
    columns: tuple[Column, ...]  # what the leaderboard shows, in order

    def fetch(self, data_dir: Path, **opts: Any) -> None: ...

    def docs(self, data_dir: Path, labels: str = "official") -> list[Doc]: ...

    def grade(self, pred: dict, ground_truth: Any, schema: dict) -> dict: ...

    def aggregate(self, per_doc: list[dict]) -> dict: ...
