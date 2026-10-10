"""Reducto — https://reducto.ai  (API docs: https://docs.reducto.ai)

Sign up at https://studio.reducto.ai (self-serve Standard plan), create a key
under API Keys, then `export REDUCTO_API_KEY=...`.

Calls: `POST /upload` (multipart) returns a `file_id`; `POST /extract_async` with
`input` = that file and `instructions.schema` = the benchmark's schema, polled on
`GET /job/{id}`. Every other option is Reducto's default (citations are off by
default, so values come back plain). The Deep Extract system adds only
`settings.deep_extract = true`, the switch for that product.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from ._http import Sidecar, env_key, poll, request, unwrap_values

BASE_URL = "https://platform.reducto.ai"
_DONE = {"completed", "failed", "error", "cancelled"}


class Reducto:
    def __init__(self, settings: dict[str, Any]):
        self.settings = settings

    def extract(self, pdf: Path, schema: dict, sidecar: Path) -> tuple[Any, dict]:
        headers = {"Authorization": f"Bearer {env_key('REDUCTO_API_KEY')}"}
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
                payload: dict[str, Any] = {"input": file_id, "instructions": {"schema": schema}}
                if self.settings:
                    payload["settings"] = self.settings
                r = request(client, "POST", f"{BASE_URL}/extract_async", headers=headers, json=payload)
                job_id = r.json().get("job_id")
                if not job_id:
                    raise RuntimeError(f"/extract_async returned no job_id: {r.text[:300]}")
                side.set("job_id", job_id)
                side.set("submitted_at", time.time())
            body = poll(
                lambda: request(client, "GET", f"{BASE_URL}/job/{job_id}", headers=headers).json(),
                lambda b: str(b.get("status", "")).lower() in _DONE,
                interval=5,
                timeout=4 * 3600,
            )
            if str(body.get("status", "")).lower() != "completed":
                side.clear()
                raise RuntimeError(f"job {job_id} {body.get('status')}: {str(body.get('reason') or body.get('error'))[:300]}")
            result = body.get("result") or {}
            if isinstance(result, dict) and result.get("type") == "url":  # large results are returned by link
                result = request(client, "GET", result["url"]).json()
        extraction = result.get("result", result) if isinstance(result, dict) else result
        usage = {"job_id": job_id, "file_id": file_id}
        if isinstance(result, dict) and isinstance(result.get("usage"), dict):
            usage.update(result["usage"])
            usage["pages"] = result["usage"].get("num_pages")
        return merge(extraction), usage


def merge(extraction: Any) -> Any:
    """Reducto returns a list of extractions, more than one when it splits a long
    document into parts. The parts are joined into one object: array fields are
    concatenated in order, and a scalar field takes the first non-empty value."""
    extraction = unwrap_values(extraction, ("citations", "confidence", "granular_confidence"))
    if not isinstance(extraction, list):
        return extraction
    merged: dict[str, Any] = {}
    for part in extraction:
        if not isinstance(part, dict):
            continue
        for key, value in part.items():
            if isinstance(value, list):
                merged.setdefault(key, [])
                if isinstance(merged[key], list):
                    merged[key].extend(value)
            elif merged.get(key) in (None, "") and value not in (None, ""):
                merged[key] = value
            else:
                merged.setdefault(key, value)
    return merged
