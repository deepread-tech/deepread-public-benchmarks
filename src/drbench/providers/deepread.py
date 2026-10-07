"""DeepRead — https://deepread.tech  (docs: https://deepread.tech/docs)

Sign up at https://app.deepread.tech, create an API key, then
`export DEEPREAD_API_KEY=...`. New accounts get free pages.

Call: `POST /v1/process` (multipart: `file`, `pipeline`, `schema`) returns a job;
`GET /v1/jobs/{id}` is polled until it completes. The benchmark's JSON Schema is
sent as-is; field `description`s are the only instructions the system gets.
Modes: `extract` (the default production pipeline) and `deep-extract`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from ._http import Sidecar, env_key, poll, request, unwrap_values

DEFAULT_URL = "https://api.deepread.tech"
PIPELINES = ("extract", "deep-extract")
_DONE = {"completed", "failed", "cancelled", "error"}
_WRAPPER_MARKERS = ("hil_flag", "needs_review", "human_review", "reason", "found_on_page")


class DeepRead:
    env_key = "DEEPREAD_API_KEY"

    def __init__(self, pipeline: str = "deep-extract", url: str | None = None, poll_interval: float = 5.0):
        if pipeline not in PIPELINES:
            raise ValueError(f"deepread: pipeline must be one of {PIPELINES}")
        self.pipeline = pipeline
        self.name = f"deepread-{pipeline}"
        self.url = (url or DEFAULT_URL).rstrip("/")
        self.poll_interval = poll_interval

    def extract(self, pdf: Path, schema: dict, sidecar: Path) -> tuple[Any, dict]:
        key = env_key(self.env_key)
        headers = {"X-API-Key": key}
        side = Sidecar(sidecar)
        with httpx.Client(timeout=httpx.Timeout(60, read=600)) as client:
            job_id = side.get("job_id")
            if not job_id:
                r = request(
                    client, "POST", f"{self.url}/v1/process", headers=headers,
                    files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")},
                    data={"pipeline": self.pipeline, "schema": json.dumps(schema)},
                )
                job_id = r.json().get("id") or r.json().get("job_id")
                if not job_id:
                    raise RuntimeError(f"/v1/process returned no job id: {r.text[:300]}")
                side.set("job_id", job_id)
                side.set("submitted_at", time.time())
            body = poll(
                lambda: request(client, "GET", f"{self.url}/v1/jobs/{job_id}", headers=headers).json(),
                lambda b: str(b.get("status", "")).lower() in _DONE,
                self.poll_interval,
                timeout=4 * 3600,
            )
        status = str(body.get("status", "")).lower()
        if status != "completed":
            side.clear()  # a failed job is not worth re-polling
            raise RuntimeError(f"job {job_id} {status}: {str(body.get('error'))[:300]}")
        usage = {
            "job_id": job_id,
            "pipeline": self.pipeline,
            "page_count": (body.get("document") or {}).get("page_count"),
            "created_at": body.get("created_at"),
            "completed_at": body.get("completed_at"),
        }
        return fields(body), usage


def fields(body: dict) -> dict:
    """`extraction.fields` is a list of {key, value, needs_review, ...}; keep {key: value}."""
    items = (body.get("extraction") or {}).get("fields")
    if isinstance(items, list):
        return {
            f["key"]: unwrap_values(f.get("value"), _WRAPPER_MARKERS)
            for f in items
            if isinstance(f, dict) and "key" in f
        }
    return unwrap_values(body.get("data") or body.get("result") or {}, _WRAPPER_MARKERS)
