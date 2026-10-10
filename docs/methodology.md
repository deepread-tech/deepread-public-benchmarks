# Methodology

## What every system gets

The same PDF and the same JSON Schema. The schema is the only instruction: each
field has a name, a type and a one-line description.

- **LongExtractBench** ships its own schema per document; it is sent unchanged.
- **Kleister-Charity** and **DocILE** have no JSON Schema of their own, so ours
  (`datasets/<name>/schema.json`) lists the benchmark's fields with the
  benchmark authors' own definitions: the field list in the Kleister README, and
  Table 1 of the DocILE paper (DocILE's tax breakdown fields are lists, one
  entry per line of the breakdown). Nothing in them was written or tuned
  against any system's output.

Each system runs with its vendor's default settings ([systems.md](systems.md)).

## What is saved

One file per (document, system), `runs/<benchmark>/<system>/<doc id>.json`:

```json
{"result": {...the values...}, "_meta": {"status": "ok", "latency_s": 42.1, "usage": {"job_id": "...", "credits": 120}}}
```

Scoring reads only these files, so anyone can re-score a run without API keys
(`drbench grade`) and check any document by hand.

A document is **completed** when the API returned a non-empty JSON object. It
**failed** when the API returned an error or nothing, or timed out after
retries. A failed document is scored as an empty answer (zero), and every table
shows the completed count.

## The score

The same definition on all three benchmarks:

> **Score (F1) = 2 × correct values ÷ (values the system returned + values in the answer key)**

- **Precision** = correct ÷ returned: how much of what the system said is right.
- **Recall** = correct ÷ answer key: how much of the answer the system found.
- F1 combines both, so a system cannot raise its score by guessing: a made-up
  value lowers precision, a missed value lowers recall.

A value is correct when it matches the answer key after removing formatting
differences that do not change the content: upper/lower case, spacing,
thousands separators, currency symbols, `100.0` vs `100`, and date formats
(`3/4/2020` and `2020-03-04`). A wrong value is both returned and not correct.

### Kleister-Charity

The benchmark's own metric, F1 (UC) from the official `config.txt`: each
document's values become `field=VALUE` labels, normalised as the Kleister README
prescribes (spaces as `_`, dates as `YYYY-MM-DD`, money as a number with two
decimals), upper-cased, and compared as sets. Counts are pooled over all 440
documents. The implementation matches the official GEval 1.14.2.0 scorer
within rounding on a real run (`tests/test_charity.py`). Dates are read day-first,
as on UK documents.

### DocILE

Value-level F1 over the KILE fields: every (document, field, value) in the
official annotations is one item to find; a field can have several values (for
example several tax rates). Amounts are compared as numbers, dates as ISO dates
(month-first when ambiguous, as on US documents), currency symbols as ISO codes.
Counts are pooled over all 500 documents. DocILE's official KILE metric also
requires the location of each value on the page; not every API returns
locations, so that part is left out for all systems.

### LongExtractBench

Rows of each table are paired with the answer key's rows by micro1's grader
(`src/drbench/graders/longextract_grading.py`, vendored unmodified, MIT): by an
inferred key such as a year or a name, then by content. Values are compared
with micro1's `canonical()` normaliser. Correct values are those in paired rows
and document-level fields that match; values in rows the system invented count
as returned, values in rows it missed count as expected. Empty values and
placeholders (`n/a`, `-`) count as neither. F1 is computed per document and
averaged over all 50 documents, so an 11,622-page report weighs as much as a
22-page one.

micro1's own three numbers are reported beside the score in `scores.json`: row
precision, row recall, and leaf accuracy (correct values among the rows the
system matched), averaged over completed documents as on micro1's leaderboard.

## Price and speed

**Price per 1,000 pages** is the run's cost on the documents a system completed,
divided by their pages: list price × pages for per-page vendors, reported
credits × credit price for credit-billed vendors ([systems.md](systems.md)).

**Time per document** is wall-clock from the first request to the final result,
including the vendor's queue, as a customer experiences it. The tables show the
median over completed documents.

## Answer-key corrections

Headline scores use each benchmark's official answer key as published. Answer
keys contain mistakes, so for Kleister-Charity and DocILE we also publish
corrections (`datasets/<name>/errata/label_fixes.csv`: one row per change with
the old label, the new one and the reason), and `drbench grade --labels
corrected` scores every system against them. They are optional: the table at
the top of the README always uses the official labels. They were found by
checking fields where a DeepRead output disagreed with the label against the
document itself, so they are a list of label errors, not a neutral re-annotation.

## Scores are a point in time

The APIs are services that change; the benchmarks, the schemas and the scoring
do not. Every output records when it was made and the vendor's job ids.
Running `drbench run` yourself makes your own run, not a copy of ours; scoring
either is deterministic.
