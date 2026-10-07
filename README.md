# Document extraction benchmarks

We gave DeepRead and other document AI APIs the same PDFs and the same JSON
Schema, and counted how many values each one got right. Everything is here so
you can run it yourself with your own API keys: the datasets, the schemas, the
scoring code, the raw outputs, and one command per step.

> **Status: internal draft.** The numbers below are **placeholders** until the
> committed runs are in; `drbench report` regenerates them from `runs/`.
> Do not share outside DeepRead until that is done.

## Results

**Accuracy = how many of the answer-key values the system got right.**
100% means every value in every document was correct. A document the system
could not process counts as all wrong.

| Benchmark | DeepRead `extract` | DeepRead `deep-extract` | Reducto Deep Extract | LandingAI ADE |
|---|---:|---:|---:|---:|
| Kleister-Charity — 440 UK charity reports, 8 fields | 95%* | 95%* | 90%* | 87%* |
| DocILE — 500 invoices and business documents, 33 fields | 95%* | 95%* | 90%* | 87%* |
| LongExtractBench — 50 long reports (22 to 11,622 pages), tables | 95%* | 95%* | 90%* | 87%* |

\* placeholder, replaced by the committed run. Run date and vendor job ids
are stored with every run in `runs/`.

## The three benchmarks

| Benchmark | What the documents are | Download |
|---|---|---|
| **Kleister-Charity** | Annual reports UK charities file with the Charity Commission. Multi-page scans. Fields: charity name and number, its street, town and postcode, report date, annual income and spending. From [applicaai/kleister-charity](https://github.com/applicaai/kleister-charity). | [huggingface.co/datasets/DeepRead/kleister-charity-dev0](https://huggingface.co/datasets/DeepRead/kleister-charity-dev0) |
| **DocILE** | Invoices and similar business documents, 1–3 pages. 33 fields: ids, dates, vendor and customer names and addresses, amounts, tax details, bank details. From [rossumai/docile](https://github.com/rossumai/docile). | Free token from [docile.rossum.ai](https://docile.rossum.ai) (their terms do not allow us to host a copy) |
| **LongExtractBench** | Long, table-heavy reports: statistical releases, 10-K/10-Q filings, clinical and regulatory reports. Each document has its own schema with large tables. From [micro1](https://huggingface.co/datasets/micro1-inc/longextract-bench-50). | [huggingface.co/datasets/DeepRead/longextract-bench-50](https://huggingface.co/datasets/DeepRead/longextract-bench-50) |

Details, versions and licences: [docs/datasets.md](docs/datasets.md).

## How we measure

1. Every system gets the same PDF and the same JSON Schema. The schema's field
   descriptions are the only instructions; nothing is tuned per vendor.
2. Each system's output is saved as one JSON file per document under
   `runs/<benchmark>/<system>/`.
3. The same code scores every output against the benchmark's answer key.
   Formatting differences (upper/lower case, `$1,200` vs `1200`, `3/4/2020`
   vs `2020-03-04`) are not errors; wrong or missing values are.
4. Accuracy is the share of answer-key values the system got right.

The full definitions — the exact matching rules per benchmark, how the
answer-key errors we found are handled, and the benchmarks' own metrics
(F1, precision, recall) which `drbench grade` also reports — are in
[docs/methodology.md](docs/methodology.md).

## Run it yourself

Requirements: Python 3.10+. The runs call paid APIs: one system over the three
benchmarks is about 32,000 pages (LongExtractBench is 19,500 of them). Prices
and free credits per vendor: [docs/providers.md](docs/providers.md). Use
`--limit` for a cheap smoke test.

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
drbench fetch docile --token <TOKEN>          # your token from docile.rossum.ai

# 3. run (paid; resumable — rerun the same command to continue)
drbench run --dataset charity --system deepread:extract -j 4
drbench run --dataset charity --system deepread:deep-extract -j 4
drbench run --dataset charity --system reducto -j 4
drbench run --dataset charity --system landingai -j 4
drbench run --dataset longextract --system deepread --limit 5   # smoke test

# 4. score and show the table (offline)
drbench grade --dataset charity
drbench report
```

Systems: `deepread:extract`, `deepread:deep-extract`, `reducto:extract`,
`reducto:deep-extract`, `landingai:dpt-3-pro`. `drbench grade` on our
committed `runs/` reproduces the table above without any key.

## Repository layout

```
datasets/<name>/         schema.json sent to every system, document lists, answer-key corrections
scripts/                 build_hf_datasets.py — how the Hugging Face copies were assembled
src/drbench/             fetch / run / grade / report
  datasets/              one module per benchmark: download, answer key, scoring
  providers/             one adapter per API: deepread, reducto, landingai
  graders/               micro1's LongExtractBench grader, vendored unmodified (MIT)
runs/<dataset>/<system>/ raw outputs behind the table, plus scores.json
official/                DeepRead scored with each benchmark's own scorer, as a cross-check
docs/                    methodology, datasets and licences, vendors and their APIs
tests/
```

## Licence

Code and documentation: MIT ([LICENSE](LICENSE)). The datasets keep their own
terms, listed in [docs/datasets.md](docs/datasets.md) and on each dataset
card; the vendored LongExtractBench grader is MIT
([THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)). Questions: hello@deepread.tech.
