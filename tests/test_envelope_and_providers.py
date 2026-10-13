import json

import pytest

from drbench import envelope
from drbench.cli import select
from drbench.datasets.base import Doc
from drbench.providers import make
from drbench.providers._http import unwrap_values
from drbench.providers.deepread import fields
from drbench.providers.extend import _run, to_extend_schema
from drbench.providers.reducto import normalise


def test_envelope_roundtrip_and_classification(tmp_path):
    out = tmp_path / "doc.json"
    envelope.write(out, system="x", result={"a": 1}, latency_s=1.23456, usage={"pages": 2})
    env = envelope.read(out)
    assert env["result"] == {"a": 1} and env["_meta"]["latency_s"] == 1.235
    assert envelope.classify(env) == ("success", None)
    envelope.write(out, system="x", result=None, latency_s=None, status="failed", error="boom")
    assert envelope.classify(envelope.read(out)) == ("failure", "boom")
    assert envelope.classify({"result": {}, "_meta": {}}) == ("failure", "empty result")
    assert envelope.classify({"result": [1, 2], "_meta": {}}) == ("failure", "result is not a JSON object")
    assert envelope.classify(None) == ("failure", "no output file")


def test_system_names():
    assert make("deepread").name == "deepread-deep-extract"
    assert make("deepread:extract").name == "deepread-extract"
    assert make("deepread:extract-selfhost").pipeline == "extract-selfhost"
    assert make("deepread:deep-extract-selfhost").name == "deepread-deep-extract-selfhost"
    assert make("reducto").name == "reducto-deep-extract"
    assert make("reducto:extract").name == "reducto-extract"
    assert make("landingai").name == "landingai-dpt-3-pro"
    assert make("extend").name == "extend-performance"
    assert make("extend:operator").name == "extend-operator"
    assert make("extend:operator").base_processor == "extraction_operator"
    with pytest.raises(ValueError):
        make("extend:light")


def test_extend_schema_dialect():
    schema = {
        "type": "object", "title": "T", "additionalProperties": False, "required": ["name", "rows"],
        "properties": {
            "name": {"type": "string", "description": "the name", "minLength": 1},
            "amount": {"type": ["number", "null"], "nullable": True},
            "either": {"type": ["number", "string", "null"]},
            "kind": {"type": "string", "enum": ["a", "b"]},
            "tags": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "rows": {"type": "array", "items": {"type": "object", "properties": {
                "n": {"type": "integer"}, "ok": {"type": "boolean"}}, "required": ["n"]}},
        },
    }
    assert to_extend_schema(schema) == {
        "type": "object", "title": "T", "required": ["name", "rows"],
        "properties": {
            "name": {"type": ["string", "null"], "description": "the name"},
            "amount": {"type": ["number", "null"]},
            "either": {"type": ["string", "null"]},
            "kind": {"type": ["string", "null"], "enum": ["a", "b", None]},
            "tags": {"type": "array", "items": {"type": "string"}},
            "rows": {"type": "array", "items": {"type": "object", "properties": {
                "n": {"type": ["integer", "null"]}, "ok": {"type": ["boolean", "null"]}}, "required": ["n"]}},
        },
    }


def test_extend_run_object_is_found_wrapped_or_bare():
    bare = {"object": "extract_run", "id": "exr_1", "status": "PROCESSED"}
    assert _run(bare) is bare
    assert _run({"success": True, "extractRun": bare}) is bare
    assert _run(None) == {}


def test_table_heading_names_a_sample():
    from drbench.datasets import DATASETS
    from drbench.report import table

    scores = {"dataset": "longextract", "labels": "official", "documents": 20,
              "sample": "datasets/longextract/sample-20.txt",
              "systems": {"x": {"summary": {"accuracy": 0.5, "completed": 20}, "docs": {}}}}
    heading = table(DATASETS["longextract"], scores).splitlines()[0]
    assert heading.endswith("— 20-document sample (datasets/longextract/sample-20.txt)")
    scores["sample"] = None
    assert "sample" not in table(DATASETS["longextract"], scores).splitlines()[0]


def test_select_keeps_file_order_and_rejects_unknown_ids(tmp_path):
    docs = [Doc(id=i, pdf=tmp_path / f"{i}.pdf", schema={}, ground_truth=None) for i in ("a", "b", "c")]
    assert select(docs, None) == docs
    ids = tmp_path / "ids.txt"
    ids.write_text("# a comment\nc\n\na\n")
    assert [d.id for d in select(docs, ids)] == ["c", "a"]
    ids.write_text("a\nzzz\n")
    with pytest.raises(SystemExit):
        select(docs, ids)


def test_deepread_fields_are_unwrapped():
    body = json.loads("""{"status": "completed", "extraction": {"fields": [
        {"key": "vendor_name", "value": "ACME", "needs_review": false},
        {"key": "lines", "value": [{"amount": {"value": 1.5, "hil_flag": false}, "desc": "x"}]}]}}""")
    assert fields(body) == {"vendor_name": "ACME", "lines": [{"amount": 1.5, "desc": "x"}]}


def test_reducto_result_is_collapsed_and_uncited():
    raw = [{"total": {"value": "12.00", "citations": [{"page": 1}]}, "items": [{"n": {"value": 1, "citations": []}}]}]
    assert normalise(raw) == {"total": "12.00", "items": [{"n": 1}]}
    assert normalise([{"a": 1}, {"a": 2}]) == [{"a": 1}, {"a": 2}]


def test_unwrap_leaves_plain_structures_alone():
    assert unwrap_values({"value": 1, "other": 2}, ("citations",)) == {"value": 1, "other": 2}
