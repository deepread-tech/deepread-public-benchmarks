"""Leaderboard tables (Markdown) from `scores.json` files."""

from __future__ import annotations

import json
from pathlib import Path

from .datasets import DATASETS, Column, Dataset


def report(runs_dir: Path, datasets: list[str] | None = None, labels: str = "official") -> str:
    blocks = []
    for name in datasets or list(DATASETS):
        dataset = DATASETS[name]
        path = runs_dir / name / ("scores.json" if labels == "official" else f"scores.{labels}.json")
        if not path.is_file():
            continue
        blocks.append(table(dataset, json.loads(path.read_text())))
    return "\n\n".join(blocks) if blocks else "no scores found — run `drbench grade` first"


def table(dataset: Dataset, scores: dict) -> str:
    label_note = "" if scores.get("labels", "official") == "official" else f" — {scores['labels']} labels"
    lines = [f"### {dataset.title}{label_note}", ""]
    lines.append("| System | " + " | ".join(c.label for c in dataset.columns) + " |")
    lines.append("|---|" + "|".join("---:" for _ in dataset.columns) + "|")
    ranked = sorted(scores["systems"].items(), key=lambda kv: -(kv[1]["summary"].get("accuracy") or 0))
    total = scores.get("documents")
    for system, data in ranked:
        summary = data["summary"]
        cells = [_fmt(summary.get(c.key), c, total) for c in dataset.columns]
        lines.append(f"| {system} | " + " | ".join(cells) + " |")
    failures = {s: d["summary"].get("failure_reasons") or {} for s, d in ranked}
    if any(failures.values()):
        lines += ["", "Failures:"]
        for system, reasons in failures.items():
            if reasons:
                lines.append(f"- {system}: " + "; ".join(f"{n} × {r}" for r, n in reasons.items()))
    return "\n".join(lines)


def _fmt(value, column: Column, total: int | None) -> str:
    if value is None:
        return "–"
    if column.kind == "int":
        return f"{value}/{total}" if total else str(value)
    if column.kind == "seconds":
        return f"{value:.0f} s"
    return f"{100 * value:.1f}%"
