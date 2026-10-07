from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class Provider(Protocol):
    """One document AI API, configured for one of its extraction modes.

    `extract` sends a PDF and a JSON Schema and returns `(extraction, usage)`:
    the extraction as a plain JSON object (values only, no per-field wrappers)
    and whatever the vendor reports about the job (ids, pages, credits). It
    raises on failure; the runner decides about retries and failure markers.
    `sidecar` is a file the adapter may use to remember vendor-side job ids so a
    retry polls the existing job instead of paying for a new one.
    """

    name: str  # label used in run directories and tables, e.g. "deepread-deep-extract"
    env_key: str  # the environment variable holding the API key

    def extract(self, pdf: Path, schema: dict, sidecar: Path) -> tuple[Any, dict]: ...
