import pytest

from drbench.datasets.docile import Docile, _ground_truth, iso_date, normalise, parse_number, values

SCHEMA = {"type": "object", "properties": {f: {"type": "string"} for f in (
    "document_id", "date_issue", "amount_total_gross", "currency_code_amount_due", "tax_detail_rate", "vendor_name")}}


@pytest.mark.parametrize(
    "raw, number",
    [("$503.70", 503.7), ("1,234.56", 1234.56), ("1.234,56", 1234.56), ("1 234,56", 1234.56), ("(12.00)", -12.0),
     ("12,50", 12.5), ("USD 1,000", 1000.0), ("abc", None), ("12%", 12.0)],
)
def test_parse_number(raw, number):
    assert parse_number(raw) == number


@pytest.mark.parametrize(
    "raw, iso",
    [("3/4/2020", "2020-03-04"), ("03/04/20", "2020-03-04"), ("2020-3-4", "2020-03-04"), ("13/4/2020", "2020-04-13"),
     ("Mar 4, 2020", "2020-03-04"), ("4 March 2020", "2020-03-04"), ("4-Mar-2020", "2020-03-04"), ("Q1 2020", None)],
)
def test_iso_date(raw, iso):
    assert iso_date(raw) == iso


def test_normalise_by_field():
    assert normalise("amount_total_gross", "$ 503.70") == "503.70"
    assert normalise("tax_detail_rate", "7.5 %") == "7.50"
    assert normalise("date_issue", "03/04/2020") == "2020-03-04"
    assert normalise("date_issue", "spring") == "spring"
    assert normalise("currency_code_amount_due", "$") == "USD"
    assert normalise("currency_code_amount_due", "usd") == "USD"
    assert normalise("vendor_name", "  ACME   Corp ") == "acme corp"
    assert normalise("vendor_name", None) is None


def test_values_split_multi_instance_fields():
    assert values("tax_detail_rate", "7.5 | 0") == ["7.50", "0.00"]
    assert values("tax_detail_rate", ["7.5%", 7.5, None]) == ["7.50"]
    assert values("vendor_name", {"value": "ACME"}) == ["acme"]


def test_ground_truth_from_annotation():
    ann = {"field_extractions": [
        {"fieldtype": "amount_total_gross", "text": "$503.70"},
        {"fieldtype": "currency_code_amount_due", "text": "$"},
        {"fieldtype": "currency_code_amount_due", "text": "¤"},
        {"fieldtype": "tax_detail_rate", "text": "7.5"},
        {"fieldtype": "tax_detail_rate", "text": "0"},
        {"fieldtype": "tax_detail_rate", "text": "7.5"},
    ]}
    assert _ground_truth(ann) == {
        "amount_total_gross": ["$503.70"], "currency_code_amount_due": ["USD"], "tax_detail_rate": ["7.5", "0"]}


def test_grade_and_aggregate():
    d = Docile()
    gt = {"document_id": ["INV-1"], "date_issue": ["3/4/2020"], "amount_total_gross": ["$503.70"],
          "tax_detail_rate": ["7.5", "0"]}
    pred = {"document_id": "inv-1", "date_issue": "2020-03-04", "amount_total_gross": 503.7,
            "tax_detail_rate": "7.5%", "vendor_name": "Extra Co"}
    g = d.grade(pred, gt, SCHEMA)
    assert (g["tp"], g["fp"], g["fn"]) == (4, 1, 1)
    agg = d.aggregate([g, d.grade({}, gt, SCHEMA)])
    assert (agg["precision"], round(agg["recall"], 3)) == (0.8, 0.4)
    assert agg["fields"]["tax_detail_rate"]["recall"] == 0.25
