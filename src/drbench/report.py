"""Results tables (Markdown) from the `scores.json` files.

`summary` is the table at the top of the README: one row per system, its score
on each benchmark, and its price per 1,000 pages over every page it processed.
`detail` is one table per benchmark with completion, price and latency.
`write_readme` puts the summary between the README's results markers, so the
published table is always regenerated from `runs/`, never typed by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

from .datasets import DATASETS
from .systems import PRICES_CHECKED, SYSTEMS

BEGIN, END = "<!-- results:begin -->", "<!-- results:end -->"


def load(runs_dir: Path, labels: str = "official") -> dict[str, dict]:
    name = "scores.json" if labels == "official" else f"scores.{labels}.json"
    return {
        dataset: json.loads((runs_dir / dataset / name).read_text())
        for dataset in DATASETS
        if (runs_dir / dataset / name).is_file()
    }


def summary(scores: dict[str, dict]) -> str:
    datasets = list(scores)
    systems = [s for s in SYSTEMS if any(s in scores[d]["systems"] for d in datasets)]
    header = ["System", *(DATASETS[d].short for d in datasets), "Price per 1,000 pages"]
    lines = ["| " + " | ".join(header) + " |", "|---|" + "---:|" * (len(header) - 1)]
    for system in systems:
        cells = []
        cost = pages = 0.0
        for d in datasets:
            s = scores[d]["systems"].get(system, {}).get("summary")
            if s is None:
                cells.append("not run")
                continue
            done = "" if not s["failed"] else f" ({s['completed']}/{s['completed'] + s['failed']} docs)"
            cells.append(f"{100 * s['score']:.1f}{done}")
            if s.get("cost_usd") is not None:
                cost, pages = cost + s["cost_usd"], pages + s["costed_pages"]
        info = SYSTEMS[system]
        price = f"${1000 * cost / pages:.2f}" if pages else "–"
        lines.append(f"| {info.vendor} {info.product} | " + " | ".join(cells) + f" | {price} |")
    return "\n".join(lines)


def detail(dataset: str, scores: dict) -> str:
    total = scores["documents"]
    labels = "" if scores.get("labels", "official") == "official" else f" — {scores['labels']} labels"
    lines = [
        f"### {DATASETS[dataset].title}{labels}",
        "",
        "| System | Score (F1) | Precision | Recall | Documents completed | Price per 1,000 pages | Median time per document |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    ranked = sorted(scores["systems"].items(), key=lambda kv: -kv[1]["summary"]["score"])
    for system, data in ranked:
        s = data["summary"]
        price = "–" if s.get("usd_per_1k_pages") is None else f"${s['usd_per_1k_pages']:.2f}"
        latency = "–" if s.get("latency_p50") is None else f"{s['latency_p50']:.0f} s"
        lines.append(
            f"| {system} | {_pct(s['score'])} | {_pct(s.get('precision'))} | {_pct(s.get('recall'))} "
            f"| {s['completed']}/{total} | {price} | {latency} |"
        )
    failures = {system: d["summary"].get("failure_reasons") for system, d in ranked}
    if any(failures.values()):
        lines += ["", "Failures:"]
        for system, reasons in failures.items():
            if reasons:
                lines.append(f"- {system}: " + "; ".join(f"{n} × {r}" for r, n in reasons.items()))
    return "\n".join(lines)


def write_readme(readme: Path, scores: dict[str, dict]) -> None:
    text = readme.read_text()
    if BEGIN not in text or END not in text:
        raise SystemExit(f"{readme}: no {BEGIN} … {END} markers")
    graded = max(s["graded_at"][:10] for s in scores.values())
    block = f"{BEGIN}\n{summary(scores)}\n\nGraded {graded}; prices checked {PRICES_CHECKED}.\n{END}"
    head, rest = text.split(BEGIN, 1)
    readme.write_text(head + block + rest.split(END, 1)[1])
    print(f"updated {readme}")


def _pct(value: float | None) -> str:
    return "–" if value is None else f"{100 * value:.1f}%"
