"""LandingAI Agentic Document Extraction (ADE) — https://landing.ai  (docs: https://docs.landing.ai)

Sign up at https://ade.landing.ai (self-serve; new accounts get free credits),
copy the key from Settings → API key, then `export VISION_AGENT_API_KEY=...`.

ADE extracts from Markdown, not from the PDF, so each document is two calls on
the v2 API: `POST /v2/parse/jobs` (DPT-3) to get Markdown, then
`POST /v2/extract/jobs` with that Markdown and the benchmark's JSON Schema. Both
are polled until complete. The parsed Markdown is kept next to the output so a
retry of the extract step does not pay for the parse again.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from ._http import Sidecar, env_key, poll, request

BASE_URL = "https://api.ade.landing.ai"
PIPELINES = ("dpt-3-pro",)
_DONE = {"completed", "failed"}


class LandingAI:
    env_key = "VISION_AGENT_API_KEY"

    def __init__(self, pipeline: str = "dpt-3-pro", poll_interval: float = 5.0):
        if pipeline not in PIPELINES:
            raise ValueError(f"landingai: pipeline must be one of {PIPELINES}")
        self.pipeline = pipeline
        self.parse_model = f"{pipeline}-latest"
        self.name = f"landingai-{pipeline}"
        self.poll_interval = poll_interval

    def extract(self, pdf: Path, schema: dict, sidecar: Path) -> tuple[Any, dict]:
        headers = {"Authorization": f"Bearer {env_key(self.env_key)}"}
        side = Sidecar(sidecar)
        markdown_path = sidecar.with_suffix(".markdown.md")
        usage: dict[str, Any] = {"pipeline": self.pipeline, "parse_model": self.parse_model}
        with httpx.Client(timeout=httpx.Timeout(60, read=600)) as client:
            # 1. parse → markdown (cached on disk)
            if not markdown_path.is_file():
                parse_job = side.get("parse_job_id")
                if not parse_job:
                    r = request(
                        client, "POST", f"{BASE_URL}/v2/parse/jobs", headers=headers,
                        files={"document": (pdf.name, pdf.read_bytes(), "application/pdf")},
                        data={"model": self.parse_model},
                    )
                    parse_job = r.json().get("job_id")
                    if not parse_job:
                        raise RuntimeError(f"/v2/parse/jobs returned no job_id: {r.text[:300]}")
                    side.set("parse_job_id", parse_job)
                    side.set("submitted_at", time.time())
                body = poll(
                    lambda: request(client, "GET", f"{BASE_URL}/v2/parse/jobs/{parse_job}", headers=headers).json(),
                    lambda b: str(b.get("status", "")).lower() in _DONE,
                    self.poll_interval,
                    timeout=4 * 3600,
                )
                if str(body.get("status", "")).lower() != "completed":
                    side.clear()
                    raise RuntimeError(f"parse job {parse_job} failed: {str(body.get('error'))[:300]}")
                result = body.get("result")
                if not result and body.get("output_url"):
                    result = request(client, "GET", body["output_url"]).json()
                markdown = (result or {}).get("markdown")
                if not markdown:
                    side.clear()
                    raise RuntimeError(f"parse job {parse_job} returned no markdown")
                markdown_path.parent.mkdir(parents=True, exist_ok=True)
                markdown_path.write_text(markdown)
                side.set("parse_metadata", (result or {}).get("metadata"))
            usage["parse"] = side.get("parse_metadata")

            # 2. extract from the markdown
            extract_job = side.get("extract_job_id")
            if not extract_job:
                r = request(
                    client, "POST", f"{BASE_URL}/v2/extract/jobs", headers=headers,
                    files={"markdown": ("document.md", markdown_path.read_bytes(), "text/markdown")},
                    data={"schema": json.dumps(schema)},
                )
                extract_job = r.json().get("job_id")
                if not extract_job:
                    raise RuntimeError(f"/v2/extract/jobs returned no job_id: {r.text[:300]}")
                side.set("extract_job_id", extract_job)
            body = poll(
                lambda: request(client, "GET", f"{BASE_URL}/v2/extract/jobs/{extract_job}", headers=headers).json(),
                lambda b: str(b.get("status", "")).lower() in _DONE,
                self.poll_interval,
                timeout=4 * 3600,
            )
        if str(body.get("status", "")).lower() != "completed":
            side.set("extract_job_id", None)
            raise RuntimeError(f"extract job {extract_job} failed: {str(body.get('error'))[:300]}")
        result = body.get("result") or {}
        usage["extract"] = result.get("metadata")
        usage["schema_violation_error"] = result.get("schema_violation_error")
        usage["parse_job_id"], usage["extract_job_id"] = side.get("parse_job_id"), extract_job
        return result.get("extraction"), usage
