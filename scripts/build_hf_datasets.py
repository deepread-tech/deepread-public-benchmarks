"""Assemble the Hugging Face dataset repositories that `drbench fetch` downloads.

This is the provenance of the DeepRead copies: every file is taken from the
benchmark's original source (pinned), plus the schema and label errata kept in
this repository. Run it, then upload each folder:

    python scripts/build_hf_datasets.py                 # writes hf/<dataset>/
    hf upload DeepRead/kleister-charity-dev0 hf/kleister-charity-dev0 --repo-type dataset
    hf upload DeepRead/longextract-bench-50  hf/longextract-bench-50  --repo-type dataset

DocILE is not assembled: its terms forbid redistribution, so `drbench fetch
docile` downloads it from Rossum with the user's own token.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import lzma
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]

# --- Kleister-Charity: applicaai/kleister-charity @ 2309f486 (2021-08-18, latest) ------
KLEISTER_REPO = "https://github.com/applicaai/kleister-charity"
KLEISTER_COMMIT = "2309f4861cc49864ac653a7fa108efc2144400b3"
# The PDFs are git-annex objects in Applica's public bucket (remote `pub-aws-s3`
# in the repo's git-annex branch); `documents/<name>` is a symlink whose target
# basename is the object key.
KLEISTER_S3 = "https://applica-public.s3-eu-west-1.amazonaws.com/kleister-charity-git-annex/"
KLEISTER_SPARSE = ("/README.md", "/config.txt", "/in-header.tsv", "/dev-0/expected.tsv", "/dev-0/in.tsv.xz", "/documents/")

# --- LongExtractBench: micro1-inc/longextract-bench-50 @ d4ca332f -----------------------
LONGEXTRACT_REPO = "micro1-inc/longextract-bench-50"
LONGEXTRACT_REVISION = "d4ca332f72f6d3649ecd11b69445a8f4ef5fcb02"

CHARITY_CARD = """---
pretty_name: Kleister-Charity dev-0
license: other
license_name: kleister-charity-unspecified
license_link: https://github.com/applicaai/kleister-charity
language:
- en
size_categories:
- n<1K
tags:
- document-extraction
- key-information-extraction
- pdf
- benchmark
- charity-reports
---

# Kleister-Charity, dev-0 split

The 440 documents and labels of the `dev-0` split of
[Kleister-Charity](https://github.com/applicaai/kleister-charity)
(Stanisławek et al., 2021): annual reports filed with the UK Charity Commission,
with eight fields each — charity name and number, the street, town and postcode
of the charity's own address, the report date, annual income and spending.
This copy exists so the benchmark can be downloaded in one step; nothing in the
original data was changed.

| File | What | Origin |
|---|---|---|
| `pdfs/<name>.pdf` | the 440 documents | git-annex objects of the Kleister repo at commit `{commit}` (Applica's public S3 bucket) |
| `documents.txt` | the 440 file names in the official order | first column of `dev-0/in.tsv.xz` |
| `expected.tsv` | the official labels, one line per document, `field=value` tokens | `dev-0/expected.tsv` at the same commit, unchanged |
| `expected.corrected.tsv` | the same labels with DeepRead's errata applied | this dataset's maintainers |
| `label_fixes.csv` | every label changed: old, new (empty = removed), confidence, reason | this dataset's maintainers |
| `schema.json` | the JSON Schema sent to every system in DeepRead's benchmark | this dataset's maintainers |

`test-A` labels were never released and the official scoring server
(gonito.net) is offline, so dev-0 is the largest split anyone can score.

## Benchmark

How the documents are scored (the benchmark's own F1 over upper-cased
`field=value` labels), how several document AI APIs compare on them, and the
code to run it with your own API keys:
**https://github.com/deepread-tech/deepread-public-benchmarks**

```bash
pip install git+https://github.com/deepread-tech/deepread-public-benchmarks
drbench fetch charity          # downloads this dataset
```

## Licence and provenance

The Kleister-Charity repository has no licence file; its README states the
data is not treated as sensitive, and the documents are public filings. They
are redistributed here as published, for benchmarking. DeepRead's additions
(`expected.corrected.tsv`, `label_fixes.csv`, `schema.json`) are CC-BY-4.0.

```bibtex
@inproceedings{{stanislawek2021kleister,
  title={{Kleister: Key Information Extraction Datasets Involving Long Documents with Complex Layouts}},
  author={{Stanis{{\\l}}awek, Tomasz and Grali{{\\'n}}ski, Filip and Wr{{\\'o}}blewska, Anna and Lipi{{\\'n}}ski, Dawid and Kaliska, Agnieszka and Rosalska, Paulina and Topolski, Bartosz and Biecek, Przemys{{\\l}}aw}},
  booktitle={{International Conference on Document Analysis and Recognition}},
  year={{2021}}
}}
```
"""

LONGEXTRACT_CARD = """---
pretty_name: LongExtractBench (50 public documents)
license: cc-by-4.0
size_categories:
- n<1K
tags:
- structured-extraction
- information-extraction
- document-understanding
- pdf
- tables
- long-context
- json-schema
- benchmark
---

# LongExtractBench, public 50-document subset — mirror

A byte-identical copy of
[micro1-inc/longextract-bench-50](https://huggingface.co/datasets/micro1-inc/longextract-bench-50)
at revision `{revision}`, kept so that DeepRead's benchmark pins one stable
copy of everything it uses. Credit and thanks to micro1; the original dataset
card follows below. The benchmark and its grader are at
https://github.com/micro1-research/longextract-bench (MIT); the benchmark was
commissioned by Reducto and audited by micro1.

How DeepRead and other document AI APIs score on these documents, graded with
micro1's own grader, and the code to run it with your own keys:
**https://github.com/deepread-tech/deepread-public-benchmarks**

```bash
pip install git+https://github.com/deepread-tech/deepread-public-benchmarks
drbench fetch longextract      # downloads this dataset
```

---

{original}
"""


def build_charity(data: Path, out: Path, workers: int) -> None:
    src = data / "charity-source"
    repo = src / "kleister-charity"
    if not (repo / "dev-0" / "expected.tsv").is_file():
        src.mkdir(parents=True, exist_ok=True)
        print(f"cloning {KLEISTER_REPO} @ {KLEISTER_COMMIT[:8]}")
        _git("clone", "--no-checkout", "--filter=blob:none", KLEISTER_REPO, str(repo))
        _git("-C", str(repo), "sparse-checkout", "set", "--no-cone", *KLEISTER_SPARSE)
        _git("-C", str(repo), "checkout", "--quiet", KLEISTER_COMMIT)
    with lzma.open(repo / "dev-0" / "in.tsv.xz", "rt", encoding="utf-8") as f:
        names = [line.split("\t", 1)[0] for line in f if line.strip()]
    expected = (repo / "dev-0" / "expected.tsv").read_text().splitlines()
    if len(names) != 440 or len(expected) != 440:
        sys.exit(f"expected 440 dev-0 documents, got {len(names)} names / {len(expected)} labels")

    dst = out / "kleister-charity-dev0"
    pdfs = dst / "pdfs"
    pdfs.mkdir(parents=True, exist_ok=True)
    keys = {n: _annex_key(repo, n) for n in names}
    todo = [n for n in names if not _complete(pdfs / n, keys[n])]
    print(f"charity: {len(names)} documents, downloading {len(todo)}")
    with httpx.Client(timeout=120, follow_redirects=True) as client, cf.ThreadPoolExecutor(workers) as pool:
        for i, _ in enumerate(pool.map(lambda n: _download(client, keys[n], pdfs / n), todo), 1):
            if i % 50 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}", flush=True)
    (dst / "documents.txt").write_text("\n".join(names) + "\n")
    shutil.copy(repo / "dev-0" / "expected.tsv", dst / "expected.tsv")
    shutil.copy(ROOT / "datasets" / "charity" / "errata" / "dev-0.expected.corrected.tsv", dst / "expected.corrected.tsv")
    shutil.copy(ROOT / "datasets" / "charity" / "errata" / "label_fixes.csv", dst / "label_fixes.csv")
    shutil.copy(ROOT / "datasets" / "charity" / "schema.json", dst / "schema.json")
    (dst / "README.md").write_text(CHARITY_CARD.format(commit=KLEISTER_COMMIT[:8]))
    print(f"charity: ready at {dst}")


def build_longextract(data: Path, out: Path) -> None:
    from huggingface_hub import snapshot_download

    src = data / "longextract-source"
    print(f"downloading {LONGEXTRACT_REPO} @ {LONGEXTRACT_REVISION[:8]}")
    snapshot_download(repo_id=LONGEXTRACT_REPO, repo_type="dataset", revision=LONGEXTRACT_REVISION, local_dir=str(src))
    dst = out / "longextract-bench-50"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".cache", ".gitattributes"))
    original = (src / "README.md").read_text()
    body = original.split("---", 2)[2].lstrip() if original.startswith("---") else original  # drop their front matter
    (dst / "README.md").write_text(LONGEXTRACT_CARD.format(revision=LONGEXTRACT_REVISION, original=body))
    folders = sum(1 for p in dst.iterdir() if p.is_dir())
    print(f"longextract: {folders} document folders ready at {dst}")


# --- helpers -----------------------------------------------------------------------------


def _git(*args: str) -> None:
    subprocess.run(["git", *args], check=True)


def _annex_key(repo: Path, name: str) -> str:
    link = repo / "documents" / name
    target = os.readlink(link) if link.is_symlink() else link.read_text().strip()
    return Path(target).name


def _complete(path: Path, key: str) -> bool:
    m = re.search(r"-s(\d+)-", key)
    return path.is_file() and (m is None or path.stat().st_size == int(m.group(1)))


def _download(client: httpx.Client, key: str, dst: Path) -> None:
    tmp = dst.with_suffix(".tmp")
    for _ in range(4):
        try:
            with client.stream("GET", KLEISTER_S3 + key) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_bytes(1 << 16):
                        f.write(chunk)
            if _complete(tmp, key):
                tmp.replace(dst)
                return
        except httpx.HTTPError as e:
            print(f"  retry {dst.name}: {e}", file=sys.stderr)
    raise RuntimeError(f"could not download {dst.name}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path("data"), help="scratch dir for the original sources")
    ap.add_argument("--out", type=Path, default=Path("hf"), help="where the upload folders are written")
    ap.add_argument("--only", choices=["charity", "longextract"])
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    if a.only in (None, "charity"):
        build_charity(a.data, a.out, a.workers)
    if a.only in (None, "longextract"):
        build_longextract(a.data, a.out)


if __name__ == "__main__":
    main()
