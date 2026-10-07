import pytest

from drbench.datasets.longextract import LongExtract

SCHEMA = {"type": "object", "properties": {
    "title": {"type": "string"},
    "rows": {"type": "array", "items": {"type": "object", "properties": {
        "year": {"type": "integer"}, "count": {"type": "number"}}}},
}}
GT = {"title": "Filings", "rows": [{"year": 2021, "count": 1000}, {"year": 2022, "count": 1200}]}


def test_perfect_prediction():
    g = LongExtract().grade({"title": "filings", "rows": [{"year": "2022", "count": "1,200"}, {"year": 2021, "count": 1000.0}]}, GT, SCHEMA)
    assert (g["row_precision"], g["row_recall"], g["leaf_accuracy"]) == (1.0, 1.0, 1.0)


def test_missing_row_hits_recall_and_wrong_cell_hits_leaves():
    g = LongExtract().grade({"title": "Filings", "rows": [{"year": 2021, "count": 999}]}, GT, SCHEMA)
    assert (g["row_precision"], g["row_recall"]) == (1.0, 0.5)
    assert g["leaf_accuracy"] == pytest.approx(2 / 3)  # title + year right, count wrong; the missed row is not in the pool


def test_aggregate_only_over_completed_documents():
    d = LongExtract()
    done = {**d.grade(GT, GT, SCHEMA), "state": "success"}
    failed = {**d.grade({}, GT, SCHEMA), "state": "failure"}
    agg = d.aggregate([done, failed])
    assert agg["leaf_accuracy"] == 1.0 and agg["documents"] == 2
