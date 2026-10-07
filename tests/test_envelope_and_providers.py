import json

from drbench import envelope
from drbench.providers import make
from drbench.providers._http import unwrap_values
from drbench.providers.deepread import fields
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
    assert make("reducto").name == "reducto-deep-extract"
    assert make("reducto:extract").name == "reducto-extract"
    assert make("landingai").name == "landingai-dpt-3-pro"


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
