from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class Adapter(Protocol):
    """Moves one PDF and one JSON Schema through one vendor's API.

    An adapter is constructed with the system's `settings` (see `drbench/systems.py`)
    and sends nothing else: no prompts, no extra options, no post-processing of
    values. `extract` returns `(extraction, usage)`: the extraction as a plain JSON
    object, and what the vendor reports about the job — always the vendor's job
    ids, plus `credits` when the vendor bills in credits. It raises on failure; the
    runner decides about retries. `sidecar` is a file the adapter uses to remember
    job ids, so a retry polls the job already paid for instead of submitting again.
    """

    def __init__(self, settings: dict[str, Any]) -> None: ...

    def extract(self, pdf: Path, schema: dict, sidecar: Path) -> tuple[Any, dict]: ...
