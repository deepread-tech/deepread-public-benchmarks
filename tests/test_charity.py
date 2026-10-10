"""The Kleister-Charity scorer must reproduce GEval 1.14.2.0.

`tests/fixtures/kleister_geval_run478/out.tsv` is a real DeepRead run that
was scored with the official GEval binary (see `geval_*_labels.txt` next to it).
The same predictions scored here must give the same numbers.
"""

import os
from pathlib import Path

import pytest

from drbench.datasets.charity import Charity, grade_labels, iso_date, money, to_labels

ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS = ROOT / "tests" / "fixtures" / "kleister_geval_run478" / "out.tsv"
CORRECTED = ROOT / "datasets" / "charity" / "errata" / "dev-0.expected.corrected.tsv"
OFFICIAL_CANDIDATES = (
    Path(os.environ.get("KLEISTER_EXPECTED", "")),
    ROOT / "data" / "charity" / "kleister-charity" / "dev-0" / "expected.tsv",
    Path("data") / "charity" / "kleister-charity" / "dev-0" / "expected.tsv",
)


def _score(expected: Path) -> dict:
    pred_lines = PREDICTIONS.read_text().splitlines()
    exp_lines = expected.read_text().splitlines()
    assert len(pred_lines) == len(exp_lines) == 440
    return Charity().aggregate([grade_labels(p.split(), e.split()) for p, e in zip(pred_lines, exp_lines)])


# GEval was run with `-B 200`, so its figures are means over 200 bootstrap
# samples (its own ± is the spread), not the whole-set value. The pooled F1,
# precision and recall land within ~0.1 of the exact numbers; the per-field
# F1s (a few hundred labels each) and the whole-document accuracy are noisier.
F1_TOL, FIELD_TOL, ACC_TOL = 0.15, 0.7, 0.5


def _close(value: float, geval: float, tol: float = F1_TOL) -> bool:
    return abs(100 * value - geval) <= tol


def test_reproduces_geval_on_corrected_labels():
    s = _score(CORRECTED)  # geval_corrected_labels.txt
    assert _close(s["f1_uc"], 84.4)
    assert _close(s["precision_uc"], 83.8)
    assert _close(s["recall_uc"], 84.9)
    assert _close(s["f1"], 76.5)
    assert _close(s["mean_f1_uc"], 84.2)
    assert _close(s["accuracy_uc"], 22.7, ACC_TOL)
    assert s["score"] == s["f1_uc"]  # the headline is the benchmark's own F1 (UC)
    geval_fields = {
        "address__post_town": 92.9, "address__postcode": 91.8, "address__street_line": 41.3,
        "charity_name": 66.3, "charity_number": 98.85, "report_date": 98.0,
        "income_annually_in_british_pounds": 91.3, "spending_annually_in_british_pounds": 91.0,
    }
    for field, geval in geval_fields.items():
        assert _close(s["fields"][field]["f1"], geval, FIELD_TOL), field


def test_reproduces_geval_on_official_labels():
    expected = next((p for p in OFFICIAL_CANDIDATES if p.is_file()), None)
    if expected is None:
        pytest.skip("official dev-0/expected.tsv not downloaded (drbench fetch charity)")
    s = _score(expected)  # geval_official_labels.txt
    assert _close(s["f1_uc"], 80.9)
    assert _close(s["precision_uc"], 80.5)
    assert _close(s["recall_uc"], 81.3)
    assert _close(s["f1"], 73.0)
    assert _close(s["mean_f1_uc"], 80.7)
    assert _close(s["accuracy_uc"], 16.0, ACC_TOL)


def test_labels_follow_kleister_normalisation():
    result = {
        "charity_name": "Havens  Christian Hospice",
        "charity_number": 1022119,
        "address__street_line": "47 Second Avenue",
        "report_date": "31 March 2016",
        "income_annually_in_british_pounds": "£10,348,000",
        "spending_annually_in_british_pounds": 9415000,
        "unrelated_field": "ignored",
    }
    assert to_labels(result) == [
        "address__street_line=47_Second_Avenue",
        "charity_name=Havens_Christian_Hospice",
        "charity_number=1022119",
        "income_annually_in_british_pounds=10348000.00",
        "report_date=2016-03-31",
        "spending_annually_in_british_pounds=9415000.00",
    ]


@pytest.mark.parametrize(
    "raw, iso",
    [("2018-07-31", "2018-07-31"), ("31/07/2018", "2018-07-31"), ("31.7.2018", "2018-07-31"),
     ("31st March 2016", "2016-03-31"), ("March 31, 2016", "2016-03-31"), ("not a date", None), ("31/13/2018", None)],
)
def test_dates(raw, iso):
    assert iso_date(raw) == iso


@pytest.mark.parametrize("raw, out", [("£1,234", "1234.00"), ("(500)", "-500.00"), (12.5, "12.50"), ("n/a", None)])
def test_money(raw, out):
    assert money(raw) == out


def test_empty_prediction_is_all_misses():
    g = grade_labels([], ["charity_number=1", "report_date=2016-03-31"])
    assert (g["tp_uc"], g["fp_uc"], g["fn_uc"]) == (0, 0, 2)
    assert g["doc_f1_uc"] == 0.0 and g["exact"] is False
