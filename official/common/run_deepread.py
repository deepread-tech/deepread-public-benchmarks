"""Send documents to the DeepRead API and save each full result as JSON.

usage: python common/run_deepread.py DOC_LIST.txt SCHEMA.json OUT_DIR [--pipeline extract-selfhost]
  DOC_LIST.txt  one PDF path per line
  OUT_DIR/<name>.json  the job's preview payload (values + field boxes + page sizes)

Env: DEEPREAD_API_KEY, DEEPREAD_API_URL (default https://api.deepread.tech).
Resumable: documents that already have an output are skipped.
"""
import argparse, concurrent.futures as cf, json, os, time
from pathlib import Path
import httpx

URL = os.environ.get("DEEPREAD_API_URL", "https://api.deepread.tech").rstrip("/")
KEY = os.environ["DEEPREAD_API_KEY"]
H = {"X-API-Key": KEY}


def run_one(pdf: Path, schema: str, pipeline: str, out: Path) -> str:
    if out.exists():
        return "skip"
    with httpx.Client(timeout=600) as c:
        r = c.post(f"{URL}/v1/process", headers=H,
                   files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")},
                   data={"pipeline": pipeline, "schema": schema, "preview": "true", "include_markers": "true"})
        r.raise_for_status()
        job = r.json()["id"]
        while True:
            b = c.get(f"{URL}/v1/jobs/{job}", headers=H).json()
            if b["status"] in ("completed", "failed", "cancelled"):
                break
            time.sleep(10)
        if b["status"] != "completed":
            out.write_text(json.dumps({"job_id": job, "status": b["status"], "error": b.get("error")}))
            return b["status"]
        art = b.get("artifacts") if isinstance(b.get("artifacts"), dict) else {}
        url = b.get("preview_url") or art.get("preview_url") or ""
        token = b.get("preview_token") or url.rstrip("/").rsplit("/", 1)[-1]
        p = c.get(f"{URL}/v1/preview/{token}").json()
        p.pop("document_url", None)
        for page in p.get("pages", []):
            page.pop("image_url", None)
        p["job_id"] = job
        out.write_text(json.dumps(p))
        return "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("doc_list"); ap.add_argument("schema"); ap.add_argument("out_dir")
    ap.add_argument("--pipeline", default="extract-selfhost"); ap.add_argument("-j", type=int, default=4)
    a = ap.parse_args()
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    schema = Path(a.schema).read_text()
    pdfs = [Path(l.strip()) for l in open(a.doc_list) if l.strip()]
    with cf.ThreadPoolExecutor(a.j) as ex:
        futs = {ex.submit(run_one, p, schema, a.pipeline, out / (p.name.removesuffix(".pdf") + ".json")): p for p in pdfs}
        for f in cf.as_completed(futs):
            print(futs[f].name, f.result(), flush=True)


if __name__ == "__main__":
    main()
