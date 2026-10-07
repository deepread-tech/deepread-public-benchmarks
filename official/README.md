# Official scorers (DeepRead)

The leaderboard in the repository root grades every system with the same code
(see `docs/methodology.md`). This folder reproduces DeepRead's scores with each
benchmark's **own scorer** in its own format, as an independent check of the
numbers and of the metric re-implementations.

| Benchmark | Split | Metric (official scorer) | Official labels | Corrected labels | Run |
|---|---|---|---|---|---|
| Kleister-Charity | dev-0, 440 docs | F1 (UC), GEval 1.14.2.0 | 80.9 | 84.4 | `kleister_charity/results/run478` |
| DocILE | validation, 500 docs | KILE AP / F1, `docile_evaluate` | 0.263 / 0.460 | – | `docile/results/run479` |

Pipeline: DeepRead `extract-selfhost`, run in October 2026. Field prompts were
tuned with the DeepRead optimizer on each benchmark's official **training**
split only; no evaluation document was used.

Requirements: Python 3.11+, `httpx`; Docker (for GEval); a DeepRead API key.

```bash
export DEEPREAD_API_KEY=...                       # and DEEPREAD_API_URL for a non-production endpoint
```

## Kleister-Charity (dev-0)

```bash
drbench fetch charity                             # labels + the 440 PDFs under data/charity/
ls data/charity/pdfs/*.pdf > dev0.txt
python official/common/run_deepread.py dev0.txt datasets/charity/schema.json raw_kleister
python official/kleister_charity/export.py raw_kleister data/charity/kleister-charity out_kleister
# official scorer, built from its pinned source (gonito.net, which served the binary, is offline)
docker build -t geval:1.14.2.0 -f official/kleister_charity/Dockerfile.geval .
cp data/charity/kleister-charity/config.txt data/charity/kleister-charity/in-header.tsv out_kleister/
cp data/charity/kleister-charity/dev-0/expected.tsv out_kleister/dev-0/
docker run --rm -v $PWD/out_kleister:/c -w /c geval:1.14.2.0 -t dev-0     # headline: the F1 (UC) row
```

Check the scorer build: scoring the official baseline's predictions
(`git show origin/baseline:dev-0/out.tsv` in the Kleister repo) gives F1 (UC) 23.7.

Corrected labels: replace `dev-0/expected.tsv` with
`datasets/charity/errata/dev-0.expected.corrected.tsv` and score again.
Our predictions for run 478 are in `kleister_charity/results/run478/out.tsv`;
scoring them reproduces `geval_official_labels.txt` / `geval_corrected_labels.txt`,
and `tests/test_charity.py` checks that `drbench grade` gives the same numbers.

## DocILE (validation)

```bash
drbench fetch docile --token TOKEN                # the 500 val PDFs + annotations under data/docile/
ls data/docile/pdfs/*.pdf > docile_val.txt
python official/common/run_deepread.py docile_val.txt datasets/docile/schema.json raw_docile
python official/docile/export.py raw_docile kile_predictions.json
git clone https://github.com/rossumai/docile && cd docile
uv run docile_evaluate --task KILE --dataset-path ../data/docile --split val --predictions ../kile_predictions.json
```

Our predictions for run 479: `docile/results/run479/kile_predictions.json.gz`
(gunzip, then `docile_evaluate` as above).

DocILE's KILE metric counts a field only when its **location** also matches the
labelled box; `docile/export.py` documents how DeepRead's field boxes are mapped.

## LongExtractBench with micro1's harness

`longextractbench/deepread_provider.py` is a DeepRead provider for micro1's own
harness, in the same shape as their Reducto/Extend/LlamaExtract adapters. Copy
it to `src/longextract_bench/providers/deepread.py`, add `"deepread"` to
`PROVIDERS`, then `lxbench-run --providers deepread`, `lxbench-grade`,
`lxbench-report`. The grader is the same code `drbench` uses.
