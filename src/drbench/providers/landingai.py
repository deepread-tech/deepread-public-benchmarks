"""LandingAI Agentic Document Extraction (ADE) — https://landing.ai  (API docs: https://docs.landing.ai)

Sign up at https://ade.landing.ai (self-serve; new accounts get free credits),
copy the key from Settings → API key, then `export VISION_AGENT_API_KEY=...`.

ADE extracts from Markdown, not from the PDF, so each document is two jobs:
`POST /v2/parse/jobs` (the PDF → Markdown) and `POST /v2/extract/jobs` (the
Markdown and the benchmark's schema → values), each polled until it ends. No
model or tier is sent, so both jobs run on LandingAI's defaults (DPT-3 Pro for
parsing at the time of writing). The Markdown is kept next to the output so a
retry of the extract step does not pay for the parse again. Cost comes from the
`credit_usage` both jobs report.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from ._http import Sidecar, env_key, poll, request

BASE_URL = "https://api.ade.landing.ai"
_DONE = {"completed", "failed"}


class LandingAI:
    def __init__(self, settings: dict[str, Any]):
        self.settings = settings

    def extract(self, pdf: Path, schema: dict, sidecar: Path) -> tuple[Any, dict]:
        headers = {"Authorization": f"Bearer {env_key('VISION_AGENT_API_KEY')}"}
        side = Sidecar(sidecar)
        markdown_path = sidecar.with_suffix(".markdown.md")
        with httpx.Client(timeout=httpx.Timeout(60, read=600)) as client:
            if not markdown_path.is_file():
                markdown, parse_meta = self._parse(client, headers, side, pdf)
                markdown_path.parent.mkdir(parents=True, exist_ok=True)
                markdown_path.write_text(markdown)
                side.set("parse_metadata", parse_meta)
            extract_job = side.get("extract_job_id")
            if not extract_job:
                r = request(
                    client, "POST", f"{BASE_URL}/v2/extract/jobs", headers=headers,
                    files={"markdown": ("document.md", markdown_path.read_bytes(), "text/markdown")},
                    data={"schema": json.dumps(schema), **self.settings},
                )
                extract_job = r.json().get("job_id")
                if not extract_job:
                    raise RuntimeError(f"/v2/extract/jobs returned no job_id: {r.text[:300]}")
                side.set("extract_job_id", extract_job)
            body = _wait(client, headers, f"{BASE_URL}/v2/extract/jobs/{extract_job}")
        if str(body.get("status", "")).lower() != "completed":
            side.set("extract_job_id", None)
            raise RuntimeError(f"extract job {extract_job} failed: {str(body.get('error'))[:300]}")
        result = body.get("result") or {}
        parse_meta = side.get("parse_metadata") or {}
        extract_meta = result.get("metadata") or {}
        usage = {
            "parse_job_id": side.get("parse_job_id"),
            "extract_job_id": extract_job,
            "pages": parse_meta.get("page_count"),
            "credits": _sum(parse_meta.get("credit_usage"), extract_meta.get("credit_usage")),
            "parse": parse_meta,
            "extract": extract_meta,
            "schema_violation_error": result.get("schema_violation_error"),
        }
        return result.get("extraction"), usage

    def _parse(self, client: httpx.Client, headers: dict, side: Sidecar, pdf: Path) -> tuple[str, dict]:
        parse_job = side.get("parse_job_id")
        if not parse_job:
            r = request(
                client, "POST", f"{BASE_URL}/v2/parse/jobs", headers=headers,
                files={"document": (pdf.name, pdf.read_bytes(), "application/pdf")},
            )
            parse_job = r.json().get("job_id")
            if not parse_job:
                raise RuntimeError(f"/v2/parse/jobs returned no job_id: {r.text[:300]}")
            side.set("parse_job_id", parse_job)
            side.set("submitted_at", time.time())
        body = _wait(client, headers, f"{BASE_URL}/v2/parse/jobs/{parse_job}")
        if str(body.get("status", "")).lower() != "completed":
            side.clear()
            raise RuntimeError(f"parse job {parse_job} failed: {str(body.get('error'))[:300]}")
        result = body.get("result")
        if not result and body.get("output_url"):  # large parses are returned by link
            result = request(client, "GET", body["output_url"]).json()
        markdown = (result or {}).get("markdown")
        if not markdown:
            side.clear()
            raise RuntimeError(f"parse job {parse_job} returned no markdown")
        return markdown, (result or {}).get("metadata") or {}


def _wait(client: httpx.Client, headers: dict, url: str) -> dict:
    return poll(
        lambda: request(client, "GET", url, headers=headers).json(),
        lambda b: str(b.get("status", "")).lower() in _DONE,
        interval=5,
        timeout=4 * 3600,
    )


def _sum(*values: Any) -> float | None:
    numbers = [v for v in values if isinstance(v, (int, float))]
    return sum(numbers) if numbers else None
