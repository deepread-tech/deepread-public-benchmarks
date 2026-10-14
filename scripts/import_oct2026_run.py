"""How `runs/charity/` and `runs/longextract/` were assembled from the October 2026 run.

The vendor outputs were produced by this harness's own adapters (one envelope
per document) and the DeepRead outputs by DeepRead's API through our internal
benchmarks app, which keeps a public preview of every job. This script turns
both into the harness's `runs/<dataset>/<system>/<doc id>.json[.gz]` layout so
that `drbench grade` can re-score the published table offline:

    python scripts/import_oct2026_run.py \
        --vendor-runs ~/Documents/deepread/wt/bench-run/runs \
        --app-docs charity=run511_docs.json longextract=run510_docs.json

`--vendor-runs` holds `app-<dataset>/<system>/<app filename>.json` envelopes;
the app filename is the harness document id plus `.pdf` (`.pdf.pdf` for
Kleister-Charity). `--app-docs` are the benchmarks app's `/runs/{id}/documents`
listings; for every DeepRead `extract-selfhost` result the extraction is read
from the job's preview (`GET /v1/preview/{token}`, public) and DeepRead's
per-field review wrappers are removed, exactly as the DeepRead adapter does.
Only the documents of the committed sample lists are kept. LongExtractBench
outputs are large, so they are written gzip-compressed.

DocILE is not imported: Rossum's terms forbid redistributing its data.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from drbench import envelope, repo_root  # noqa: E402
from drbench.providers._http import unwrap_values  # noqa: E402
from drbench.providers.deepread import _WRAPPER_MARKERS  # noqa: E402

PREVIEW_URL = "https://deep-read-service-staging.up.railway.app/v1/preview/{token}"
SAMPLES = {"charity": "datasets/charity/sample-40.txt", "longextract": "datasets/longextract/sample-20.txt"}
SUFFIX = {"charity": ".pdf.pdf", "longextract": ".pdf"}  # app filename = harness id + suffix
VENDORS = ("reducto-extract", "reducto-deep-extract", "extend-performance", "extend-operator", "landingai-dpt-3-pro")
DEEPREAD = "deepread-extract-selfhost"
GZIP = {"longextract"}


def sample_ids(dataset: str) -> list[str]:
    lines = (repo_root() / SAMPLES[dataset]).read_text().splitlines()
    return [s.strip() for s in lines if s.strip() and not s.startswith("#")]


def write(path: Path, env: dict, packed: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(env, ensure_ascii=False)
    if packed:
        with gzip.open(path.with_suffix(".json.gz"), "wt", encoding="utf-8") as f:
            f.write(text)
    else:
        path.write_text(text)


def import_vendors(vendor_runs: Path, dataset: str, runs_dir: Path) -> None:
    ids = sample_ids(dataset)
    for system in VENDORS:
        src = vendor_runs / f"app-{dataset}" / system
        n = missing = 0
        for doc_id in ids:
            f = src / f"{doc_id}{SUFFIX[dataset]}.json"
            if not f.is_file():
                missing += 1  # no output at all: the grader counts it as a failure
                continue
            write(runs_dir / dataset / system / f"{doc_id}.json", json.loads(f.read_text()), dataset in GZIP)
            n += 1
        print(f"{dataset} × {system}: {n} envelopes copied, {missing} without output")


def import_deepread(app_docs: Path, dataset: str, runs_dir: Path, pipeline_id: int) -> None:
    ids = set(sample_ids(dataset))
    docs = [d for d in json.loads(app_docs.read_text()) if d["pipeline_id"] == pipeline_id]
    n = 0
    with httpx.Client(timeout=httpx.Timeout(60, read=600)) as client:
        for d in docs:
            doc_id = d["document_filename"].removesuffix(SUFFIX[dataset])
            if doc_id not in ids:
                continue
            usage = {"app_run": d["run_id"], "app_doc_result": d["id"], "page_count": d.get("page_count"),
                     "cost_usd": d.get("cost_usd"), "pipeline": "extract-selfhost"}
            if d["status"] != "done" or not d.get("preview_token"):
                env = _envelope(None, status="failed", error=d.get("error") or d["status"], latency=None, usage=usage)
            else:
                body = client.get(PREVIEW_URL.format(token=d["preview_token"])).raise_for_status().json()
                result = unwrap_values(body.get("data") or {}, _WRAPPER_MARKERS)
                env = _envelope(result, status="ok", error=None, latency=d.get("duration_s"), usage=usage)
            write(runs_dir / dataset / DEEPREAD / f"{doc_id}.json", env, dataset in GZIP)
            n += 1
    print(f"{dataset} × {DEEPREAD}: {n} envelopes from the app's previews")


def _envelope(result, *, status: str, error, latency, usage) -> dict:
    meta = {"system": DEEPREAD, "status": status, "latency_s": latency, "usage": usage, "attempts": 1,
            "written_at": "2026-10-13"}
    if error:
        meta["error"] = str(error)[:2000]
    return {"result": result, "_meta": meta}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--vendor-runs", type=Path, required=True)
    p.add_argument("--app-docs", nargs="+", required=True, help="<dataset>=<documents.json> pairs")
    p.add_argument("--deepread-pipeline-id", type=int, default=11, help="the app's id for extract-selfhost")
    p.add_argument("--runs", type=Path, default=Path("runs"))
    a = p.parse_args()
    app_docs = dict(pair.split("=", 1) for pair in a.app_docs)
    for dataset in SAMPLES:
        import_vendors(a.vendor_runs, dataset, a.runs)
        if dataset in app_docs:
            import_deepread(Path(app_docs[dataset]), dataset, a.runs, a.deepread_pipeline_id)
    assert envelope  # the layout written here is what drbench.envelope reads
    return 0


if __name__ == "__main__":
    sys.exit(main())
