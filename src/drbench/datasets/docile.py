"""DocILE, validation split: 500 invoice-like business documents, 33 KILE fields.

Source: https://github.com/rossumai/docile (dataset v1.0). Access needs a free
token from https://docile.rossum.ai. The dataset terms allow non-commercial
research use only and forbid redistribution, so this repository ships no DocILE
documents and no labels: `drbench fetch docile --token ...` downloads the
annotated train+val archive with your token and keeps the 500 validation
documents; the ground truth is built from the official annotations on your
machine. `datasets/docile/val_docids.txt` pins the document list.

Headline: accuracy, the share of a document's answer-key values the system got
right, averaged over the documents; a document the system failed scores 0. Every
(document, field, value) in the official KILE annotations is one item; a
system's values for that field are matched after light normalisation
(whitespace and case, numeric amounts, dates to ISO, currency symbols to ISO
codes). Per-field precision, recall and F1 are reported as well. This is the
text half of DocILE's KILE metric;
the official scorer also requires the field's location on the page, which not
every API returns. For DeepRead, the location-aware official score is in
official/docile.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from .. import repo_root
from .base import Column, Doc

ARCHIVE_URL = "https://docile-dataset-rossum.s3.eu-west-1.amazonaws.com/{token}/annotated-trainval.zip"
SYMBOL_TO_CODE = {"$": "USD", "US$": "USD", "USD": "USD", "€": "EUR", "EUR": "EUR", "£": "GBP", "GBP": "GBP"}
MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}


# --- value normalisation --------------------------------------------------------------


def parse_number(s: str) -> float | None:
    t = re.sub(r"[^\d,.\-()]", "", s)
    if not re.search(r"\d", t):
        return None
    negative = t.startswith("(") and t.endswith(")") or t.startswith("-")
    t = t.strip("()-")
    if "," in t and "." in t:
        t = t.replace(",", "") if t.rfind(".") > t.rfind(",") else t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", t) else t.replace(",", ".")
    try:
        x = float(t)
    except ValueError:
        return None
    return -x if negative else x


def iso_date(s: str) -> str | None:
    """US documents: month first when the order is ambiguous."""
    s = s.strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", s)
    if m:
        a, b, y = (int(x) for x in m.groups())
        if y < 100:
            y += 2000 if y < 70 else 1900
        return _date(y, a, b) or _date(y, b, a)
    m = re.fullmatch(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", s)
    if m and m.group(1).lower() in MONTHS:
        return _date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2)))
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?[\s-]+([A-Za-z]{3})[a-z]*\.?,?[\s-]+(\d{4})", s)
    if m and m.group(2).lower() in MONTHS:
        return _date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
    return None


def _date(y: int, mo: int, d: int) -> str | None:
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def normalise(field: str, value: Any) -> str | None:
    if value in (None, "", [], {}):
        return None
    s = " ".join(str(value).split())
    if field.startswith("currency_code"):
        return SYMBOL_TO_CODE.get(s.upper(), SYMBOL_TO_CODE.get(s, s.upper()))
    if field.startswith("amount_") or field.startswith("tax_detail_"):
        x = parse_number(s)
        if x is not None:
            return f"{x:.2f}"
    if field.startswith("date_"):
        iso = iso_date(s)
        if iso:
            return iso
    return s.lower()


def values(field: str, value: Any) -> list[str]:
    """A system's value(s) for a field as normalised strings, duplicates dropped."""
    if isinstance(value, dict):
        value = value.get("value")
    if isinstance(value, list):
        items: list[Any] = value
    elif isinstance(value, str) and " | " in value:
        items = value.split(" | ")
    else:
        items = [value]
    out: list[str] = []
    for item in items:
        n = normalise(field, item)
        if n and n not in out:
            out.append(n)
    return out


class Docile:
    name = "docile"
    title = "DocILE (validation, 500 documents)"
    columns = (
        Column("accuracy", "Accuracy"),
        Column("completed", "Documents completed", "int"),
    )

    # -- data ---------------------------------------------------------------------

    def fetch(self, data_dir: Path, token: str | None = None, source: Path | None = None, **_: Any) -> None:
        root = data_dir / self.name
        root.mkdir(parents=True, exist_ok=True)
        ids = self._ids()
        if source:
            archive = Path(source)
            if archive.is_dir():
                self._copy_from_dir(archive, root, ids)
                return
        elif token:
            archive = root / "annotated-trainval.zip"
            if not archive.is_file():
                _download_archive(ARCHIVE_URL.format(token=token.strip()), archive)
        else:
            sys.exit("docile: pass --token (from https://docile.rossum.ai) or --source <annotated-trainval.zip | extracted dir>")
        self._extract(archive, root, ids)

    def _extract(self, archive: Path, root: Path, ids: list[str]) -> None:
        print(f"extracting the validation split from {archive.name}")
        with zipfile.ZipFile(archive) as z:
            names = set(z.namelist())
            val_json = next((n for n in names if n.endswith("val.json")), None)
            if val_json is None:
                sys.exit(f"{archive}: no val.json inside; is this the annotated-trainval archive?")
            base = val_json[: -len("val.json")]
            (root / "pdfs").mkdir(exist_ok=True)
            (root / "annotations").mkdir(exist_ok=True)
            (root / "val.json").write_bytes(z.read(val_json))
            missing = []
            for i, docid in enumerate(ids, 1):
                for sub, ext in (("pdfs", ".pdf"), ("annotations", ".json")):
                    member = f"{base}{sub}/{docid}{ext}"
                    dst = root / sub / f"{docid}{ext}"
                    if dst.is_file():
                        continue
                    if member not in names:
                        missing.append(member)
                        continue
                    dst.write_bytes(z.read(member))
                if i % 100 == 0:
                    print(f"  {i}/{len(ids)}", flush=True)
        if missing:
            print(f"warning: {len(missing)} files not in the archive, e.g. {missing[0]}", file=sys.stderr)
        print(f"ready: {root}")

    def _copy_from_dir(self, src: Path, root: Path, ids: list[str]) -> None:
        for sub, ext in (("pdfs", ".pdf"), ("annotations", ".json")):
            (root / sub).mkdir(exist_ok=True)
            for docid in ids:
                s, d = src / sub / f"{docid}{ext}", root / sub / f"{docid}{ext}"
                if s.is_file() and not d.is_file():
                    d.write_bytes(s.read_bytes())
        if (src / "val.json").is_file():
            (root / "val.json").write_bytes((src / "val.json").read_bytes())
        print(f"ready: {root}")

    @staticmethod
    def _ids() -> list[str]:
        return (repo_root() / "datasets" / "docile" / "val_docids.txt").read_text().split()

    def docs(self, data_dir: Path, labels: str = "official") -> list[Doc]:
        root = data_dir / self.name
        schema = json.loads((repo_root() / "datasets" / "docile" / "schema.json").read_text())
        fixes = _label_fixes() if labels == "corrected" else {}
        if labels not in ("official", "corrected"):
            raise ValueError(f"unknown labels {labels!r}; use official or corrected")
        docs = []
        for docid in self._ids():
            ann_path = root / "annotations" / f"{docid}.json"
            if not ann_path.is_file():
                raise FileNotFoundError(f"{ann_path} — run `drbench fetch docile` first")
            gt = _ground_truth(json.loads(ann_path.read_text()))
            for field, (old, new) in fixes.get(f"{docid}.pdf", {}).items():
                current = " | ".join(gt.get(field, []))
                if current != old:
                    print(f"errata: {docid} {field}: label is {current!r}, not {old!r}; fix skipped", file=sys.stderr)
                    continue
                if new:
                    gt[field] = new.split(" | ")
                else:
                    gt.pop(field, None)
            docs.append(Doc(id=docid, pdf=root / "pdfs" / f"{docid}.pdf", schema=schema, ground_truth=gt))
        return docs

    # -- scoring ------------------------------------------------------------------

    def grade(self, pred: dict, ground_truth: dict[str, list[str]], schema: dict) -> dict:
        fields = list(schema.get("properties", {}))
        out: dict[str, Any] = {"tp": 0, "fp": 0, "fn": 0, "fields": {}}
        for field in fields:
            p = set(values(field, pred.get(field)))
            e = {n for t in ground_truth.get(field, []) if (n := normalise(field, t))}
            tp, fp, fn = len(p & e), len(p - e), len(e - p)
            out["fields"][field] = {"tp": tp, "fp": fp, "fn": fn}
            out["tp"] += tp
            out["fp"] += fp
            out["fn"] += fn
        # the headline, per document: answer-key values the system got right
        expected = out["tp"] + out["fn"]
        out["accuracy"] = out["tp"] / expected if expected else 1.0
        return out

    def aggregate(self, per_doc: list[dict]) -> dict:
        tp = sum(d["tp"] for d in per_doc)
        fp = sum(d["fp"] for d in per_doc)
        fn = sum(d["fn"] for d in per_doc)
        prf = _prf(tp, fp, fn)
        # the headline: answer-key values the system got right, averaged per document
        # (a failed document contributes 0); recall is the same thing pooled
        accuracy = sum(d["accuracy"] for d in per_doc) / len(per_doc) if per_doc else 0.0
        out = {"documents": len(per_doc), "accuracy": accuracy, **prf, "fields": {}}
        for field in sorted({f for d in per_doc for f in d["fields"]}):
            counts = [d["fields"].get(field, {"tp": 0, "fp": 0, "fn": 0}) for d in per_doc]
            out["fields"][field] = _prf(
                sum(c["tp"] for c in counts), sum(c["fp"] for c in counts), sum(c["fn"] for c in counts)
            )
        return out


def _prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": precision, "recall": recall, "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0}


def _ground_truth(annotation: dict) -> dict[str, list[str]]:
    """KILE labels as {fieldtype: [text, ...]}; bare currency symbols become ISO codes."""
    gt: dict[str, list[str]] = {}
    for item in annotation.get("field_extractions", []):
        fieldtype, text = item.get("fieldtype"), (item.get("text") or "").strip()
        if not fieldtype or not text:
            continue
        if fieldtype.startswith("currency_code"):
            text = SYMBOL_TO_CODE.get(text, SYMBOL_TO_CODE.get(text.upper()))
            if text is None:
                continue
        if text not in gt.setdefault(fieldtype, []):
            gt[fieldtype].append(text)
    return gt


def _label_fixes() -> dict[str, dict[str, tuple[str, str]]]:
    """datasets/docile/errata/label_fixes.csv as {file: {field: (old, new)}}; empty new = removed."""
    fixes: dict[str, dict[str, tuple[str, str]]] = {}
    with open(repo_root() / "datasets" / "docile" / "errata" / "label_fixes.csv", newline="") as f:
        for row in csv.DictReader(f):
            fixes.setdefault(row["file"], {})[row["field"]] = (row["label"], row["new"])
    return fixes


def _download_archive(url: str, dst: Path) -> None:
    print("downloading annotated-trainval.zip (several GB; resumes are not supported, so let it finish)")
    tmp = dst.with_suffix(".part")
    with httpx.Client(timeout=httpx.Timeout(60, read=600), follow_redirects=True) as client:
        with client.stream("GET", url) as r:
            if r.status_code == 403:
                sys.exit("403 from the DocILE bucket: check the token (it is the folder name in the download URL)")
            r.raise_for_status()
            total = int(r.headers.get("content-length") or 0)
            done = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
                    done += len(chunk)
                    if total and done % (256 << 20) < (1 << 20):
                        print(f"  {done / 1e9:.1f} / {total / 1e9:.1f} GB", flush=True)
    tmp.replace(dst)
