"""Extend — https://www.extend.ai  (API docs: https://docs.extend.ai)

Sign up at https://dashboard.extend.ai (pay as you go; new accounts get free
credits), create an API key, then `export EXTEND_API_KEY=...`.

Calls: `POST /files/upload` (multipart) returns a file id; `POST /extract_runs`
with `file.id` and `config.schema`, polled on `GET /extract_runs/{id}`. Every
other option is Extend's default, which is the `extraction_performance`
processor. The Operator system adds only `config.baseProcessor =
"extraction_operator"`, the switch for that product. Cost comes from the run's
`usage.totalCredits` (extraction plus the parse it triggers).

Extend accepts a stricter dialect of JSON Schema than the other APIs, so the
schema is translated (`to_extend_schema`) without changing any field, type or
description; values are mapped back (`from_extend`).
"""

from __future__ import annotations

import copy
import time
from pathlib import Path
from typing import Any

import httpx

from ._http import Sidecar, env_key, poll, request

BASE_URL = "https://api.extend.ai"
API_VERSION = "2026-02-09"
_DONE = {"PROCESSED", "FAILED", "CANCELLED"}
_ID_ALIAS = "id_field"  # `id` is reserved inside Extend schemas


class Extend:
    def __init__(self, settings: dict[str, Any]):
        self.settings = settings

    def extract(self, pdf: Path, schema: dict, sidecar: Path) -> tuple[Any, dict]:
        headers = {"Authorization": f"Bearer {env_key('EXTEND_API_KEY')}", "x-extend-api-version": API_VERSION}
        side = Sidecar(sidecar)
        with httpx.Client(timeout=httpx.Timeout(60, read=600)) as client:
            file_id = side.get("file_id")
            if not file_id:
                r = request(
                    client, "POST", f"{BASE_URL}/files/upload", headers=headers,
                    files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")},
                )
                file_id = r.json().get("id") or (r.json().get("file") or {}).get("id")
                if not file_id:
                    raise RuntimeError(f"/files/upload returned no id: {r.text[:300]}")
                side.set("file_id", file_id)
            run_id = side.get("run_id")
            if not run_id:
                config = {"schema": to_extend_schema(schema), **self.settings}
                r = request(client, "POST", f"{BASE_URL}/extract_runs", headers=headers,
                            json={"file": {"id": file_id}, "config": config})
                run_id = r.json().get("id")
                if not run_id:
                    raise RuntimeError(f"/extract_runs returned no id: {r.text[:300]}")
                side.set("run_id", run_id)
                side.set("submitted_at", time.time())
            body = poll(
                lambda: request(client, "GET", f"{BASE_URL}/extract_runs/{run_id}", headers=headers).json(),
                lambda b: str(b.get("status", "")).upper() in _DONE,
                interval=5,
                timeout=4 * 3600,
            )
        if str(body.get("status", "")).upper() != "PROCESSED":
            side.clear()
            raise RuntimeError(f"run {run_id} {body.get('status')}: {body.get('failureReason')} {body.get('failureMessage')}")
        run_usage = body.get("usage") or {}
        usage = {
            "run_id": run_id,
            "file_id": file_id,
            "credits": run_usage.get("totalCredits", run_usage.get("credits")),
            "breakdown": run_usage.get("breakdown"),
        }
        return from_extend((body.get("output") or {}).get("value")), usage


def to_extend_schema(schema: dict) -> dict:
    """Translate a JSON Schema into the form Extend accepts. Extend rejects a
    schema unless scalar fields allow null, objects set `additionalProperties:
    false`, and `$ref`s are inlined; and it reserves the key `id`. Field names,
    types and descriptions are otherwise unchanged."""
    return _node(copy.deepcopy(schema), schema.get("$defs", {}))


def _node(node: dict, defs: dict, in_array: bool = False) -> dict:
    if "$ref" in node:
        return _node(copy.deepcopy(defs.get(node["$ref"].split("/")[-1], {})), defs, in_array)
    node.pop("$defs", None)
    kind = node.get("type")
    kinds = kind if isinstance(kind, list) else [kind]
    if "object" in kinds:
        node["type"] = "object"
        node["additionalProperties"] = False
        props = {k: _node(v, defs) for k, v in node.get("properties", {}).items()}
        if "id" in props:
            props[_ID_ALIAS] = props.pop("id")
        node["properties"] = props
        if "required" in node:
            node["required"] = [_ID_ALIAS if r == "id" else r for r in node["required"] if r in props or r == "id"]
    elif "array" in kinds:
        node["type"] = "array"
        if isinstance(node.get("items"), dict):
            node["items"] = _node(node["items"], defs, in_array=True)
    elif not in_array and kind is not None and "null" not in kinds:
        node["type"] = [*kinds, "null"]
        if isinstance(node.get("enum"), list):
            node["enum"] = [*node["enum"], None]
    return node


def from_extend(value: Any) -> Any:
    """Undo the `id` renaming in the extracted values."""
    if isinstance(value, dict):
        return {("id" if k == _ID_ALIAS else k): from_extend(v) for k, v in value.items()}
    if isinstance(value, list):
        return [from_extend(v) for v in value]
    return value
