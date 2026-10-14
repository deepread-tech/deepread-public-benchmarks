# Systems

Each system is one adapter in `src/drbench/providers/`. An adapter does three
things: send the PDF and the JSON Schema in the API's request shape, wait for
the job, and return the extraction as a plain JSON object. It does not change
field descriptions, add prompts or post-process values. Vendor job ids are
kept in a `<doc id>.job.json` sidecar while a document is in flight so that a
retry polls the job already paid for; `_meta.usage` in the output envelope
holds whatever the vendor reports (pages, credits, job ids).

Keys are read from environment variables (or a `.env` file via your shell);
each key is used only for that vendor's calls. Nothing takes a key as a
command-line flag, so no key ends up in your shell history.

| System id | Vendor | Mode | Key | API calls |
|---|---|---|---|---|
| `deepread:extract` | [DeepRead](https://deepread.tech) | `extract` pipeline | `DEEPREAD_API_KEY` | `POST /v1/process` → poll `GET /v1/jobs/{id}` |
| `deepread:deep-extract` (default) | DeepRead | `deep-extract` pipeline | `DEEPREAD_API_KEY` | same |
| `deepread:extract-selfhost` | DeepRead | `extract` on DeepRead's self-hosted OCR engine | `DEEPREAD_API_KEY` | same |
| `deepread:deep-extract-selfhost` | DeepRead | `deep-extract` on the self-hosted OCR engine | `DEEPREAD_API_KEY` | same |
| `reducto:deep-extract` (default) | [Reducto](https://reducto.ai) | Deep Extract (`settings.deep_extract = true`) | `REDUCTO_API_KEY` | `POST /upload` → `POST /extract_async` → poll `GET /job/{id}` |
| `reducto:extract` | Reducto | standard Extract | `REDUCTO_API_KEY` | same |
| `landingai:dpt-3-pro` (default) | [LandingAI ADE](https://landing.ai) | DPT-3 Pro parse + Extract | `VISION_AGENT_API_KEY` | `POST /v2/parse/jobs` → poll → `POST /v2/extract/jobs` → poll |
| `extend:performance` (default) | [Extend](https://extend.ai) | Extract, `extraction_performance` | `EXTEND_API_KEY` | `POST /files/upload` → `POST /extract_runs` → poll `GET /extract_runs/{id}` |
| `extend:operator` | Extend | Extract, `extraction_operator` (agent for long, table-heavy documents) | `EXTEND_API_KEY` | same |

## Getting keys

- **DeepRead**: sign up at <https://app.deepread.tech>, create an API key in the
  dashboard. New accounts include free pages.
- **Reducto**: sign up at <https://studio.reducto.ai> (self-serve), API Keys in
  the sidebar. New Standard accounts come with free usage credit.
- **LandingAI**: sign up at <https://ade.landing.ai> (self-serve, no card),
  Settings → API key. New accounts come with free credits that expire after
  90 days.
- **Extend**: sign up at <https://dashboard.extend.ai> (self-serve), Settings →
  API keys. New accounts come with 10,000 free credits.

Prices change; check each vendor's pricing page before a full sweep. What each
system cost us per page on the October 2026 run, which is also what
`drbench short-run` and `drbench full-run` use for their estimates
(`src/drbench/suite.py`):

| System | $ / 1,000 pages | How it is billed |
|---|---:|---|
| DeepRead extract | $15 | list price, paid in DeepRead credits |
| DeepRead deep-extract | $35 | list price, paid in DeepRead credits |
| Reducto Extract | $20 | list price |
| Reducto Deep Extract | $40 | list price |
| Extend Performance | $62.50 | 5 credits a page at $0.0125 (3 to extract + 2 to parse) |
| Extend Operator | $87.50 | 7 credits a page at $0.0125 (5 to extract + 2 to parse) |
| LandingAI ADE | $61 | credits per page parsed plus per character extracted; this is what the run averaged |

The short run is 2,614 pages per system and the full run 30,803
(LongExtractBench alone is 19,528 of them).

## Per-vendor notes

### DeepRead

Multipart `POST /v1/process` with `file`, `pipeline` and `schema` (the JSON
Schema as a string). The job is polled on `GET /v1/jobs/{id}`; the extraction
is `extraction.fields[]`, flattened to `{key: value}` with DeepRead's
per-field review wrappers removed. `DEEPREAD_API_URL` selects a non-production
endpoint.

### Reducto

`POST /upload` returns a `file_id`; `POST /extract_async` is called with
`input = file_id`, `instructions.schema = <the schema>`,
`settings.deep_extract` true or false by mode, `citations.enabled = false`
(plain values) and `async.priority = false`. This is the configuration micro1
used for Reducto on LongExtractBench. The job is polled on `GET /job/{id}`;
`result.result` is a list of extractions (one per document, more if Reducto
split the input) and a single-element list is unwrapped to the object.

### LandingAI ADE

ADE extracts from Markdown, not from the PDF, so each document is a parse job
(`POST /v2/parse/jobs`, multipart `document` + `model = dpt-3-pro-latest`)
followed by an extract job (`POST /v2/extract/jobs`, multipart with the
Markdown as a file and `schema` as JSON). The Markdown is cached next to the
output (`<doc id>.markdown.md`, git-ignored) so a retry of the extract step
does not pay for the parse again. ADE's documented limits at the time of
writing: 6,000 pages per PDF, so the largest LongExtractBench documents fail
the parse step — counted as failures. Schema-violation warnings from the
extract step are kept in `_meta.usage`.

### Extend

`POST /files/upload` (multipart `file`) returns a file `id`; `POST /extract_runs`
is called with `file.id` and an inline `config`: `baseProcessor` by mode
(`extraction_performance` or `extraction_operator`), `schema = <the schema>`
and `advancedOptions.citationsEnabled = false` (plain values). Requests carry
`x-extend-api-version: 2026-02-09`. The run is polled on
`GET /extract_runs/{id}` until `PROCESSED`, `FAILED` or `CANCELLED`; the
extraction is `output.value`. A run that fails with `OUT_OF_CREDITS` stops the
whole sweep like a rejected key would. Credits and the page count are kept in
`_meta.usage`.

## Adding a system

Write `src/drbench/providers/<vendor>.py` with a class exposing `name`,
`env_key` and `extract(pdf, schema, sidecar) -> (extraction, usage)` (see
`base.py`), register it in `providers/__init__.py`, and document the exact API
calls here. Keep it a dialect translation: the same schema, no extra prompting.
