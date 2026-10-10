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
    assert g["score"] == 1.0
    assert (g["row_precision"], g["row_recall"], g["leaf_accuracy"]) == (1.0, 1.0, 1.0)


def test_missing_row_and_wrong_value():
    g = LongExtract().grade({"title": "Filings", "rows": [{"year": 2021, "count": 999}]}, GT, SCHEMA)
    assert (g["correct"], g["returned"], g["expected"]) == (2, 3, 5)
    assert g["score"] == pytest.approx(2 * 2 / (3 + 5))
    assert (g["row_precision"], g["row_recall"]) == (1.0, 0.5)
    assert g["leaf_accuracy"] == pytest.approx(2 / 3)  # micro1: the missed row is not in its pool


def test_invented_rows_lower_the_score():
    honest = LongExtract().grade({"title": "Filings", "rows": [{"year": 2021, "count": 1000}]}, GT, SCHEMA)
    padded = LongExtract().grade({"title": "Filings", "rows": [
        {"year": 2021, "count": 1000}, {"year": 2019, "count": 5}, {"year": 2020, "count": 7}]}, GT, SCHEMA)
    assert padded["score"] < honest["score"]


def test_empty_prediction_scores_zero():
    g = LongExtract().grade({}, GT, SCHEMA)
    assert g["score"] == 0.0 and g["expected"] == 5


def test_failed_documents_count_as_zero_in_the_headline():
    d = LongExtract()
    done = {**d.grade(GT, GT, SCHEMA), "state": "success"}
    failed = {**d.grade({}, GT, SCHEMA), "state": "failure"}
    agg = d.aggregate([done, failed])
    assert agg["score"] == 0.5
    assert agg["leaf_accuracy"] == 1.0  # micro1's numbers: completed documents only
