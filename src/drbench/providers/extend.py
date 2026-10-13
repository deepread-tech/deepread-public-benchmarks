"""Extend — https://extend.ai  (docs: https://docs.extend.ai)

Sign up at https://dashboard.extend.ai (self-serve; new accounts get free
credits), create a key under Settings → API keys, then `export EXTEND_API_KEY=...`.

Call: `POST /files/upload` (multipart) gives a file `id`; `POST /extract_runs`
with an inline `config` — `baseProcessor` by mode and `schema` = the benchmark's
JSON Schema — polled on `GET /extract_runs/{id}`. Modes: `performance`
(`extraction_performance`, Extend's default) and `operator`
(`extraction_operator`, its agent for long, table-heavy documents). Citations
are off so `output.value` is plain values.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from ._http import FatalError, Sidecar, env_key, poll, request

BASE_URL = "https://api.extend.ai"
API_VERSION = "2026-02-09"
PIPELINES = {"performance": "extraction_performance", "operator": "extraction_operator"}
_DONE = {"PROCESSED", "FAILED", "CANCELLED"}


class Extend:
    env_key = "EXTEND_API_KEY"

    def __init__(self, pipeline: str = "performance", poll_interval: float = 5.0):
        if pipeline not in PIPELINES:
            raise ValueError(f"extend: pipeline must be one of {tuple(PIPELINES)}")
        self.pipeline = pipeline
        self.base_processor = PIPELINES[pipeline]
        self.name = f"extend-{pipeline}"
        self.poll_interval = poll_interval

    def extract(self, pdf: Path, schema: dict, sidecar: Path) -> tuple[Any, dict]:
        headers = {"Authorization": f"Bearer {env_key(self.env_key)}", "x-extend-api-version": API_VERSION}
        side = Sidecar(sidecar)
        with httpx.Client(timeout=httpx.Timeout(60, read=600)) as client:
            file_id = side.get("file_id")
            if not file_id:
                r = request(
                    client, "POST", f"{BASE_URL}/files/upload", headers=headers,
                    files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")},
                )
                file_id = r.json().get("id")
                if not file_id:
                    raise RuntimeError(f"/files/upload returned no id: {r.text[:300]}")
                side.set("file_id", file_id)
            run_id = side.get("run_id")
            if not run_id:
                payload = {
                    "file": {"id": file_id},
                    "config": {
                        "baseProcessor": self.base_processor,
                        "schema": schema,
                        "advancedOptions": {"citationsEnabled": False},
                    },
                }
                r = request(client, "POST", f"{BASE_URL}/extract_runs", headers=headers, json=payload)
                run_id = _run(r.json()).get("id")
                if not run_id:
                    raise RuntimeError(f"/extract_runs returned no id: {r.text[:300]}")
                side.set("run_id", run_id)
                side.set("submitted_at", time.time())
            body = poll(
                lambda: _run(request(client, "GET", f"{BASE_URL}/extract_runs/{run_id}", headers=headers).json()),
                lambda b: str(b.get("status", "")).upper() in _DONE,
                self.poll_interval,
                timeout=4 * 3600,
            )
        status = str(body.get("status", "")).upper()
        if status != "PROCESSED":
            side.clear()
            reason = f"{body.get('failureReason')}: {str(body.get('failureMessage'))[:300]}"
            if body.get("failureReason") == "OUT_OF_CREDITS":
                raise FatalError(f"run {run_id} failed: {reason}")
            raise RuntimeError(f"run {run_id} {status}: {reason}")
        output = body.get("output") or {}
        extraction = output.get("value", output) if isinstance(output, dict) else output
        usage: dict[str, Any] = {"run_id": run_id, "pipeline": self.pipeline, "base_processor": self.base_processor}
        usage.update({k: v for k, v in (body.get("usage") or {}).items() if k != "breakdown"})
        pages = ((body.get("file") or {}).get("metadata") or {}).get("pageCount")
        if pages is not None:
            usage["pages"] = pages
        return extraction, usage


def _run(body: Any) -> dict:
    """The run object: the body itself, or wrapped as `{"extractRun": {...}}`."""
    if isinstance(body, dict) and isinstance(body.get("extractRun"), dict):
        return body["extractRun"]
    return body if isinstance(body, dict) else {}
