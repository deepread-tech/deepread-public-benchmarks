# Datasets

Three public benchmarks, pinned to exact versions. `drbench fetch` downloads
Kleister-Charity and LongExtractBench from DeepRead's Hugging Face datasets
(copies of the originals, assembled by `scripts/build_hf_datasets.py`, every
file's origin listed on the dataset card) and DocILE from Rossum with your own
token, because its terms allow no re-hosting. What is committed in this
repository is the JSON Schema each system receives, the document lists, and
our label errata.

| Dataset | Split | Documents | Pages | Fields | Download | Original / pin | Licence |
|---|---|---|---|---|---|---|---|
| Kleister-Charity | dev-0 | 440 | multi-page annual reports | 8 scalars | [deepread-tech/kleister-charity-dev0](https://huggingface.co/datasets/deepread-tech/kleister-charity-dev0) | [applicaai/kleister-charity](https://github.com/applicaai/kleister-charity) @ `2309f486` | no licence file; public UK Charity Commission filings |
| DocILE | validation | 500 | 1–3 page business documents | 33 KILE field types | your own token ([access form](https://docile.rossum.ai)) | [rossumai/docile](https://github.com/rossumai/docile), dataset v1.0 | non-commercial research only, no redistribution |
| LongExtractBench (public subset) | the 50 public documents | 50 | 22–11,622 pages, median 86 | per-document schema, large row arrays | [deepread-tech/longextract-bench-50](https://huggingface.co/datasets/deepread-tech/longextract-bench-50) (mirror) | [micro1-inc/longextract-bench-50](https://huggingface.co/datasets/micro1-inc/longextract-bench-50) @ `d4ca332f` | labels CC-BY-4.0; PDFs keep their original rights |

## Kleister-Charity

UK charities' annual reports with eight fields: charity name and number,
street, town and postcode of the charity's own address, report date, annual
income and spending. `test-A` labels were never published and the scoring
server (gonito.net) is offline, so `dev-0` is the largest split anyone can
score.

`drbench fetch charity` downloads
[deepread-tech/kleister-charity-dev0](https://huggingface.co/datasets/deepread-tech/kleister-charity-dev0)
(1.7 GB): the 440 PDFs, `documents.txt` (the official order), the official
`expected.tsv`, our corrected labels and errata, and the schema. The copy was
assembled by `scripts/build_hf_datasets.py` from the Kleister repository at the
pinned commit: labels and document list from a blob-less clone, PDFs from
Applica's public S3 bucket, where they are git-annex objects whose key is the
target of each `documents/<name>` symlink. Nothing was altered.

Schema: `datasets/charity/schema.json` — the eight fields with a one-sentence
description each. Errata: `datasets/charity/errata/label_fixes.csv` (336
changes across 190 documents; the most common is the auditor's address
labelled as the charity's) and `dev-0.expected.corrected.tsv`, the full
corrected label file in the official format.

## DocILE

Invoice-like business documents from the UCSF Industry Documents Library and
public procurement, annotated by Rossum for the DocILE 2023 benchmark. The KILE
task has 33 field types (document and order ids, dates, vendor and customer
names and addresses, amounts, tax details, bank details...). The validation
split is 500 documents; the test split is scored only on the organisers'
server.

Access is gated: fill the form at <https://docile.rossum.ai> and you receive a
token by email. Then `drbench fetch docile --token <TOKEN>` downloads the
annotated train+val archive (several GB), extracts only the 500 validation
documents and their annotations, and discards nothing else you may want — the
archive stays in `data/docile/`. If you already have the dataset,
`--source /path/to/annotated-trainval.zip` or `--source /path/to/extracted/dir`
reuses it.

The ground truth is built from the official `annotations/<id>.json`
`field_extractions` at grading time, so no DocILE labels are stored in this
repository. The document list is pinned in `datasets/docile/val_docids.txt`.

The dataset terms allow **non-commercial research use only** and forbid
redistribution. Comply with them: do not commit DocILE documents, OCR or
labels, and do not publish per-document values.

Schema: `datasets/docile/schema.json` — the 33 KILE field types with field
descriptions. Errata: `datasets/docile/errata/label_fixes.csv` (200 changes
across 144 documents, e.g. a letter O labelled where the document prints a
zero).

## LongExtractBench

micro1's public 50-document subset of a 225-document benchmark of long,
table-heavy documents: statistical releases, 10-K/10-Q filings, clinical and
regulatory reports, mostly English with a few German and Dutch documents. Each
document folder holds `document.pdf`, `schema.json` (a JSON Schema with large
array-of-rows fields plus a few document-level scalars, every field with a
natural-language description) and `ground_truth.json` (model-drafted, human
reconciled; median ~640 KB). The benchmark was commissioned by Reducto and
audited by micro1; the methodology and grader are published at
<https://github.com/micro1-research/longextract-bench>.

`drbench fetch longextract` downloads
[deepread-tech/longextract-bench-50](https://huggingface.co/datasets/deepread-tech/longextract-bench-50)
(~360 MB), a byte-identical mirror of micro1's revision `d4ca332f` with
micro1's dataset card kept on it, so the benchmark pins one stable copy. No
account is needed.

Note the sizes: 19,528 pages in total, one document of 11,622 pages. APIs
with page limits will fail some documents — that is reported as a failure, not
hidden.

## What each system receives

For every dataset the same `schema.json` goes to every system unchanged
(DeepRead reads `description` as the field instruction, as do Reducto and
LandingAI). The schemas for Kleister-Charity and DocILE were written by
DeepRead against each benchmark's **training** split; no evaluation document
was used.
