# Document extraction benchmarks, reproducible

How well do document AI APIs turn a PDF plus a JSON Schema into correct JSON?
This repository measures DeepRead and other APIs on three public benchmarks and
gives you everything to check the numbers yourself: the datasets (hosted on
Hugging Face), the exact schema sent to every system, the grader, the raw
outputs behind every number, and one command per step. You run it with your
own API keys; no key of ours is in here.

> **Status: internal draft.** The result tables hold **placeholder numbers**
> until the committed runs are in; `drbench report` regenerates them from
> `runs/`. Do not share outside DeepRead until that is done.

## The benchmarks

| Benchmark | Documents | Task | Dataset (download) | Original source |
|---|---:|---|---|---|
| **Kleister-Charity** | 440 (dev-0) | UK charity annual reports, multi-page scans; 8 fields: charity name and number, its street, town and postcode, report date, annual income and spending | [deepread-tech/kleister-charity-dev0](https://huggingface.co/datasets/deepread-tech/kleister-charity-dev0) | [applicaai/kleister-charity](https://github.com/applicaai/kleister-charity) `2309f486` |
| **DocILE** | 500 (validation) | invoices and business documents, 1–3 pages; 33 field types: ids, dates, vendor and customer names and addresses, amounts, tax details, bank details | from Rossum with your own token — their terms allow no re-hosting | [rossumai/docile](https://github.com/rossumai/docile), token from [docile.rossum.ai](https://docile.rossum.ai) |
| **LongExtractBench** | 50 (public subset) | long, table-heavy reports (statistical releases, 10-K/10-Q filings, clinical and regulatory reports), 22 to 11,622 pages; one schema per document with large row arrays | [deepread-tech/longextract-bench-50](https://huggingface.co/datasets/deepread-tech/longextract-bench-50) (mirror) | [micro1-inc/longextract-bench-50](https://huggingface.co/datasets/micro1-inc/longextract-bench-50) `d4ca332f` |

Each Hugging Face dataset card lists every file and where it came from;
[`scripts/build_hf_datasets.py`](scripts/build_hf_datasets.py) is the code
that assembled them from the originals. More in [docs/datasets.md](docs/datasets.md).

## Results

Same PDFs, same JSON Schema, same grader for every system; the schema's field
descriptions are the only instructions any system gets. Official labels as
published by each benchmark.

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

## How we measure

1. **Fetch** the dataset from the links above. Nothing is modified: the PDFs
   and labels are the benchmark's own, pinned to one version.
2. **Run** each system over every document with the dataset's JSON Schema.
   The adapter for each API (`src/drbench/providers/`) only translates the
   request shape; it adds no prompts and changes no values. Every output is
   saved as one JSON file per document under `runs/<dataset>/<system>/`.
3. **Grade** offline with the benchmark's own metric:
   - Kleister-Charity: the official MultiLabel-F1 over upper-cased
     `field=value` labels, after the normalisation the Kleister README
     prescribes. Our implementation reproduces GEval's numbers on a real run
     (`tests/test_charity.py`). A document the system failed counts as misses.
   - DocILE: per-field F1 over (document, field, value) items, after light
     normalisation (whitespace and case, amounts as numbers, dates to ISO,
     currency symbols to codes). DocILE's official KILE score additionally
     needs each value's position on the page, which not every API returns.
   - LongExtractBench: micro1's grader, vendored unmodified — row precision
     and recall over the schema's arrays, leaf accuracy over the values of
     matched rows and document-level fields; averaged over the documents a
     system completed, as on micro1's leaderboard.
4. **Report**: the tables above come from `drbench report`, which reads only
   the saved outputs. Anyone can re-grade our committed runs without any key,
   and inspect every document's result.

Full definitions, including how failures are counted and how our label errata
were made: [docs/methodology.md](docs/methodology.md).

## Run it yourself

Requirements: Python 3.10+. The runs call paid APIs: one system over the three
datasets is about 32,000 pages (LongExtractBench is 19,500 of them); see the
vendors' prices in [docs/providers.md](docs/providers.md), and use `--limit`
for a smoke test.

```bash
git clone https://github.com/deepread-tech/deepread-public-benchmarks
cd deepread-public-benchmarks
pip install -e ".[dev]"

# 1. keys: sign up with each vendor you want to run and export its key
export DEEPREAD_API_KEY=...        # https://app.deepread.tech  (dashboard → API keys)
export REDUCTO_API_KEY=...         # https://studio.reducto.ai
export VISION_AGENT_API_KEY=...    # https://ade.landing.ai

# 2. data
drbench fetch charity                         # 1.7 GB from Hugging Face
drbench fetch longextract                     # 360 MB from Hugging Face
drbench fetch docile --token <TOKEN>          # your own token from docile.rossum.ai

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
`reducto:extract`, `reducto:deep-extract`, `landingai:dpt-3-pro`. Each run is
resumable and keeps the vendor's job ids, so an interrupted run continues
without paying twice. `drbench grade` on our committed `runs/` reproduces the
tables above without any key.

## Repository layout

```
datasets/<name>/         schema.json sent to every system, document lists, label errata
scripts/                 build_hf_datasets.py — how the Hugging Face copies were assembled
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
own terms, listed in [docs/datasets.md](docs/datasets.md) and on each dataset
card; the vendored LongExtractBench grader is MIT, see
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md). Questions: hello@deepread.tech.
