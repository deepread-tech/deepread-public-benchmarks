# Document extraction benchmarks

**Which document AI API pulls the right data out of a PDF, and what does it cost?**

We sign up for each commercial API like any new customer, send every one the
same PDFs and the same list of fields, and check the answers against three
public benchmarks. Everything is here — the code, the schemas, the raw outputs,
the scoring — so you can rerun it yourself with your own API keys.

## The rules

1. **Default settings, no tuning.** Every API runs with the vendor's default
   options. Nothing is tuned for a benchmark, for any vendor, including our own.
   The only option we ever set is the one that picks a product the vendor sells
   under its own name and price (for example Reducto's Deep Extract switch).
   [`src/drbench/systems.py`](src/drbench/systems.py) lists exactly what each
   system sends.
2. **List prices.** Every price is the vendor's published pay-as-you-go price,
   the one you pay when you sign up today. No discounts, no enterprise deals.
3. **Same input for everyone.** The same PDF and the same JSON Schema go to every
   API. The field descriptions in the schema are the benchmark authors' own
   definitions, word for word.
4. **Same scoring for everyone.** One piece of code scores every output against
   the benchmark's answer key.
5. **Failures count.** A document an API cannot process scores zero, and the
   table says how many documents each API completed.

## Results

<!-- results:begin -->
No committed runs yet. `drbench report --readme README.md` fills this table from `runs/`.
<!-- results:end -->

**Score** is F1, from 0 to 100: it goes up for every correct value and down for
every value that is missed or made up. **Price** is what the run cost per 1,000
pages at list price. Per-benchmark tables with precision, recall, completion and
speed: `drbench report`. Full definitions: [docs/methodology.md](docs/methodology.md).

DeepRead built this harness, and DeepRead is one of the APIs in the table. That
is why everything needed to check our numbers is public: run it yourself and
compare.

## The systems

| System | What it is | Price at list (checked 2026-10-09) |
|---|---|---|
| DeepRead Extract | DeepRead's standard extraction | $15 per 1,000 pages |
| DeepRead Deep Extract | DeepRead's high-accuracy extraction | $35 per 1,000 pages |
| Reducto Extract | Reducto's default extraction | $20 per 1,000 pages |
| Reducto Deep Extract | Reducto's agentic extraction | $40 per 1,000 pages |
| Extend Extract (Performance) | Extend's default extraction | 5 credits/page × $0.0125 ≈ $62.50 per 1,000 pages |
| Extend Operator | Extend's agentic extraction for table-heavy documents | ~7 credits/page × $0.0125 ≈ $87.50 per 1,000 pages |
| LandingAI ADE | LandingAI's parse (DPT-3 Pro) + extract | credits per page and per character, × $0.01 |

For credit-billed APIs the table uses the credits the API itself reported for
each job. Settings, API calls and sign-up links: [docs/systems.md](docs/systems.md).
Want another API in the table? See [adding a system](docs/systems.md#adding-a-system).

## The benchmarks

All three are public and were made by other teams. We only run APIs on them.

| Benchmark | Documents | What is extracted | Made by |
|---|---|---|---|
| [Kleister-Charity](https://github.com/applicaai/kleister-charity) | 440 UK charity annual reports, many of them scans | 8 fields: name, number, address, report date, income, spending | Applica.ai ([paper](https://arxiv.org/abs/2105.05796)) |
| [DocILE](https://docile.rossum.ai) | 500 invoices and order forms, 1–3 pages | 36 fields: ids, dates, parties, amounts, tax, bank details | Rossum ([paper](https://arxiv.org/abs/2302.05658)) |
| [LongExtractBench](https://github.com/micro1-research/longextract-bench) | 50 long reports, 22 to 11,622 pages | large tables, row by row, plus a few document-level fields | micro1 |

Versions, licences and citations: [docs/datasets.md](docs/datasets.md).

## Run it yourself

You need Python 3.10+ and an API key for each system you want to run. The runs
call paid APIs: all three benchmarks together are about 32,000 pages per
system, most of them in LongExtractBench. Start with `--limit 5`.

```bash
git clone https://github.com/deepread-tech/deepread-public-benchmarks
cd deepread-public-benchmarks
pip install -e .

drbench systems                       # what will be run, with settings and prices

# 1. API keys (only for the systems you run; sign-up links in docs/systems.md)
export DEEPREAD_API_KEY=...  REDUCTO_API_KEY=...  EXTEND_API_KEY=...  VISION_AGENT_API_KEY=...

# 2. benchmarks
drbench fetch charity                 # 1.7 GB
drbench fetch longextract             # 360 MB
drbench fetch docile --token TOKEN    # free token from docile.rossum.ai

# 3. run (paid; rerun the same command to resume)
drbench run longextract reducto-extract extend-performance --limit 5
drbench run charity deepread-extract reducto-extract extend-performance landingai-ade

# 4. score and print the tables (offline, no keys)
drbench grade charity
drbench report
```

Every output is saved as one JSON file per document in
`runs/<benchmark>/<system>/`, so you can open any document and see exactly what
each API returned and why it scored the way it did. `drbench grade` re-scores
saved outputs without calling any API.

## What is in this repository

```
src/drbench/systems.py     the systems: vendor, product, settings sent, list price
src/drbench/providers/     one small adapter per API (file + schema in, values out)
src/drbench/datasets/      one module per benchmark: download, answer key, scoring
src/drbench/graders/       micro1's LongExtractBench grader, unmodified (MIT)
datasets/                  the schema every system receives; answer-key corrections
runs/                      every raw output behind the table, and the scores
docs/                      methodology, systems, datasets
tests/
```

## Licence

Code and documentation: MIT ([LICENSE](LICENSE)). Each benchmark keeps its own
licence, listed in [docs/datasets.md](docs/datasets.md). Questions or a result
you cannot reproduce: open an issue, or write to hello@deepread.tech.
