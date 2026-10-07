"""Kleister-Charity, dev-0 split: 440 UK charity annual reports, 8 fields.

Source: https://github.com/applicaai/kleister-charity at commit 2309f486
(2021-08-18, the latest). The document list (`dev-0/in.tsv.xz`) and labels
(`dev-0/expected.tsv`) come from that repo; the PDFs are git-annex objects in
Applica's public S3 bucket and are downloaded from there directly, so git-annex
is not required. `test-A` labels were never released and the scoring server
(gonito.net) is offline, so dev-0 is the largest split anyone can score.

Metric: the benchmark's own one, MultiLabel-F1 over upper-cased `field=value`
labels ("F1 (UC)" in the Kleister `config.txt`), computed over all 440 documents
(a document the system failed contributes only misses). Values are normalised
the way the Kleister README prescribes before comparison: spaces as `_`, dates
as YYYY-MM-DD, money as a number with two decimals. The implementation here is
checked against GEval 1.14.2.0 output in tests/test_charity.py.
"""

from __future__ import annotations

import concurrent.futures as cf
import json
import lzma
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from .. import repo_root
from .base import Column, Doc

REPO_URL = "https://github.com/applicaai/kleister-charity"
COMMIT = "2309f4861cc49864ac653a7fa108efc2144400b3"
S3_PREFIX = "https://applica-public.s3-eu-west-1.amazonaws.com/kleister-charity-git-annex/"
SPARSE_PATHS = ("/config.txt", "/in-header.tsv", "/README.md", "/dev-0/expected.tsv", "/dev-0/in.tsv.xz", "/documents/")

FIELDS = (
    "address__post_town",
    "address__postcode",
    "address__street_line",
    "charity_name",
    "charity_number",
    "income_annually_in_british_pounds",
    "report_date",
    "spending_annually_in_british_pounds",
)
MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}


# --- value normalisation (Kleister README rules) -------------------------------------


def iso_date(value: Any) -> str | None:
    s = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", s)  # UK documents: day first
    if m:
        d, mo, y = map(int, m.groups())
        return _date(y, mo, d)
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3})[a-z]*\.?,?\s+(\d{4})", s)
    if m and m.group(2).lower() in MONTHS:
        return _date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
    m = re.fullmatch(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", s)
    if m and m.group(1).lower() in MONTHS:
        return _date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2)))
    return None


def _date(y: int, mo: int, d: int) -> str | None:
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def money(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return f"{float(value):.2f}"
    s = re.sub(r"[£,\s]", "", str(value))
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        x = float(s)
    except ValueError:
        return None
    return f"{-x if negative else x:.2f}"


def normalise(field: str, value: Any) -> str | None:
    if value in (None, "", [], {}):
        return None
    if isinstance(value, dict):  # a wrapped value some APIs return
        return normalise(field, value.get("value"))
    if isinstance(value, list):
        value = value[0] if value else None
        return normalise(field, value)
    if "date" in field:
        out = iso_date(value)
    elif field.endswith("_in_british_pounds"):
        out = money(value)
    else:
        out = " ".join(str(value).split())
    return out.replace(" ", "_") if out else None


def to_labels(result: dict) -> list[str]:
    """A system's extraction as Kleister `field=value` labels."""
    labels = []
    for field in FIELDS:
        value = normalise(field, result.get(field))
        if value:
            labels.append(f"{field}={value}")
    return labels


# --- scoring: MultiLabel-F1 as GEval computes it -------------------------------------


def grade_labels(pred: list[str], expected: list[str]) -> dict:
    """Per-document counts; the aggregate pools them over all documents."""
    p, e = set(pred), set(expected)
    pu, eu = {x.upper() for x in p}, {x.upper() for x in e}
    out: dict[str, Any] = {
        "tp_uc": len(pu & eu), "fp_uc": len(pu - eu), "fn_uc": len(eu - pu),
        "tp": len(p & e), "fp": len(p - e), "fn": len(e - p),
        "exact": sorted(pu) == sorted(eu),
        "doc_f1_uc": _f1(len(pu & eu), len(pu - eu), len(eu - pu)),
        "fields": {},
    }
    for field in FIELDS:
        prefix = f"{field.upper()}="
        pf = {x for x in pu if x.startswith(prefix)}
        ef = {x for x in eu if x.startswith(prefix)}
        out["fields"][field] = {"tp": len(pf & ef), "fp": len(pf - ef), "fn": len(ef - pf)}
    return out


def _f1(tp: int, fp: int, fn: int) -> float:
    denominator = 2 * tp + fp + fn
    return 1.0 if denominator == 0 else 2 * tp / denominator


def _prf(tp: int, fp: int, fn: int) -> dict:
    return {
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "f1": _f1(tp, fp, fn),
    }


class Charity:
    name = "charity"
    title = "Kleister-Charity (dev-0, 440 documents)"
    columns = (
        Column("completed", "Completed", "int"),
        Column("f1_uc", "F1 (UC)"),
        Column("precision_uc", "Precision"),
        Column("recall_uc", "Recall"),
        Column("latency_p50", "Median latency", "seconds"),
    )

    # -- data ---------------------------------------------------------------------

    def fetch(self, data_dir: Path, workers: int = 8, **_: Any) -> None:
        root = data_dir / self.name
        repo = root / "kleister-charity"
        if not (repo / "dev-0" / "expected.tsv").is_file():
            root.mkdir(parents=True, exist_ok=True)
            print(f"cloning {REPO_URL} @ {COMMIT[:8]} (labels and document list only)")
            _git("clone", "--no-checkout", "--filter=blob:none", REPO_URL, str(repo))
            _git("-C", str(repo), "sparse-checkout", "set", "--no-cone", *SPARSE_PATHS)
            _git("-C", str(repo), "checkout", "--quiet", COMMIT)
        names = self._names(repo)
        pdfs = root / "pdfs"
        pdfs.mkdir(exist_ok=True)
        todo = [n for n in names if not _complete(pdfs / n, _annex_key(repo, n))]
        print(f"{len(names)} dev-0 documents, {len(names) - len(todo)} already present, fetching {len(todo)}")
        with httpx.Client(timeout=120, follow_redirects=True) as client, cf.ThreadPoolExecutor(workers) as pool:
            futures = {pool.submit(_download, client, _annex_key(repo, n), pdfs / n): n for n in todo}
            for i, future in enumerate(cf.as_completed(futures), 1):
                future.result()
                if i % 50 == 0 or i == len(todo):
                    print(f"  {i}/{len(todo)}", flush=True)
        print(f"ready: {pdfs}")

    def docs(self, data_dir: Path, labels: str = "official") -> list[Doc]:
        root = data_dir / self.name
        repo = root / "kleister-charity"
        names = self._names(repo)
        if labels == "official":
            expected = repo / "dev-0" / "expected.tsv"
        elif labels == "corrected":
            expected = repo_root() / "datasets" / "charity" / "errata" / "dev-0.expected.corrected.tsv"
        else:
            raise ValueError(f"unknown labels {labels!r}; use official or corrected")
        lines = expected.read_text().splitlines()
        if len(lines) != len(names):
            raise RuntimeError(f"{expected}: {len(lines)} lines for {len(names)} documents")
        schema = json.loads((repo_root() / "datasets" / "charity" / "schema.json").read_text())
        return [
            Doc(id=name.removesuffix(".pdf"), pdf=root / "pdfs" / name, schema=schema, ground_truth=line.split())
            for name, line in zip(names, lines)
        ]

    @staticmethod
    def _names(repo: Path) -> list[str]:
        with lzma.open(repo / "dev-0" / "in.tsv.xz", "rt", encoding="utf-8") as f:
            return [line.split("\t", 1)[0] for line in f if line.strip()]

    # -- scoring ------------------------------------------------------------------

    def grade(self, pred: dict, ground_truth: list[str], schema: dict) -> dict:
        return grade_labels(to_labels(pred), ground_truth)

    def aggregate(self, per_doc: list[dict]) -> dict:
        tp_uc = sum(d["tp_uc"] for d in per_doc)
        fp_uc = sum(d["fp_uc"] for d in per_doc)
        fn_uc = sum(d["fn_uc"] for d in per_doc)
        tp = sum(d["tp"] for d in per_doc)
        fp = sum(d["fp"] for d in per_doc)
        fn = sum(d["fn"] for d in per_doc)
        uc = _prf(tp_uc, fp_uc, fn_uc)
        out = {
            "documents": len(per_doc),
            "f1_uc": uc["f1"],
            "precision_uc": uc["precision"],
            "recall_uc": uc["recall"],
            "f1": _prf(tp, fp, fn)["f1"],
            "mean_f1_uc": sum(d["doc_f1_uc"] for d in per_doc) / len(per_doc) if per_doc else 0.0,
            "accuracy_uc": sum(d["exact"] for d in per_doc) / len(per_doc) if per_doc else 0.0,
            "fields": {},
        }
        for field in FIELDS:
            counts = [d["fields"][field] for d in per_doc]
            out["fields"][field] = _prf(
                sum(c["tp"] for c in counts), sum(c["fp"] for c in counts), sum(c["fn"] for c in counts)
            )
        return out


# --- fetch helpers ---------------------------------------------------------------------


def _git(*args: str) -> None:
    subprocess.run(["git", *args], check=True)


def _annex_key(repo: Path, name: str) -> str:
    """`documents/<name>` is a git-annex symlink; the object key is the link's basename."""
    link = repo / "documents" / name
    target = os.readlink(link) if link.is_symlink() else link.read_text().strip()  # Windows: a text file
    return Path(target).name


def _annex_size(key: str) -> int | None:
    m = re.search(r"-s(\d+)-", key)
    return int(m.group(1)) if m else None


def _complete(path: Path, key: str) -> bool:
    size = _annex_size(key)
    return path.is_file() and (size is None or path.stat().st_size == size)


def _download(client: httpx.Client, key: str, dst: Path) -> None:
    tmp = dst.with_suffix(".tmp")
    for attempt in range(4):
        try:
            with client.stream("GET", S3_PREFIX + key) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_bytes(1 << 16):
                        f.write(chunk)
            if _complete(tmp, key):
                tmp.replace(dst)
                return
        except httpx.HTTPError as e:
            print(f"  retry {dst.name}: {e}", file=sys.stderr)
    raise RuntimeError(f"could not download {dst.name}")
