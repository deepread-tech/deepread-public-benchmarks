"""Reducto — https://reducto.ai  (docs: https://docs.reducto.ai)

Sign up at https://studio.reducto.ai (self-serve; new accounts get free usage),
create a key under API Keys, then `export REDUCTO_API_KEY=...`.

Call: `POST /upload` (multipart) gives a `file_id`; `POST /extract_async` with
`instructions.schema` = the benchmark's JSON Schema, polled on `GET /job/{id}`.
Modes: `deep-extract` (`settings.deep_extract = true`, Reducto's strongest and
the configuration micro1 used for LongExtractBench) and `extract` (standard).
Citations are off so the result is plain values.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from ._http import Sidecar, env_key, poll, request, unwrap_values

BASE_URL = "https://platform.reducto.ai"
PIPELINES = ("deep-extract", "extract")
_DONE = {"completed", "failed", "error", "cancelled"}


class Reducto:
    env_key = "REDUCTO_API_KEY"

    def __init__(self, pipeline: str = "deep-extract", poll_interval: float = 5.0):
        if pipeline not in PIPELINES:
            raise ValueError(f"reducto: pipeline must be one of {PIPELINES}")
        self.pipeline = pipeline
        self.name = f"reducto-{pipeline}"
        self.poll_interval = poll_interval

    def extract(self, pdf: Path, schema: dict, sidecar: Path) -> tuple[Any, dict]:
        headers = {"Authorization": f"Bearer {env_key(self.env_key)}"}
        side = Sidecar(sidecar)
        with httpx.Client(timeout=httpx.Timeout(60, read=600)) as client:
            file_id = side.get("file_id")
            if not file_id:
                r = request(
                    client, "POST", f"{BASE_URL}/upload", headers=headers,
                    files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")},
                )
                file_id = r.json().get("file_id")
                if not file_id:
                    raise RuntimeError(f"/upload returned no file_id: {r.text[:300]}")
                side.set("file_id", file_id)
            job_id = side.get("job_id")
            if not job_id:
                payload = {
                    "input": file_id,
                    "instructions": {"schema": schema},
                    "settings": {"deep_extract": self.pipeline == "deep-extract", "citations": {"enabled": False}},
                    "async": {"priority": False},
                }
                r = request(client, "POST", f"{BASE_URL}/extract_async", headers=headers, json=payload)
                job_id = r.json().get("job_id")
                if not job_id:
                    raise RuntimeError(f"/extract_async returned no job_id: {r.text[:300]}")
                side.set("job_id", job_id)
                side.set("submitted_at", time.time())
            body = poll(
                lambda: request(client, "GET", f"{BASE_URL}/job/{job_id}", headers=headers).json(),
                lambda b: str(b.get("status", "")).lower() in _DONE or b.get("result") is not None,
                self.poll_interval,
                timeout=4 * 3600,
            )
        status = str(body.get("status", "")).lower()
        if status != "completed" and body.get("result") is None:
            side.clear()
            raise RuntimeError(f"job {job_id} {status}: {str(body.get('reason') or body.get('error'))[:300]}")
        result = body.get("result") or {}
        extraction = result.get("result", result) if isinstance(result, dict) else result
        usage = {"job_id": job_id, "pipeline": self.pipeline, "duration_s": body.get("duration")}
        if isinstance(result, dict):
            usage.update(result.get("usage") or {})
        return normalise(extraction), usage


def normalise(extraction: Any) -> Any:
    """Reducto returns a list of extractions (one per document, more if it split
    the input); a single one is the object itself. Citation wrappers are removed."""
    extraction = unwrap_values(extraction, ("citations", "confidence", "granular_confidence"))
    if isinstance(extraction, list) and len(extraction) == 1:
        return extraction[0]
    return extraction
