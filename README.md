# Document extraction benchmarks

[![Code licence: MIT](https://img.shields.io/badge/code-MIT-green)](LICENSE)
[![Results as of 16 Oct 2026](https://img.shields.io/badge/results-16%20Oct%202026-blue)](#results)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![Live leaderboard](https://img.shields.io/badge/live%20page-deepread.tech%2Fbenchmarks-black)](https://deepread.tech/benchmarks)

Seven document-extraction APIs, the same PDFs, the same JSON Schema, three
public benchmarks. We count how many answer-key values each API got right and
publish the numbers, the raw outputs, and one command that repeats the whole
run with your own keys.

The benchmarks are not ours. They are
[Kleister-Charity](https://github.com/applicaai/kleister-charity) by Applica.ai,
[DocILE](https://github.com/rossumai/docile) by Rossum and
[LongExtractBench](https://github.com/micro1-research/longextract-bench) by
micro1. Credits and licences are in
[Datasets, credits and licences](#datasets-credits-and-licences).

**Jump to:** [Results](#results) ·
[What this repository is](#what-this-repository-is) ·
[Run it yourself](#run-it-yourself-step-by-step) ·
[What it costs](#what-it-costs) ·
[How we measure](#how-we-measure) ·
[Re-score our outputs](#re-score-our-outputs-no-key-needed)

## Results

**Accuracy = how many of the answer-key values the system got right**, averaged
per document. 100 means every value in every document was right. A document
the system could not process counts as 0. Results as of **16 October 2026**.

| System | DocILE (500 docs) | Kleister-Charity (40 docs) | LongExtractBench (20 docs) | Average |
|---|---:|---:|---:|---:|
| **DeepRead deep-extract** | **85.8** | **92.4** | 97.8 | **91.8** |
| **DeepRead extract** | 83.5 | 92.0 | 97.7 | 90.9 |
| Extend Operator | 77.8 | **92.4** | **99.6** | 89.9 |
| Reducto Deep Extract | 75.2 | 91.7 | 94.9 | 87.3 |
| Extend Performance | 71.4 | 90.4 | 77.5 † | 79.8 |
| LandingAI ADE | 75.3 | 91.1 | 70.8 † | 79.1 |
| Reducto Extract | 71.9 | 92.0 | 47.6 | 70.5 |

† On LongExtractBench, Extend Performance returned 19 of the 20 documents and
LandingAI 18. Jobs that never finished, or failed with internal errors after
four attempts, count as 0.

What is behind the numbers:

- **Same input for everyone.** 2,614 pages per system, the same documents, the
  same schema, nothing tuned per vendor. The documents were chosen by a fixed
  rule before anyone was run, see [How we chose the documents](#how-we-chose-the-documents).
- **When.** The vendors ran on 13 October 2026 on their self-serve APIs at
  default settings. DeepRead's two rows were rerun on 15 and 16 October after
  accuracy fixes, on the same documents. Every system was then scored with the
  same scorer settings.
- **Prices.** DeepRead extract is $15 per 1,000 pages, DeepRead deep-extract
  $35. The vendors range from $20 to $87.50. The full list is in
  [What it costs](#what-it-costs).
- **The same numbers live at** [deepread.tech/benchmarks](https://deepread.tech/benchmarks).
  Every change to this table is listed in [Results history](#results-history).

## What this repository is

Everything needed to check the table above or produce your own.

| | Where | What it is |
|---|---|---|
| **The harness** | `src/drbench/` | One command downloads the datasets, sends every document to every API, grades the outputs and prints the table. It shows the cost first, asks before spending, and can be interrupted and resumed. |
| **What we sent** | `datasets/<benchmark>/` | The JSON Schema given to every system and the fixed document lists. The schema's field descriptions are the only instructions any system gets. |
| **What came back** | `runs/<benchmark>/<system>/` | Every raw output of the published run on Kleister-Charity and LongExtractBench, one file per document. DocILE outputs are not committed because Rossum's terms forbid redistributing its data. |
| **Scores** | `runs/<benchmark>/scores.json` | Per-document and per-system scores of the committed outputs, produced by `drbench grade`. |
| **Label corrections** | `datasets/<benchmark>/errata/` | Answer-key errors we found while reviewing results. The published table uses the official labels. `--labels corrected` applies the fixes. |
| **The write-up** | `docs/` | [Methodology](docs/methodology.md), [datasets and licences](docs/datasets.md), [vendors and their APIs](docs/providers.md). |

How we did it, in one paragraph. We took three public extraction benchmarks
that already have answer keys. For each one we wrote one JSON Schema that asks
for exactly the fields the answer key holds. We sent every document with that
schema to each API through its public, self-serve endpoint at default
settings, saved whatever came back, and compared it to the answer key with the
same code for everyone. LongExtractBench is scored by the benchmark's own
grader, unmodified. The result is one accuracy number per system per
benchmark, and the average of the three.

## Run it yourself, step by step

### What you need

- **Python 3.10 or newer** and about 2 GB of disk for the datasets.
- **An API key for each system you want to run.** You can run any subset. The
  keys and where to get them are in step 2.
- **Money on those accounts.** The published run costs about **$840** at list
  price across all seven systems, about $130 of it in DeepRead credits and the
  rest on the vendor accounts. New vendor accounts come with free credits that
  cover part of it. Nothing is sent until you confirm, and `--dry-run` shows
  the exact cost for free.
- **Time.** The run is resumable, so it does not have to finish in one sitting.

### Step 1. Install

```bash
git clone https://github.com/deepread-tech/deepread-public-benchmarks
cd deepread-public-benchmarks
pip install -e ".[dev]"
drbench --version
```

### Step 2. Add your keys

Keys are read from the environment only. Set the ones for the systems you want
to run.

| System | Environment variable | Where to get it |
|---|---|---|
| DeepRead extract and deep-extract | `DEEPREAD_API_KEY` | [app.deepread.tech](https://app.deepread.tech), dashboard → API keys |
| Reducto Extract and Deep Extract | `REDUCTO_API_KEY` | [studio.reducto.ai](https://studio.reducto.ai), API Keys |
| Extend Performance and Operator | `EXTEND_API_KEY` | [dashboard.extend.ai](https://dashboard.extend.ai), Settings → API keys |
| LandingAI ADE | `VISION_AGENT_API_KEY` | [ade.landing.ai](https://ade.landing.ai), Settings → API key |
| DocILE dataset download | `DOCILE_TOKEN` | [docile.rossum.ai](https://docile.rossum.ai), free token, research use only |

```bash
export DEEPREAD_API_KEY=...
export REDUCTO_API_KEY=...
export EXTEND_API_KEY=...
export VISION_AGENT_API_KEY=...
export DOCILE_TOKEN=...
```

Without `DOCILE_TOKEN` the run skips DocILE, says so, and still runs the other
two benchmarks. Rossum's terms do not let us host a copy of DocILE.

### Step 3. See the plan and the cost. Nothing is sent.

```bash
drbench short-run --dry-run
```

This prints which documents will be sent, how many pages they are, and the
cost per system at list price. It needs no key.

### Step 4. Run

```bash
drbench short-run
```

What happens, in order:

1. The plan and the cost table are printed.
2. Your keys are checked. A missing key stops the run and prints the exact
   `export` line to fix it.
3. You are asked `Send these documents to the systems above and spend the
   amounts listed? [y/N]`. Anything but `y` sends nothing.
4. The datasets are downloaded: DocILE from Rossum with your token,
   Kleister-Charity (1.7 GB) and LongExtractBench (360 MB) from Hugging Face.
5. Every document goes to every system, four documents in flight per system.
6. The outputs are graded.
7. The results table is printed, with the same columns as ours.

Useful variations:

```bash
drbench short-run --systems reducto,deepread    # only the systems you have keys for
drbench short-run --yes -j 8                    # skip the question, 8 documents in flight per system
drbench full-run                                # every document of all three benchmarks: 30,803 pages per system, about $9,900
```

`--systems` takes system ids (`reducto:extract`, `extend:operator`) or provider
names (`reducto` means both Reducto modes, `deepread` means extract and
deep-extract). The seven ids are listed under [What it costs](#what-it-costs).

### Step 5. Read your results

- The table at the end of the run is your result, in the same format as the
  one at the top of this page.
- Every raw output is saved as `runs/<benchmark>/<system>/<document>.json`.
- The scores are in `runs/<benchmark>/scores.json`.
- You can re-score at any time without a key:

```bash
drbench grade --dataset charity --ids datasets/charity/sample-40.txt
drbench grade --dataset longextract --ids datasets/longextract/sample-20.txt
drbench report
```

### If something stops

| What you see | What it means | What to do |
|---|---|---|
| `missing API key(s)` and an `export` line | A system you asked for has no key | Export it and rerun, or pass `--systems` with the systems you have keys for |
| `stopped before every document was sent` | A vendor answered 401, 402 or 403: bad key, no credit, or no access | Fix that account and rerun the same command. Only the documents never sent are sent now |
| The run was interrupted | Nothing is lost | Rerun the same command. Documents that already have an output are skipped |
| A document shows as failed | The vendor timed out or returned an error after the retries. It scores 0, like in our table | To retry it: `drbench run --dataset <benchmark> --system <id> --retry-failures`, then `drbench grade` |
| `not run: DocILE` | No `DOCILE_TOKEN` and no local download | Get a token at docile.rossum.ai, export it, rerun |

## What it costs

Every price is what a self-serve customer pays per 1,000 pages, as of October
2026. The vendors bill their own accounts at their list rate, which is what
they charged us for the published run. DeepRead's share is paid with the
credits on your DeepRead account. Page counts come from the PDFs themselves.

| System | `--systems` id | $ / 1k pages | Short run (2,614 pages) | Full run (30,803 pages) |
|---|---|---:|---:|---:|
| DeepRead extract | `deepread:extract-selfhost` | $15 | $39 | $462 |
| DeepRead deep-extract | `deepread:deep-extract` | $35 | $91 | $1,078 |
| Reducto Extract | `reducto:extract` | $20 | $52 | $616 |
| Reducto Deep Extract | `reducto:deep-extract` | $40 | $105 | $1,232 |
| Extend Performance | `extend:performance` | $62.50 | $163 | $1,925 |
| Extend Operator | `extend:operator` | $87.50 | $229 | $2,695 |
| LandingAI ADE | `landingai:dpt-3-pro` | $61 | $159 | $1,879 |
| **All seven** | | | **about $840** | **about $9,900** |

Of the short run, about $710 goes to the vendor accounts and about $130 to
DeepRead credits. Of the full run, about $8,350 to the vendors and about
$1,540 to DeepRead. `drbench` prints this table for the systems you chose and
asks before sending anything. DeepRead extract runs on DeepRead's own OCR
engine, which the API calls `pipeline=extract-selfhost`; that is the engine
behind the "DeepRead extract" row.

## How we measure

1. **Same input.** Every system gets the same PDF and the same JSON Schema. The
   schema's field descriptions are the only instructions. Nothing is tuned per
   vendor, and every vendor runs at its default settings.
2. **One file per document.** Each system's output is saved as one JSON file
   under `runs/<benchmark>/<system>/`, with the request's timing and usage.
3. **Same scorer.** The same code compares every output to the benchmark's
   answer key. Formatting differences are not errors: upper or lower case,
   `$1,200` against `1200`, `3/4/2020` against `2020-03-04`. Wrong or missing
   values are errors. LongExtractBench is scored by the benchmark's own grader,
   where every row of every table counts.
4. **One number.** Accuracy is the share of a document's answer-key values the
   system got right, averaged over the documents. A document the system did
   not return scores 0, so a system cannot improve its number by failing on
   hard documents.

The published table additionally lets a reviewer model accept a difference it
judges immaterial, such as a street line with the district appended.
`drbench grade` does not, which is why its Kleister-Charity numbers below are
lower. The exact matching rules, how the answer-key errors we found are
handled, and the benchmarks' own metrics (F1, precision, recall), which
`drbench grade` also reports, are in [docs/methodology.md](docs/methodology.md).

### How we chose the documents

No document was picked by hand. Each sample is cut by a fixed rule decided
before any system was run, and every system got the same files.

| Benchmark | Rule | Documents | Pages | List |
|---|---|---:|---:|---|
| DocILE | all of the validation split | 500 | 636 | `datasets/docile/val_docids.txt` |
| Kleister-Charity | the first 40 of 440, in the dataset's own `documents.txt` order | 40 | 1,143 | [`datasets/charity/sample-40.txt`](datasets/charity/sample-40.txt) |
| LongExtractBench | the 20 shortest of 50, by page count | 20 | 835 | [`datasets/longextract/sample-20.txt`](datasets/longextract/sample-20.txt) |

The rules look at nothing but order and length, so they cannot favour anyone.
Shorter documents are easier for every system alike. The full
LongExtractBench set is 19,528 pages, and one document alone is 11,622, which
is what makes the full run cost what it does.

## Re-score our outputs, no key needed

Every output of the 13 October run on Kleister-Charity and LongExtractBench is
committed under [`runs/`](runs/), one file per document and system, so anyone
can re-score it offline:

```bash
pip install -e ".[dev]"
drbench grade --dataset charity --ids datasets/charity/sample-40.txt
drbench grade --dataset longextract --ids datasets/longextract/sample-20.txt
```

The table at the top was scored by our internal scorer. `drbench grade` on the
committed outputs gives:

| System | Kleister-Charity (40 docs) | LongExtractBench (20 docs) |
|---|---:|---:|
| DeepRead extract | 80.6 | 97.6 |
| Extend Operator | 84.1 | 99.6 |
| Reducto Deep Extract | 80.6 | 94.9 |
| Extend Performance | 80.9 | 77.5 (19/20) |
| LandingAI ADE | 80.3 | 70.8 (18/20) |
| Reducto Extract | 81.3 | 44.0 |

LongExtractBench agrees to the decimal for five systems, since both scorers
run micro1's grader. Kleister-Charity is 8 to 11 points lower for every system
because `drbench grade` applies only the benchmark's own matching rule, an
upper-cased exact `field=value` match after Kleister's normalisation, while our
scorer also accepts a value a reviewer model judges immaterially different.
The ranking is close either way. Reducto Extract's LongExtractBench score is
3.6 points lower here because on six documents where it returned under 1% of
the rows, our scorer credited it with more than the strict "every missed row
counts as wrong" rule gives.

The committed DeepRead outputs are the 13 October `extract` run (97.6 on
LongExtractBench, 91.7 on Kleister-Charity by our scorer). The 15 and 16
October reruns behind the table at the top, and the deep-extract outputs, are
not yet committed. `scripts/import_oct2026_run.py` documents how `runs/` was
assembled.

## Datasets, credits and licences

All credit for the datasets, the annotations and the metrics goes to their
authors. What is ours is the harness, the schemas, the label corrections and
the results.

| Benchmark | Made by | Paper / page | Code and data | Licence |
|---|---|---|---|---|
| **Kleister-Charity** | Applica.ai — Stanisławek, Graliński, Wróblewska et al. | [Kleister: Key Information Extraction Datasets Involving Long Documents with Complex Layouts](https://arxiv.org/abs/2105.05796), ICDAR 2021 | [github.com/applicaai/kleister-charity](https://github.com/applicaai/kleister-charity) | no licence file; public UK Charity Commission filings |
| **DocILE** | Rossum — Šimsa, Šulc, Uřičář et al. | [DocILE Benchmark for Document Information Localization and Extraction](https://arxiv.org/abs/2302.05658), ICDAR 2023 | [github.com/rossumai/docile](https://github.com/rossumai/docile), [docile.rossum.ai](https://docile.rossum.ai) | non-commercial research only; download with your own token |
| **LongExtractBench** | micro1 (commissioned by Reducto) | [micro1.ai/benchmark/long-extraction](https://www.micro1.ai/benchmark/long-extraction) | [github.com/micro1-research/longextract-bench](https://github.com/micro1-research/longextract-bench), [micro1-inc/longextract-bench-50](https://huggingface.co/datasets/micro1-inc/longextract-bench-50) | code MIT, labels CC-BY-4.0 |

Kleister-Charity and LongExtractBench are fetched from our Hugging Face
mirrors, pinned to exact revisions so a run today downloads the same bytes we
used. DocILE is fetched from Rossum with your own token. Full citations, the
BibTeX entries and what each system receives are in
[docs/datasets.md](docs/datasets.md).

## Results history

- **16 October 2026.** DeepRead deep-extract added to the table and to the
  default run. DeepRead's two rows rerun after accuracy fixes. Every vendor's
  DocILE and Kleister-Charity outputs re-scored with the same scorer settings
  as ours, which raised each vendor's numbers by 1 to 3 points.
- **13 October 2026.** First published run: six systems, 2,614 pages each.

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
terms, listed above, in [docs/datasets.md](docs/datasets.md) and on each
dataset card. The vendored LongExtractBench grader is MIT
([THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)).
Questions: hello@deepread.tech.
