# Methodology

Every system gets the same input: the same PDF and the same JSON Schema, with
the field descriptions as the only instructions. Every output is graded by the
same deterministic code against the same answer key. Nothing is tuned per
vendor; the only vendor-specific code is the adapter that moves the PDF and
schema into each API's request shape (see [providers.md](providers.md)).

## 0. The headline number: accuracy

The README shows one number per system and benchmark: **accuracy, the share
of answer-key values the system got right**, over every document in the
benchmark. A document the system failed to process counts as all wrong.

- Kleister-Charity and DocILE: correct values ÷ all values in the answer key,
  pooled over all documents (in the benchmarks' terms, the recall of their
  official metric).
- LongExtractBench: per document, correct values ÷ all answer-key values
  (cells of every answer-key row, including rows the system missed, plus the
  document-level fields), averaged over the 50 documents.

`drbench grade` also reports each benchmark's own metrics — F1, precision and
recall for Kleister-Charity and DocILE, micro1's row precision, row recall and
leaf accuracy for LongExtractBench — in `runs/<dataset>/scores.json`, defined
in §3 below.

## 1. The unit of evaluation

A document is one PDF with a JSON Schema and a ground truth. A run is one
system over every document of a dataset. Each (document, system) pair produces
one envelope, `runs/<dataset>/<system>/<doc id>.json`:

```json
{"result": {...the extraction...}, "_meta": {"system": "...", "status": "ok", "latency_s": 42.1, "usage": {...}}}
```

The grader reads only envelopes, so anyone can re-grade a committed run
without API keys (`drbench grade`), and anyone can inspect why a document
scored the way it did.

## 2. Success and failure

Each pair is exactly one of:

| State | Meaning |
|---|---|
| success | the system returned a non-empty JSON object, which is graded |
| failure | a failure marker (the API errored or timed out after retries), an empty result, a non-object result, or no output file |

The leaderboard shows the completed count next to every score. How a failed
document affects the score depends on the benchmark's own convention, kept
here so our numbers stay comparable with the benchmark's published ones:

- Kleister-Charity and DocILE: the official metrics score every document; a
  failed document is an empty prediction (all of its labels are misses).
- LongExtractBench: as on micro1's leaderboard, accuracy is averaged over the
  documents the system completed. Read it together with the completed count.

## 3. The metrics

### Kleister-Charity — F1 (UC), the benchmark's metric

Each document's labels are `field=value` tokens (8 fields). A system's
extraction is turned into the same tokens using the normalisation the Kleister
README prescribes: spaces become `_`, dates become `YYYY-MM-DD`, money becomes
a number with two decimals. Tokens are upper-cased ("UC") and compared as sets
per document; true/false positives and false negatives are pooled over all 440
documents and turned into precision, recall and F1. That is exactly GEval's
`MultiLabel-F1:u`, the headline of the official `config.txt`.
`drbench grade` also reports the case-sensitive F1, the per-field F1s, the mean
per-document F1 and the share of documents with every label right.

The implementation (`src/drbench/datasets/charity.py`) is tested against GEval
1.14.2.0 output on a real run (`official/kleister_charity/results/run478`,
scored both with the official and the corrected labels).

### DocILE — field F1 (value match)

The KILE task labels 33 field types per document; a field type can occur more
than once (several tax rates, several IDs). Each (document, field, value) in
the annotations is one item. A system's values for the field are matched to
those items after light normalisation that folds formatting, not content:
whitespace and case; amounts as numbers (`$1,234.50` = `1234.50`); dates to
ISO, month-first when ambiguous (US documents); currency symbols to ISO codes
(`$` = `USD`), which is also how the ground truth is read. Pooled precision,
recall and F1 over all 500 documents; per-field F1 is reported too.

DocILE's official KILE metric additionally requires each value's location on
the page to overlap the annotated box. Not every API returns locations, so the
leaderboard uses this text-only variant for all systems. DeepRead's
location-aware official KILE score is reproduced separately in
[`official/docile`](../official/README.md).

### LongExtractBench — the benchmark's grader, unmodified

`src/drbench/graders/longextract_grading.py` is micro1's grader as published
(MIT). Rows of the schema's top-level arrays are paired by a key inferred from
the ground truth, then by content; **row precision** and **row recall** count
matched rows; **leaf accuracy** is the share of exactly-right values among the
cells of matched rows plus the document-level fields, after micro1's
`canonical()` normaliser (case, whitespace, thousands separators, `100.0` vs
`100`, `$`/`%`, accents, leading zeros, placeholder markers). Rows a system
missed or invented move precision and recall, not leaf accuracy, so the three
numbers are only meaningful together. Full description in micro1's
[methodology](https://github.com/micro1-research/longextract-bench/blob/main/docs/methodology.md).

## 4. Official and corrected labels

Headline scores use each benchmark's **official labels as published**. For
Kleister-Charity and DocILE we also publish label errata (`datasets/*/errata/`)
and `drbench grade --labels corrected` scores against them. Every change is one
CSV row with the old label, the new one (empty = removed), a confidence flag
and the reason. How they were made: every field where a DeepRead extraction
disagreed with the label was checked against the document text (PP-OCR,
Mistral OCR and the PDF text layer) and then ruled by a strong model against
the original field definitions, not our prompts. Only labels the document does
not support were changed: values printed nowhere, rounded figures, prior-year
columns, the accountant's address instead of the charity's, vendor and customer
swapped, truncated text. DeepRead's own extraction errors were left as
failures. The gap between an official and a corrected score measures label
noise, not an easier test — every system is scored against the same corrected
set.

## 5. Latency and cost

Latency is wall-clock from the first request for a document to the final
result, including the vendor's queue, as a client experiences it; the table
shows the median over completed documents. Vendor-reported usage (pages,
credits, job ids) is kept in each envelope's `_meta.usage` for cost estimates;
list prices are in [providers.md](providers.md).

## 6. Scores are a point in time

The systems are services that change; the grader and the pinned datasets do
not. Every committed run records its date and the vendor's job ids. Running
`drbench run` yourself produces your own run, not a copy of ours, and
`drbench grade` on any run — ours or yours — is deterministic.
