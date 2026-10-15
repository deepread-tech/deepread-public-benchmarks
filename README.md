# Document extraction benchmarks

We gave DeepRead and other document AI APIs the same PDFs and the same JSON
Schema, and counted how many values each one got right. Everything is here so
you can run it yourself with your own API keys: the datasets, the schemas, the
scoring code, and one command that repeats the whole comparison.

**The benchmarks are not ours.** They are three public benchmarks made by
other teams; we only run document AI APIs on them and publish the results.
All credit for the datasets, the annotations and the metrics goes to their
authors:

| Benchmark | Made by | Paper / page | Code and data | Licence |
|---|---|---|---|---|
| **Kleister-Charity** | Applica.ai — Stanisławek, Graliński, Wróblewska et al. | [Kleister: Key Information Extraction Datasets Involving Long Documents with Complex Layouts](https://arxiv.org/abs/2105.05796), ICDAR 2021 | [github.com/applicaai/kleister-charity](https://github.com/applicaai/kleister-charity) | no licence file; public UK Charity Commission filings |
| **DocILE** | Rossum — Šimsa, Šulc, Uřičář et al. | [DocILE Benchmark for Document Information Localization and Extraction](https://arxiv.org/abs/2302.05658), ICDAR 2023 | [github.com/rossumai/docile](https://github.com/rossumai/docile), [docile.rossum.ai](https://docile.rossum.ai) | non-commercial research only; download with your own token |
| **LongExtractBench** | micro1 (commissioned by Reducto) | [micro1.ai/benchmark/long-extraction](https://www.micro1.ai/benchmark/long-extraction) | [github.com/micro1-research/longextract-bench](https://github.com/micro1-research/longextract-bench), [micro1-inc/longextract-bench-50](https://huggingface.co/datasets/micro1-inc/longextract-bench-50) | code MIT, labels CC-BY-4.0 |

What is ours: the harness that runs the APIs, the JSON Schemas we send, the
label corrections we found, and the results. For LongExtractBench we also use
micro1's own grader, unmodified. Full citations in
[docs/datasets.md](docs/datasets.md#credits-and-citations).

## Results — October 2026

**Accuracy = how many of the answer-key values the system got right**, averaged
per document. 100% means every value in every document was correct. A document
the system could not process counts as 0.

| System | DocILE (500 docs) | Kleister-Charity (40 docs) | LongExtractBench (20 docs) | Average |
|---|---:|---:|---:|---:|
| **DeepRead extract** | 79.4% | 91.7% | 97.6% | **89.6%** |
| Extend Operator | 75.0% | 91.7% | 99.6% | 88.8% |
| Reducto Deep Extract | 72.3% | 91.0% | 94.9% | 86.1% |
| Extend Performance | 68.6% | 89.2% | 77.5%\* | 78.4% |
| LandingAI ADE | 72.4% | 89.8% | 70.8%\* | 77.7% |
| Reducto Extract | 69.1% | 91.1% | 47.6% | 69.3% |

\* On LongExtractBench, Extend Performance returned 19 of the 20 documents
and LandingAI 18 (jobs that never finished or failed with internal errors
after four attempts); each missing document counts as 0.

Run on 13 October 2026, 2,614 pages per system, the same documents and the
same schema for everyone. DeepRead extract here runs on DeepRead's own OCR
engine (`pipeline=extract-selfhost`), the engine the published numbers come
from. The other systems are the vendors' self-serve APIs at their default
settings, described in [docs/providers.md](docs/providers.md).
`drbench short-run` repeats exactly this run.

### The raw outputs, and what `drbench grade` gives on them

Every output of that run on Kleister-Charity and LongExtractBench is committed
under [`runs/`](runs/) — one file per document and system — so anyone can
re-score it offline with `drbench grade` and no API key. DocILE outputs are
not committed: Rossum's terms forbid redistributing its data. The table above
was scored by our internal scorer; `drbench grade` on the committed outputs
gives:

| System | Kleister-Charity (40 docs) | LongExtractBench (20 docs) |
|---|---:|---:|
| DeepRead extract | 80.6% | 97.6% |
| Extend Operator | 84.1% | 99.6% |
| Reducto Deep Extract | 80.6% | 94.9% |
| Extend Performance | 80.9% | 77.5% (19/20) |
| LandingAI ADE | 80.3% | 70.8% (18/20) |
| Reducto Extract | 81.3% | 44.0% |

LongExtractBench agrees to the decimal for five systems, since both scorers
run micro1's grader. Kleister-Charity is 8–11 points lower for every system
because `drbench grade` applies only the benchmark's own matching rule (an
upper-cased, exact `field=value` match after Kleister's normalisation), while
our scorer also accepts a value that a reviewer model judges immaterially
different, such as a street line with the district appended or a charity
name with "The" in front. The ranking is close either way. Reducto Extract's
LongExtractBench score is 3.6 points lower here because, on six documents
where it returned under 1% of the rows, our scorer credited it with more
than the strict "every missed row counts as wrong" rule gives.

```bash
drbench grade --dataset charity --ids datasets/charity/sample-40.txt
drbench grade --dataset longextract --ids datasets/longextract/sample-20.txt
```

`scripts/import_oct2026_run.py` documents how `runs/` was assembled.

## How we chose the documents

We did not pick documents by hand. Each sample is cut by a fixed rule, decided
before any system was run, and every system got the same files:

- **DocILE**: no selection — all 500 documents of the validation split (636 pages).
- **Kleister-Charity**: the first 40 of the 440 documents, in the order the
  dataset itself lists them in `documents.txt` (1,143 pages). The list is
  [`datasets/charity/sample-40.txt`](datasets/charity/sample-40.txt).
- **LongExtractBench**: the 20 shortest of the 50 documents by page count
  (835 pages). The full set is 19,528 pages and one document alone is 11,622,
  which is what makes the full run cost what it does below. The list is
  [`datasets/longextract/sample-20.txt`](datasets/longextract/sample-20.txt).

The rules look at nothing but order and length, so they cannot favour anyone.
Shorter documents are easier for every system alike.

## What it costs

Every price is what a self-serve customer pays per 1,000 pages. The vendors
bill their own accounts at their self-serve list rate, which is what they
charged us for the published run; DeepRead's share is its list price, paid
with the credits on your DeepRead account. Prices are as of October 2026
([docs/providers.md](docs/providers.md)); each command prints this table for
the systems you chose and asks before sending anything.

| System | $ / 1k pages | Short run (2,614 pages) | Full run (30,803 pages) |
|---|---:|---:|---:|
| DeepRead extract | $15 | $39 | $462 |
| Reducto Extract | $20 | $52 | $616 |
| Reducto Deep Extract | $40 | $105 | $1,232 |
| Extend Performance | $62.50 | $163 | $1,925 |
| Extend Operator | $87.50 | $229 | $2,695 |
| LandingAI ADE | $61 | $159 | $1,879 |
| **All six** | | **about $750** | **about $8,800** |

So the short run is roughly **$750** at list price, about $710 of it on the
vendor accounts, and the full run roughly **$8,800: $8,350 on the vendors
plus $460 of DeepRead credits**. New vendor accounts come with free credits
that cover part of a short run.
Page counts are from the PDFs themselves (DocILE 636; Kleister-Charity 10,639
over 440 documents; LongExtractBench 19,528 over 50).

## Run it yourself

Requirements: Python 3.10+ and an API key for each system you want to run.
Keys are read from the environment only.

```bash
git clone https://github.com/deepread-tech/deepread-public-benchmarks
cd deepread-public-benchmarks
pip install -e ".[dev]"

export DEEPREAD_API_KEY=...        # https://app.deepread.tech  (dashboard → API keys)
export REDUCTO_API_KEY=...         # https://studio.reducto.ai
export EXTEND_API_KEY=...          # https://dashboard.extend.ai
export VISION_AGENT_API_KEY=...    # https://ade.landing.ai
export DOCILE_TOKEN=...            # your free token from https://docile.rossum.ai (see below)

drbench short-run                  # our published run: 2,614 pages per system, about $750 at list price
drbench full-run                   # every document: 30,803 pages per system, about $8,800 at list price
```

Each command downloads the datasets, sends every document through the six
systems of the table above, grades the outputs, and ends with that table
built from your run. It shows the cost first and waits for a `y`. It is resumable: a document
that already has an output is not sent again, so rerunning the same command
continues an interrupted run. Useful options:

```bash
drbench short-run --dry-run                       # just the plan and the cost, nothing sent
drbench short-run --systems reducto,deepread      # only the systems you have keys for
drbench full-run --yes -j 8                       # no confirmation, 8 documents in flight per system
```

**DocILE needs your own token.** Its terms allow non-commercial research use
only and forbid redistribution, so we cannot host a copy. Request a free token
at [docile.rossum.ai](https://docile.rossum.ai), then either export
`DOCILE_TOKEN` as above or run `drbench fetch docile --token <TOKEN>` first.
Without it the commands explain this and run the other two benchmarks.

### Step by step

The two commands are built from four steps you can also run one at a time,
for example to test one system on a handful of documents first:

```bash
drbench fetch charity                                   # 1.7 GB from Hugging Face
drbench fetch longextract                               # 360 MB from Hugging Face
drbench fetch docile --token <TOKEN>                    # your token from docile.rossum.ai

drbench run --dataset charity --system reducto:extract --limit 5          # smoke test: 5 documents
drbench run --dataset longextract --system extend:operator \
            --ids datasets/longextract/sample-20.txt                      # our 20-document sample

drbench grade --dataset longextract --ids datasets/longextract/sample-20.txt   # score (offline)
drbench report                                                            # tables (offline)
```

Systems in the published table, and what `short-run` and `full-run` run by
default: `deepread:extract-selfhost`, `reducto:extract`, `reducto:deep-extract`,
`extend:performance`, `extend:operator`, `landingai:dpt-3-pro`. DeepRead
extract here runs on DeepRead's own OCR engine (`pipeline=extract-selfhost`),
the engine the published numbers come from. Also available through `--systems`
or `drbench run`: `deepread:deep-extract`, `deepread:extract` and
`deepread:deep-extract-selfhost`. `drbench grade` scores saved outputs without
any key, so a committed run can be re-scored by anyone.

## How we measure

1. Every system gets the same PDF and the same JSON Schema. The schema's field
   descriptions are the only instructions; nothing is tuned per vendor.
2. Each system's output is saved as one JSON file per document under
   `runs/<benchmark>/<system>/`.
3. The same code scores every output against the benchmark's answer key.
   Formatting differences (upper/lower case, `$1,200` vs `1200`, `3/4/2020`
   vs `2020-03-04`) are not errors; wrong or missing values are. The
   published table additionally lets a reviewer model accept a difference it
   judges immaterial; `drbench grade` does not, which is why its
   Kleister-Charity numbers above are lower.
4. Accuracy is the share of a document's answer-key values the system got
   right, averaged over the documents. LongExtractBench is scored by the
   benchmark's own grader, where every row of every table counts.

The exact matching rules per benchmark, how the answer-key errors we found are
handled, and the benchmarks' own metrics (F1, precision, recall), which
`drbench grade` also reports, are in [docs/methodology.md](docs/methodology.md).

## Repository layout

```
datasets/<name>/         schema.json sent to every system, document lists, answer-key corrections
scripts/                 how the Hugging Face copies and the committed runs/ were assembled
src/drbench/             short-run / full-run, and the steps they are made of: fetch / run / grade / report
  suite.py               the two runs: which documents, which systems, what they cost
  datasets/              one module per benchmark: download, answer key, scoring
  providers/             one adapter per API: deepread, reducto, landingai, extend
  graders/               micro1's LongExtractBench grader, vendored unmodified (MIT)
runs/<dataset>/<system>/ raw outputs of the October 2026 run (Charity, LongExtract), plus scores.json
official/                DeepRead scored with each benchmark's own scorer, as a cross-check
docs/                    methodology, datasets and licences, vendors and their APIs
tests/
```

## Licence

Code and documentation: MIT ([LICENSE](LICENSE)). The datasets keep their own
terms, listed in [docs/datasets.md](docs/datasets.md) and on each dataset
card; the vendored LongExtractBench grader is MIT
([THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)). Questions: hello@deepread.tech.
