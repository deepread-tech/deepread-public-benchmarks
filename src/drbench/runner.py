"""Send every document of a dataset through one system, in parallel, resumably.

Outputs land in `<runs>/<dataset>/<system>/<doc id>.json`. A finished document
is skipped, so rerunning the same command continues where it stopped. Vendor
job ids are kept in `<doc id>.job.json` while a document is in flight: a
document that timed out still has one, and the rerun polls that job instead of
paying for a new one. `--retry-failures` also redoes documents that failed, and
`--force` redoes everything.
"""

from __future__ import annotations

import concurrent.futures as cf
import random
import sys
import threading
import time
import traceback
from pathlib import Path

from . import envelope
from .datasets import Dataset, Doc
from .providers import Adapter
from .providers._http import FatalError
from .systems import System


def run(
    dataset: Dataset,
    system: System,
    provider: Adapter,
    docs: list[Doc],
    runs_dir: Path,
    *,
    concurrency: int = 4,
    retries: int = 3,
    force: bool = False,
    retry_failures: bool = False,
) -> dict[str, int]:
    out_dir = runs_dir / dataset.name / system.id
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [doc for doc in docs if force or _needs_run(out_dir / f"{doc.id}.json", retry_failures)]
    counts = {"ok": 0, "failed": 0, "skipped": len(docs) - len(todo)}
    print(f"{dataset.name} × {system.id}: {len(todo)} to run, {counts['skipped']} already done → {out_dir}")
    if not todo:
        return counts
    stop = threading.Event()
    with cf.ThreadPoolExecutor(concurrency) as pool:
        futures = {pool.submit(_one, system, provider, doc, out_dir / f"{doc.id}.json", retries, stop): doc for doc in todo}
        for future in cf.as_completed(futures):
            doc = futures[future]
            status, detail = future.result()
            if status == "stopped":
                continue
            counts["ok" if status == "ok" else "failed"] += 1
            print(f"  {doc.id}: {status} {detail}", flush=True)
    if stop.is_set():
        left = len(todo) - counts["ok"] - counts["failed"]
        print(f"stopped: {counts['ok']} ok, {counts['failed']} failed, {left} not attempted — rerun the same "
              f"command to continue once the account is fixed")
        counts["stopped"] = left
        return counts
    print(f"done: {counts['ok']} ok, {counts['failed']} failed, {counts['skipped']} skipped")
    return counts


def _needs_run(out: Path, retry_failures: bool) -> bool:
    if not out.is_file() or out.with_suffix(".job.json").is_file():
        return True  # never run, or a vendor job still to collect
    return retry_failures and envelope.classify(envelope.read(out))[0] == "failure"


def _one(system: System, provider: Adapter, doc: Doc, out: Path, retries: int, stop: threading.Event) -> tuple[str, str]:
    sidecar = out.with_suffix(".job.json")
    time.sleep(random.uniform(0, 2))  # stagger submissions
    if stop.is_set():
        return "stopped", ""
    last_error = ""
    started = time.monotonic()
    for attempt in range(1, retries + 1):
        try:
            result, usage = provider.extract(doc.pdf, doc.schema, sidecar)
        except SystemExit:
            raise
        except FatalError as e:
            # no output is written: the document was never really attempted
            if not stop.is_set():
                stop.set()
                print(f"\nSTOP: {e}\n(the key is rejected or the account has no credit; nothing more is sent)",
                      file=sys.stderr, flush=True)
            return "stopped", str(e)
        except TimeoutError as e:
            # the vendor job may still finish; keep the sidecar so the next run polls it
            envelope.write(out, system=system.id, result=None, latency_s=None, status="failed",
                           error=f"timeout: {e}", attempts=attempt)
            return "failed", f"timeout after {time.monotonic() - started:.0f}s (sidecar kept)"
        except Exception as e:  # noqa: BLE001 — any vendor error is a failed attempt
            last_error = f"{type(e).__name__}: {e}"
            if attempt < retries:
                print(f"  {doc.id}: attempt {attempt} failed ({last_error[:160]}), retrying", file=sys.stderr)
                time.sleep(min(60, 5 * 2**attempt) + random.uniform(0, 3))
            else:
                traceback.print_exc(limit=1, file=sys.stderr)
        else:
            latency = time.monotonic() - started
            envelope.write(out, system=system.id, result=result, latency_s=latency, usage=usage, attempts=attempt)
            sidecar.unlink(missing_ok=True)
            return "ok", f"{latency:.0f}s"
    envelope.write(out, system=system.id, result=None, latency_s=None, status="failed",
                   error=last_error, attempts=retries)
    sidecar.unlink(missing_ok=True)
    return "failed", last_error[:160]
