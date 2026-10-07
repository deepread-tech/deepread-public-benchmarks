#!/usr/bin/env python3
"""Run DeepRead extraction against a PDF + JSON Schema.

Submits a /v1/process job (multipart: file + schema + pipeline) and polls
/v1/jobs/{id}. Every setting is controlled here, so this script is the single
source of truth for how the benchmark calls DeepRead:
  - pipeline: extract-selfhost (DEEPREAD_PIPELINE overrides)
  - no blueprint, no prompt changes: the benchmark's schema is sent as-is

The job id is kept in a sidecar next to --out, so a retry after a timeout polls
the same job instead of submitting (and paying for) a new one.

Auth: DEEPREAD_API_KEY. Endpoint: DEEPREAD_API_URL (default: production API).

Usage:
    python -m longextract_bench.providers.deepread \
        --pdf path/to/document.pdf --schema path/to/schema.json --out /tmp/deepread_out.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from longextract_bench.envelope import write_output

DEFAULT_URL = "https://api.deepread.tech"
DEFAULT_PIPELINE = "extract-selfhost"
_OK = {"completed", "done", "succeeded"}
_FAIL = {"failed", "error", "errored", "cancelled"}
_TRANSIENT = {429, 502, 503, 504}


def _unwrap(node: Any) -> Any:
    """DeepRead returns each field as {value, hil_flag, reason, ...}; the
    benchmark wants plain values, so keep only `value` at every level."""
    if isinstance(node, dict):
        if "value" in node and ("hil_flag" in node or "reason" in node or "found_on_page" in node):
            return _unwrap(node["value"])
        return {k: _unwrap(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_unwrap(v) for v in node]
    return node


def _fields(body: dict) -> dict:
    """The job's extracted fields as {key: value} (GET /v1/jobs/{id} returns
    extraction.fields as a list of {key, value, needs_review, ...})."""
    fields = (body.get("extraction") or {}).get("fields")
    if isinstance(fields, list):
        return {f["key"]: _unwrap(f.get("value")) for f in fields if isinstance(f, dict) and "key" in f}
    return _unwrap(body.get("data") or {})


def _submit(client: httpx.Client, url: str, key: str, pdf: Path, schema: dict, pipeline: str) -> str:
    for attempt in range(6):
        r = client.post(
            f"{url}/v1/process",
            headers={"X-API-Key": key, "accept": "application/json"},
            files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")},
            data={"pipeline": pipeline, "schema": json.dumps(schema)},
            timeout=600,
        )
        if r.status_code in _TRANSIENT:
            time.sleep(min(60, 5 * 2**attempt))
            continue
        r.raise_for_status()
        body = r.json()
        job_id = body.get("id") or body.get("job_id")
        if not job_id:
            raise RuntimeError(f"/v1/process: no job id: {r.text[:300]}")
        return str(job_id)
    raise RuntimeError(f"/v1/process HTTP {r.status_code}: {r.text[:300]}")


def _poll(client: httpx.Client, url: str, key: str, job_id: str, interval: int) -> dict:
    while True:
        try:
            r = client.get(f"{url}/v1/jobs/{job_id}", headers={"X-API-Key": key}, timeout=120)
            if r.status_code in _TRANSIENT:
                time.sleep(interval)
                continue
            r.raise_for_status()
        except httpx.TransportError:
            time.sleep(interval)
            continue
        body = r.json()
        status = str(body.get("status", "")).lower()
        if status in _OK:
            return body
        if status in _FAIL:
            raise RuntimeError(f"job {job_id} {status}: {str(body.get('error'))[:300]}")
        time.sleep(interval)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, type=Path)
    ap.add_argument("--schema", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--poll-interval", type=int, default=15)
    args = ap.parse_args()

    key = os.environ.get("DEEPREAD_API_KEY")
    if not key:
        print("DEEPREAD_API_KEY is not set", file=sys.stderr)
        return 2
    url = os.environ.get("DEEPREAD_API_URL", DEFAULT_URL).rstrip("/")
    pipeline = os.environ.get("DEEPREAD_PIPELINE", DEFAULT_PIPELINE)
    schema = json.loads(args.schema.read_text())
    sidecar = args.out.with_suffix(".job.json")

    t0 = time.time()
    with httpx.Client() as client:
        if sidecar.exists():
            job_id = json.loads(sidecar.read_text())["job_id"]
        else:
            job_id = _submit(client, url, key, args.pdf, schema, pipeline)
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            sidecar.write_text(json.dumps({"job_id": job_id, "submitted_at": t0}))
        body = _poll(client, url, key, job_id, args.poll_interval)
    result = _fields(body)
    usage = {k: body.get(k) for k in ("id", "status", "created_at", "completed_at", "review") if k in body}
    usage["pipeline"] = pipeline
    write_output(args.out, provider="deepread", result=result, latency_s=time.time() - t0, usage=usage)
    sidecar.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
