# Document extraction benchmarks, reproducible

Structured extraction (PDF + JSON Schema → JSON) measured on three public
benchmarks, for DeepRead and other document AI APIs, with everything needed to
run it yourself: the datasets' sources, the exact schemas sent, the grader,
the raw outputs behind every number, and one command per step.

> **Status: internal draft.** The tables below hold **placeholder numbers**
> until the committed runs are in; `drbench report` regenerates them from
> `runs/`. Do not share outside DeepRead until that is done.

## Results

Same PDFs, same JSON Schema, same grader for every system; the schema's field
descriptions are the only instructions any system gets. Official labels as
published by each benchmark. Details in [docs/methodology.md](docs/methodology.md).

### Kleister-Charity (dev-0, 440 documents) — F1 (UC), the benchmark's metric

| System | Completed | F1 (UC) | Precision | Recall |
|---|---:|---:|---:|---:|
| DeepRead `deep-extract` | –/440 | 95.0%* | – | – |
| DeepRead `extract` | –/440 | 95.0%* | – | – |
| Reducto Deep Extract | –/440 | 90.0%* | – | – |
| Reducto Extract | –/440 | 90.0%* | – | – |
| LandingAI ADE (DPT-3 Pro) | –/440 | run pending | – | – |

### DocILE (validation, 500 documents) — field F1, value match

| System | Completed | Field F1 | Precision | Recall |
|---|---:|---:|---:|---:|
| DeepRead `deep-extract` | –/500 | 95.0%* | – | – |
| DeepRead `extract` | –/500 | 95.0%* | – | – |
| Reducto Deep Extract | –/500 | 90.0%* | – | – |
| Reducto Extract | –/500 | 90.0%* | – | – |
| LandingAI ADE (DPT-3 Pro) | –/500 | run pending | – | – |

### LongExtractBench (public subset, 50 documents) — micro1's grader

| System | Completed | Row precision | Row recall | Leaf accuracy |
|---|---:|---:|---:|---:|
| DeepRead `deep-extract` | –/50 | – | – | 95.0%* |
| DeepRead `extract` | –/50 | – | – | 95.0%* |
| Reducto Deep Extract | –/50 | – | – | 90.0%* |
| LandingAI ADE (DPT-3 Pro) | –/50 | – | – | run pending |

\* placeholder, to be replaced by the committed run. Scores are a point in
time (run dates and vendor job ids are in `runs/`); the grader and the pinned
datasets are what stays fixed.

For DeepRead we also reproduce the scores with each benchmark's **own scorer**
(GEval for Kleister-Charity, `docile_evaluate` KILE for DocILE) in
[`official/`](official/README.md), as an independent check: Kleister-Charity
F1 (UC) 80.9 with the official labels, 84.4 with our label errata applied
(pipeline `extract-selfhost`, October 2026).

## The datasets

| Dataset | What | Documents | Source (pinned) | Licence |
|---|---|---:|---|---|
| [Kleister-Charity](docs/datasets.md#kleister-charity) | UK charity annual reports, 8 fields | 440 (dev-0) | [applicaai/kleister-charity](https://github.com/applicaai/kleister-charity) `2309f486` | no licence file; public filings |
| [DocILE](docs/datasets.md#docile) | invoices and business documents, 33 KILE field types | 500 (val) | [rossumai/docile](https://github.com/rossumai/docile) v1.0, token from [docile.rossum.ai](https://docile.rossum.ai) | non-commercial research, no redistribution |
| [LongExtractBench](docs/datasets.md#longextractbench) | long, table-heavy reports; 22–11,622 pages | 50 (public subset) | [micro1-inc/longextract-bench-50](https://huggingface.co/datasets/micro1-inc/longextract-bench-50) `d4ca332f` | labels CC-BY-4.0 |

This repository ships no documents; `drbench fetch` downloads each dataset
from its source. What is committed: the schemas, the document lists, our label
errata, and the runs. See [docs/datasets.md](docs/datasets.md).

## Run it yourself

Requirements: Python 3.10+, git. The runs call paid APIs — a full sweep of one
system over the three datasets is roughly 32,000 pages (LongExtractBench is
19,500 of them); check the vendors' prices in
[docs/providers.md](docs/providers.md) first, and use `--limit` for a smoke
test.

```bash
git clone https://github.com/deepread-tech/deepread-public-benchmarks
cd deepread-public-benchmarks
pip install -e ".[dev]"

# 1. keys: sign up with each vendor and export only the ones you want to run
export DEEPREAD_API_KEY=...        # https://app.deepread.tech
export REDUCTO_API_KEY=...         # https://studio.reducto.ai
export VISION_AGENT_API_KEY=...    # https://ade.landing.ai

# 2. data
drbench fetch charity                         # ~1.7 GB from the Kleister repo + Applica's public S3
drbench fetch longextract                     # ~360 MB from Hugging Face
drbench fetch docile --token <TOKEN>          # your own token from docile.rossum.ai, several GB

# 3. run (paid; resumable — rerun the same command to continue)
drbench run --dataset charity --system deepread:deep-extract -j 4
drbench run --dataset charity --system reducto -j 4
drbench run --dataset charity --system landingai -j 4
drbench run --dataset longextract --system deepread --limit 5   # smoke test

# 4. grade and report (offline, deterministic)
drbench grade --dataset charity               # also: --labels corrected
drbench report
```

Systems are `<provider>[:<mode>]`: `deepread:extract`, `deepread:deep-extract`,
`reducto:extract`, `reducto:deep-extract`, `landingai:dpt-3-pro`. Outputs are
one JSON envelope per document under `runs/<dataset>/<system>/`; `drbench
grade` reads only those, so the committed runs can be re-graded without any
key, and any run can be inspected document by document.

## Repository layout

```
datasets/<name>/         schema.json sent to every system, document lists, label errata
src/drbench/             the harness: fetch / run / grade / report
  datasets/              one module per benchmark: fetcher, ground truth, metric
  providers/             one adapter per API: deepread, reducto, landingai
  graders/               micro1's LongExtractBench grader, vendored unmodified (MIT)
runs/<dataset>/<system>/ raw outputs behind the tables, plus scores.json
official/                DeepRead scored with each benchmark's own scorer (GEval, docile_evaluate)
docs/                    methodology, datasets and licences, systems and their APIs
tests/                   including the check that our Kleister scorer matches GEval
```

## Label errata

Public benchmark labels contain errors; we publish the ones we found
(`datasets/*/errata/label_fixes.csv`: old label, new label or removed,
confidence, reason — 336 changes for Kleister-Charity, 200 for DocILE) and
`drbench grade --labels corrected` scores every system against the corrected
set. Headline numbers always use the official labels. How the errata were made
is in [docs/methodology.md](docs/methodology.md#4-official-and-corrected-labels).

## Licence

Code and documentation: MIT (see [LICENSE](LICENSE)). The datasets keep their
own terms, listed in [docs/datasets.md](docs/datasets.md); the vendored
LongExtractBench grader is MIT, see [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
Questions: hello@deepread.tech.
