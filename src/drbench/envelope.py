"""One JSON file per (document, system): `{"result": <extraction>, "_meta": {...}}`.

The envelope is the only thing the grader reads, so anyone can re-grade a run
without API keys, and a run can be inspected document by document. A run
writes plain `<doc id>.json`; committed runs may be stored gzip-compressed as
`<doc id>.json.gz`, which the grader and the runner read the same way.
"""

from __future__ import annotations

import gzip
import json
import time
from pathlib import Path
from typing import Any


def write(
    path: Path,
    *,
    system: str,
    result: Any,
    latency_s: float | None,
    usage: Any = None,
    status: str = "ok",
    error: str | None = None,
    attempts: int = 1,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {
        "system": system,
        "status": status,
        "latency_s": None if latency_s is None else round(latency_s, 3),
        "usage": usage,
        "attempts": attempts,
        "written_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if error:
        meta["error"] = error[:2000]
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps({"result": result, "_meta": meta}, ensure_ascii=False, default=str))
    tmp.replace(path)


def read(path: Path) -> dict | None:
    """The envelope at `path`, plain or gzip-compressed (`.json.gz`); None when unreadable."""
    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def locate(out_dir: Path, doc_id: str) -> Path:
    """Where a document's envelope is (or goes): a committed `.json.gz` when
    one exists, otherwise the plain `.json`."""
    packed = out_dir / f"{doc_id}.json.gz"
    return packed if packed.is_file() else out_dir / f"{doc_id}.json"


def classify(env: dict | None) -> tuple[str, str | None]:
    """Every (document, system) pair is exactly one of `success` or `failure`.

    Success means a real, non-empty extraction that the grader can score.
    A failure marker, an empty result, or a missing file are all failures;
    the reason is kept for the failures table.
    """
    if env is None:
        return "failure", "no output file"
    meta = env.get("_meta") or {}
    if meta.get("status") == "failed":
        return "failure", str(meta.get("error") or "failed")
    result = env.get("result")
    if result in ({}, None, []):
        return "failure", "empty result"
    if not isinstance(result, dict):
        return "failure", "result is not a JSON object"
    return "success", None
