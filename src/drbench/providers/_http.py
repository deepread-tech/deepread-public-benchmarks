"""Shared HTTP plumbing for the vendor adapters: retries on transient errors and
a job-id sidecar so that a retry polls the job it already paid for instead of
submitting a new one."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

import httpx

TRANSIENT = {408, 409, 425, 429, 500, 502, 503, 504}
FATAL = {401, 402, 403}  # bad key, no credit, no access: retrying cannot help, stop the whole run


class FatalError(RuntimeError):
    """An error that will hit every document the same way; the runner stops on it."""


def env_key(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"{name} is not set (see docs/providers.md)")
    return value


def request(client: httpx.Client, method: str, url: str, *, attempts: int = 6, **kwargs: Any) -> httpx.Response:
    """One HTTP call with exponential backoff on transient status codes and transport errors."""
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            r = client.request(method, url, **kwargs)
        except httpx.TransportError as e:
            last = e
        else:
            if r.status_code in FATAL:
                raise FatalError(f"HTTP {r.status_code} from {url}: {r.text[:300]}")
            if r.status_code not in TRANSIENT:
                r.raise_for_status()
                return r
            last = httpx.HTTPStatusError(f"HTTP {r.status_code}: {r.text[:300]}", request=r.request, response=r)
            retry_after = r.headers.get("retry-after")
            if retry_after and retry_after.isdigit():
                time.sleep(min(120, int(retry_after)))
                continue
        time.sleep(min(60, 5 * 2**attempt))
    raise RuntimeError(f"{method} {url} failed after {attempts} attempts: {last}")


def poll(fetch: Callable[[], dict], done: Callable[[dict], bool], interval: float, timeout: float) -> dict:
    """Call `fetch` until `done(body)`; transient errors only delay the next poll."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            body = fetch()
        except (httpx.TransportError, httpx.HTTPStatusError, RuntimeError) as e:
            if time.monotonic() > deadline:
                raise
            print(f"  poll error, retrying: {str(e)[:120]}", file=sys.stderr)
        else:
            if done(body):
                return body
            if time.monotonic() > deadline:
                raise TimeoutError(f"job still not finished after {timeout:.0f}s")
        time.sleep(interval)


class Sidecar:
    """`<out>.job.json`: the vendor-side ids of work already submitted for this document."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, Any] = {}
        if path.is_file():
            try:
                self.data = json.loads(path.read_text())
            except ValueError:
                self.data = {}

    def get(self, key: str) -> Any:
        return self.data.get(key)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data))

    def clear(self) -> None:
        self.data = {}
        self.path.unlink(missing_ok=True)


def unwrap_values(node: Any, markers: tuple[str, ...]) -> Any:
    """Some APIs wrap every leaf as {"value": ..., <marker>: ...}; keep only the value."""
    if isinstance(node, dict):
        if "value" in node and any(m in node for m in markers):
            return unwrap_values(node["value"], markers)
        return {k: unwrap_values(v, markers) for k, v in node.items()}
    if isinstance(node, list):
        return [unwrap_values(v, markers) for v in node]
    return node
