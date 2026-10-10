"""DeepRead — https://deepread.tech  (API docs: https://deepread.tech/docs)

Sign up at https://app.deepread.tech, create an API key in the dashboard, then
`export DEEPREAD_API_KEY=...`.

Calls: `POST /v1/process` (multipart: `file`, `schema`, and the system's
`pipeline`) returns a job id; `GET /v1/jobs/{id}` is polled until the job ends.
The extraction is `extraction.fields`, a list of `{key, value, needs_review, ...}`
that is flattened to `{key: value}`.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from ._http import Sidecar, env_key, poll, request, unwrap_values

DEFAULT_URL = "https://api.deepread.tech"
_DONE = {"completed", "failed", "cancelled", "error"}
_REVIEW_MARKERS = ("needs_review", "review_reason", "hil_flag", "found_on_page")


class DeepRead:
    def __init__(self, settings: dict[str, Any]):
        self.settings = settings
        self.url = os.environ.get("DEEPREAD_API_URL", DEFAULT_URL).rstrip("/")

    def extract(self, pdf: Path, schema: dict, sidecar: Path) -> tuple[Any, dict]:
        headers = {"X-API-Key": env_key("DEEPREAD_API_KEY")}
        side = Sidecar(sidecar)
        with httpx.Client(timeout=httpx.Timeout(60, read=600)) as client:
            job_id = side.get("job_id")
            if not job_id:
                r = request(
                    client, "POST", f"{self.url}/v1/process", headers=headers,
                    files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")},
                    data={**self.settings, "schema": json.dumps(schema)},
                )
                job_id = r.json().get("id") or r.json().get("job_id")
                if not job_id:
                    raise RuntimeError(f"/v1/process returned no job id: {r.text[:300]}")
                side.set("job_id", job_id)
                side.set("submitted_at", time.time())
            body = poll(
                lambda: request(client, "GET", f"{self.url}/v1/jobs/{job_id}", headers=headers).json(),
                lambda b: str(b.get("status", "")).lower() in _DONE,
                interval=5,
                timeout=4 * 3600,
            )
        if str(body.get("status", "")).lower() != "completed":
            side.clear()  # a failed job is not worth polling again
            raise RuntimeError(f"job {job_id} {body.get('status')}: {str(body.get('error'))[:300]}")
        usage = {"job_id": job_id, "pages": (body.get("document") or {}).get("page_count")}
        return fields(body), usage


def fields(body: dict) -> dict:
    """`extraction.fields` → `{key: value}`, without DeepRead's per-value review flags."""
    items = (body.get("extraction") or {}).get("fields")
    if not isinstance(items, list):
        return {}
    return {
        f["key"]: unwrap_values(f.get("value"), _REVIEW_MARKERS)
        for f in items
        if isinstance(f, dict) and "key" in f
    }
