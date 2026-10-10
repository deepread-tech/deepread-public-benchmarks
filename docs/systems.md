# Systems

A **system** is one vendor product, called the way a new self-serve customer
would call it: the vendor's default settings, at the vendor's pay-as-you-go
list price. The whole configuration is
[`src/drbench/systems.py`](../src/drbench/systems.py); `drbench systems` prints it.

What every system receives is the PDF and the benchmark's JSON Schema, and
nothing else, apart from at most one option: the switch that selects a
product the vendor sells under its own name and price. No prompts, no tuned
settings, no post-processing of values.

| System id | Vendor | Product | Only option sent | List price (checked 2026-10-09) | Key |
|---|---|---|---|---|---|
| `deepread-extract` | DeepRead | Extract | `pipeline=extract` | $15 per 1,000 pages | `DEEPREAD_API_KEY` |
| `deepread-deep-extract` | DeepRead | Deep Extract | `pipeline=deep-extract` | $35 per 1,000 pages | `DEEPREAD_API_KEY` |
| `reducto-extract` | Reducto | Extract | none | $20 per 1,000 pages | `REDUCTO_API_KEY` |
| `reducto-deep-extract` | Reducto | Deep Extract | `settings.deep_extract=true` | $40 per 1,000 pages | `REDUCTO_API_KEY` |
| `extend-performance` | Extend | Extract (Performance) | none | $0.0125 per credit, credits as reported (≈ 5 per page) | `EXTEND_API_KEY` |
| `extend-operator` | Extend | Operator | `config.baseProcessor=extraction_operator` | $0.0125 per credit, credits as reported (≈ 7 per page) | `EXTEND_API_KEY` |
| `landingai-ade` | LandingAI | Agentic Document Extraction | none | $0.01 per credit, credits as reported | `VISION_AGENT_API_KEY` |

Pricing pages: [DeepRead](https://deepread.tech/pricing),
[Reducto](https://reducto.ai/pricing), [Extend](https://www.extend.ai/pricing),
[LandingAI](https://landing.ai/pricing). Prices change; the date above is when
they were last checked, and every committed run records its own date.

**How cost is computed.** For a vendor with a flat per-page price: pages ×
price. For a vendor that bills in credits: the credits the API reported for
each job × the list price of a credit, so the cost is what the vendor actually
charged. Pages are counted from the PDFs. Only completed documents are costed.

## Getting keys

- **DeepRead**: sign up at <https://app.deepread.tech>, then Dashboard → API keys.
  New accounts get 2,000 free pages a month.
- **Reducto**: sign up at <https://studio.reducto.ai> (Standard plan, self-serve),
  then API Keys in the sidebar. New accounts get free credit.
- **Extend**: sign up at <https://dashboard.extend.ai> (pay as you go), then
  create an API key. New accounts get 10,000 free credits.
- **LandingAI**: sign up at <https://ade.landing.ai> (self-serve), then Settings →
  API key. New accounts get free credits.

## How each API is called

### DeepRead

`POST /v1/process` (multipart: `file`, `schema`, `pipeline`) returns a job id;
`GET /v1/jobs/{id}` is polled until it ends. The extraction is
`extraction.fields`, a list of `{key, value, needs_review, ...}`, flattened to
`{key: value}`. Documents over the plan's page limit (1,000 pages on Standard)
are refused and count as failures.

### Reducto

`POST /upload` returns a `file_id`; `POST /extract_async` with `input` and
`instructions.schema`, polled on `GET /job/{id}`. Everything else is Reducto's
default (citations are off by default). When Reducto splits a long document,
it returns one extraction per part; the parts are joined into one object (table
rows concatenated in order, the first non-empty value for other fields).

micro1's LongExtractBench runs Reducto with two further options: an `alpha`
model setting that Reducto does not document, and agentic table parsing. They
are not defaults, so they are not used here.

### Extend

`POST /files/upload` returns a file id; `POST /extract_runs` with `file.id` and
`config.schema`, polled on `GET /extract_runs/{id}`. Everything else is
Extend's default, which is the `extraction_performance` processor. Extend only
accepts a stricter form of JSON Schema: scalar fields must allow `null`, objects
must set `additionalProperties: false`, `$ref`s must be inlined, and `id` is a
reserved key. The adapter makes exactly those changes and nothing else (no
field, type or description changes), and maps `id` back in the output.

### LandingAI ADE

ADE extracts from Markdown, so each document is a parse job
(`POST /v2/parse/jobs` with the PDF) and an extract job (`POST /v2/extract/jobs`
with the Markdown and the schema). No model or tier is sent, so both run on
LandingAI's defaults (DPT-3 Pro for parsing at the time of writing). The
Markdown is kept next to the output so a retry does not pay for the parse again.

## Adding a system

1. Write `src/drbench/providers/<vendor>.py`: a class constructed with the
   system's `settings`, with `extract(pdf, schema, sidecar) -> (values, usage)`
   (see [`base.py`](../src/drbench/providers/base.py)). Send the file, the
   schema and `settings`, nothing else. Put `credits` in `usage` if the vendor
   bills in credits.
2. Register it in `providers/__init__.py`, and add one `System` per product to
   `systems.py` with its list price and the pricing page it came from.
3. Document the exact API calls in this file.

The rule for a new system is the same as for the others: the vendor's defaults,
plus at most the switch for a product the vendor sells under its own name and price.
