# DeepRead on public extraction benchmarks

Everything needed to reproduce DeepRead's scores on the public benchmarks shown on
deepread.tech/benchmarks: document lists, the official scorers, our exporters to
each scorer's format, our predictions, and our label errata.

**Internal for now.** Do not share outside DeepRead until the owner decides to publish.

## Results

| Benchmark | Split | Metric (official scorer) | Official labels | Corrected labels | Run |
|---|---|---|---|---|---|
| Kleister-Charity | dev-0, 440 docs | F1, upper-cased (GEval 1.14.2.0) | 80.9 | 84.4 | `kleister_charity/results/run478` |
| DocILE | validation, 500 docs | KILE AP / F1 (`docile_evaluate`) | 0.263 / 0.460 | – | `docile/results/run479` |

Pipeline: DeepRead `extract-selfhost`, run on staging (October 2026).
Field prompts were tuned with the DeepRead optimizer on each benchmark's
official **training** split only; no evaluation document was used.

## Data (pinned)

| Benchmark | Source | Version | Evaluation split |
|---|---|---|---|
| Kleister-Charity | https://github.com/applicaai/kleister-charity | commit `2309f486` (2021-08-18, latest) | `dev-0` (440 docs). `test-A` labels were never released and its scoring server (gonito.net) is offline, so `dev-0` is the largest scoreable split. |
| DocILE | https://github.com/rossumai/docile (dataset via `download_dataset.sh`, needs a free token from docile.rossum.ai) | repo commit `45f1f00` | `val` (500 docs). The test split is scored only on the RRC server. |
| LongExtractionBench | https://github.com/micro1-research/longextract-bench, data `micro1-inc/longextract-bench-50` | HF snapshot `d4ca332f` | the 50 public documents (the published results cover 225, mostly private) |

## Reproduce

Requirements: Python 3.11+, `httpx`; Docker (for GEval); a DeepRead API key.

```bash
export DEEPREAD_API_KEY=...                       # and DEEPREAD_API_URL for a non-production endpoint
```

### Kleister-Charity (dev-0)

```bash
git clone https://github.com/applicaai/kleister-charity && (cd kleister-charity && git checkout 2309f486)
# fetch the dev-0 PDFs with git-annex as the Kleister README describes, then:
xzcat kleister-charity/dev-0/in.tsv.xz | cut -f1 | sed 's|^|kleister-charity/documents/|' > dev0.txt
python common/run_deepread.py dev0.txt kleister_charity/schema.json raw_kleister
python kleister_charity/export.py raw_kleister kleister-charity out_kleister
# official scorer, built from its pinned source (gonito.net, which served the binary, is offline)
docker build -t geval:1.14.2.0 -f kleister_charity/Dockerfile.geval .
cp kleister-charity/config.txt kleister-charity/in-header.tsv out_kleister/
cp kleister-charity/dev-0/expected.tsv out_kleister/dev-0/
docker run --rm -v $PWD/out_kleister:/c -w /c geval:1.14.2.0 -t dev-0     # headline: the F1 (UC) row
```

Check the scorer build: scoring the official baseline's predictions
(`git show origin/baseline:dev-0/out.tsv` in the Kleister repo) gives F1 (UC) 23.7.

Corrected labels: replace `dev-0/expected.tsv` with
`errata/kleister_charity/dev-0.expected.corrected.tsv` and score again.
Our predictions for run 478 are in `kleister_charity/results/run478/out.tsv`;
scoring them reproduces `geval_official_labels.txt` / `geval_corrected_labels.txt`.

### DocILE (validation)

```bash
git clone https://github.com/rossumai/docile && cd docile && ./download_dataset.sh TOKEN annotated-trainval data/docile --unzip && cd ..
sed "s|^|docile/data/docile/pdfs/|; s|$|.pdf|" docile/val_docids.txt > docile_val.txt   # the 500 val PDFs
python common/run_deepread.py docile_val.txt docile/schema.json raw_docile
python docile/export.py raw_docile kile_predictions.json
(cd docile && uv run docile_evaluate --task KILE --dataset-path data/docile --split val --predictions ../kile_predictions.json)
```

Our predictions for run 479: `docile/results/run479/kile_predictions.json.gz`
(gunzip, then `docile_evaluate` as above reproduces `kile_val_report.txt`).

DocILE's KILE metric counts a field only when its **location** also matches the
labelled box; `docile/export.py` documents how DeepRead's field boxes are mapped.

### LongExtractionBench

`longextractbench/deepread_provider.py` is a provider for micro1's harness, in the
same shape as their Reducto/Extend/LlamaExtract adapters. Copy it to
`src/longextract_bench/providers/deepread.py`, add `"deepread"` to `PROVIDERS`, then
`lxbench-run --providers deepread`, `lxbench-grade`, `lxbench-report`.
DeepRead's API accepts field descriptions up to 2,000 characters and schemas up to
256 KB, which these schemas need.

## Label errata

`errata/<dataset>/label_fixes.csv` lists every label we changed, with the reason and
a confidence flag; `ground_truth_clean.json` is the full corrected label set (same
keys as the dataset's `ground_truth.json` in deep-read-datasets).

How they were made: every field where our extraction disagreed with the label was
checked against the document text (PP-OCR, Mistral OCR and the PDF text layer), then
ruled by a strong model against the original field definitions (not our prompts).
Only labels the document does not support were changed: values printed nowhere,
rounded figures, prior-year columns, the accountant's address instead of the
charity's, vendor and customer swapped, truncated text. Our own extraction errors
were left as failures. Headline scores always use the official labels.
