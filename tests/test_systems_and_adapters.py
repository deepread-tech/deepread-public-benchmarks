import json

import pytest

from drbench import envelope
from drbench.datasets.docile import Docile
from drbench.providers import ADAPTERS
from drbench.providers._http import FatalError, poll, unwrap_values
from drbench.providers.deepread import fields
from drbench.providers.extend import from_extend, to_extend_schema
from drbench.providers.reducto import merge
from drbench.systems import SYSTEMS, Price


def test_every_system_has_an_adapter_a_price_and_a_key():
    for s in SYSTEMS.values():
        assert s.adapter in ADAPTERS
        assert (s.price.per_1k_pages is None) != (s.price.per_credit is None)
        assert s.price.source.startswith("https://") and s.key_env


def test_systems_change_at_most_the_product_switch():
    assert all(len(s.settings) <= 1 for s in SYSTEMS.values())
    assert SYSTEMS["reducto-extract"].settings == {}
    assert SYSTEMS["extend-performance"].settings == {}
    assert SYSTEMS["landingai-ade"].settings == {}


def test_cost():
    assert Price(per_1k_pages=20).cost(pages=50, credits=None) == 1.0
    assert Price(per_credit=0.0125).cost(pages=50, credits=250) == pytest.approx(3.125)
    assert Price(per_credit=0.01).cost(pages=50, credits=None) is None


def test_envelope_roundtrip_and_classification(tmp_path):
    out = tmp_path / "doc.json"
    envelope.write(out, system="x", result={"a": 1}, latency_s=1.23456, usage={"pages": 2})
    env = envelope.read(out)
    assert env["result"] == {"a": 1} and env["_meta"]["latency_s"] == 1.235
    assert envelope.classify(env) == ("success", None)
    envelope.write(out, system="x", result=None, latency_s=None, status="failed", error="boom")
    assert envelope.classify(envelope.read(out)) == ("failure", "boom")
    assert envelope.classify({"result": {}, "_meta": {}}) == ("failure", "empty result")
    assert envelope.classify(None) == ("failure", "no output file")


def test_deepread_review_flags_are_removed():
    body = json.loads("""{"status": "completed", "extraction": {"fields": [
        {"key": "vendor_name", "value": "ACME", "needs_review": false},
        {"key": "lines", "value": [{"amount": {"value": 1.5, "hil_flag": false}, "reason": "x"}]}]}}""")
    assert fields(body) == {"vendor_name": "ACME", "lines": [{"amount": 1.5, "reason": "x"}]}


def test_reducto_parts_are_merged():
    assert merge([{"total": {"value": "12.00", "citations": []}, "rows": [{"n": 1}]}]) == {"total": "12.00", "rows": [{"n": 1}]}
    parts = [{"title": "T", "rows": [{"n": 1}], "note": None}, {"title": "", "rows": [{"n": 2}], "note": "x"}]
    assert merge(parts) == {"title": "T", "rows": [{"n": 1}, {"n": 2}], "note": "x"}
    assert envelope.classify({"result": merge(parts), "_meta": {}})[0] == "success"


def test_extend_schema_translation_keeps_fields_and_descriptions():
    schema = {"type": "object", "properties": {
        "id": {"type": "string", "description": "the id"},
        "rows": {"type": "array", "items": {"$ref": "#/$defs/row"}},
    }, "$defs": {"row": {"type": "object", "properties": {"n": {"type": "number", "description": "n"}}}}}
    out = to_extend_schema(schema)
    assert out["properties"]["id_field"] == {"type": ["string", "null"], "description": "the id"}
    row = out["properties"]["rows"]["items"]
    assert row["additionalProperties"] is False and row["properties"]["n"] == {"type": ["number", "null"], "description": "n"}
    assert "$defs" not in out and schema["properties"]["id"]["type"] == "string"  # input untouched
    assert from_extend({"id_field": "7", "rows": [{"id_field": 1}]}) == {"id": "7", "rows": [{"id": 1}]}


def test_poll_raises_fatal_errors_at_once():
    def rejected():
        raise FatalError("HTTP 401")
    with pytest.raises(FatalError):
        poll(rejected, lambda b: True, interval=0, timeout=3600)


def test_guessing_does_not_raise_the_docile_score():
    d, schema = Docile(), {"properties": {"document_id": {}}}
    gt = {"document_id": ["INV-7"]}
    one_answer = d.aggregate([d.grade({"document_id": "INV-7"}, gt, schema)])
    four_guesses = d.aggregate([d.grade({"document_id": ["INV-1", "INV-7", "INV-8", "INV-9"]}, gt, schema)])
    assert four_guesses["score"] < one_answer["score"]


def test_unwrap_leaves_plain_structures_alone():
    assert unwrap_values({"value": 1, "other": 2}, ("citations",)) == {"value": 1, "other": 2}
