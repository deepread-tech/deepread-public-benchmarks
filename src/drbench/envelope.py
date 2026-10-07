"""One JSON file per (document, system): `{"result": <extraction>, "_meta": {...}}`.

The envelope is the only thing the grader reads, so anyone can re-grade a run
without API keys, and a run can be inspected document by document.
"""

from __future__ import annotations

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
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


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
