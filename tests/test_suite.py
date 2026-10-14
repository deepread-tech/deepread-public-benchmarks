"""`drbench short-run` / `drbench full-run`: the plan, the price, the key check,
and that a run is resumable — all with a fake provider, no API calls."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from drbench import cli, envelope, suite
from drbench.datasets.base import Column, Doc
from drbench.suite import (
    DEFAULT_SYSTEMS, PLANS, SYSTEMS, cost_table, describe, estimate, missing_keys, pages, systems_for,
)

ROOT = Path(__file__).resolve().parents[1]
ALL_KEYS = ("DEEPREAD_API_KEY", "REDUCTO_API_KEY", "EXTEND_API_KEY", "VISION_AGENT_API_KEY")


def _ids(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")]


def test_the_plans_are_the_documents_we_ran():
    short, full = PLANS["short"], PLANS["full"]
    assert [p.dataset for p in short] == [p.dataset for p in full] == ["docile", "charity", "longextract"]
    # the short run's lists are the committed sample files, and they hold exactly that many documents
    assert len(_ids(ROOT / "datasets/docile/val_docids.txt")) == short[0].documents == 500
    assert len(_ids(ROOT / short[1].ids)) == short[1].documents == 40
    assert len(_ids(ROOT / short[2].ids)) == short[2].documents == 20
    assert pages("short") == 2_614
    assert [p.documents for p in full] == [500, 440, 50] and pages("full") == 30_803
    assert all(p.ids is None for p in full)


def test_cost_is_pages_times_list_price():
    deepread = next(s for s in SYSTEMS if s.id == "deepread:extract-selfhost")
    assert dict(estimate("short", [deepread]))[deepread] == pytest.approx(0.015 * 2_614)
    total_short = sum(cost for _, cost in estimate("short", list(DEFAULT_SYSTEMS)))
    total_full = sum(cost for _, cost in estimate("full", list(DEFAULT_SYSTEMS)))
    assert total_short == pytest.approx(747.6, abs=0.1)  # "about $750"
    assert total_full == pytest.approx(8_809.7, abs=0.1)  # "about $8,800"
    vendors = [s for s in DEFAULT_SYSTEMS if not s.id.startswith("deepread")]
    assert sum(cost for _, cost in estimate("full", vendors)) == pytest.approx(8_347.6, abs=0.1)
    table = cost_table("short", list(DEFAULT_SYSTEMS))
    assert "| DeepRead extract | $15 | $39 |" in table and "**$748**" in table
    assert "DeepRead deep-extract" not in table


def test_the_published_six_run_by_default_and_deep_extract_is_opt_in():
    assert [s.id for s in systems_for(None)] == [
        "deepread:extract-selfhost", "reducto:extract", "reducto:deep-extract",
        "extend:performance", "extend:operator", "landingai:dpt-3-pro"]
    assert [s.id for s in systems_for("deepread:deep-extract")] == ["deepread:deep-extract"]
    assert [s.id for s in systems_for("deepread")] == ["deepread:extract-selfhost", "deepread:deep-extract"]


def test_systems_subset_by_id_or_provider():
    assert [s.id for s in systems_for("reducto")] == ["reducto:extract", "reducto:deep-extract"]
    assert [s.id for s in systems_for("extend:operator, deepread:extract-selfhost")] == [
        "extend:operator", "deepread:extract-selfhost"]
    with pytest.raises(SystemExit):
        systems_for("nanonets")


def test_missing_keys_are_named(monkeypatch):
    for key in ALL_KEYS:
        monkeypatch.delenv(key, raising=False)
    assert missing_keys(list(DEFAULT_SYSTEMS)) == sorted(ALL_KEYS)
    monkeypatch.setenv("REDUCTO_API_KEY", "x")
    assert missing_keys(systems_for("reducto")) == []
    assert "DEEPREAD_API_KEY" in missing_keys(systems_for("deepread,reducto"))


def test_dry_run_prints_the_plan_and_sends_nothing(monkeypatch, capsys):
    for key in ALL_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(suite, "make", lambda system: pytest.fail("a provider was built in a dry run"))
    assert cli.main(["short-run", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "2,614 pages each" in out and "datasets/longextract/sample-20.txt" in out
    assert "| LandingAI ADE | $61 | $159 |" in out and "dry run: nothing was sent." in out


def test_a_missing_key_stops_before_anything_is_sent(monkeypatch, capsys):
    for key in ALL_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("REDUCTO_API_KEY", "x")
    with pytest.raises(SystemExit) as e:
        cli.main(["full-run", "--systems", "reducto,extend", "--yes"])
    assert "EXTEND_API_KEY" in str(e.value) and "REDUCTO_API_KEY" not in str(e.value)


def test_declining_the_confirmation_sends_nothing(monkeypatch):
    for key in ALL_KEYS:
        monkeypatch.setenv(key, "x")
    monkeypatch.setattr(suite, "make", lambda system: pytest.fail("a provider was built after 'no'"))
    assert suite.sweep("short", list(DEFAULT_SYSTEMS), Path("data"), Path("runs"), ask=lambda prompt: "n") == 1


class FakeDataset:
    """Two documents, scored by whether the result equals the ground truth."""

    name = "fake"
    title = "Fake (2 documents)"
    columns = (Column("accuracy", "Accuracy"), Column("completed", "Documents completed", "int"))

    def fetch(self, data_dir: Path, **opts):
        raise AssertionError("already fetched")

    def docs(self, data_dir: Path, labels: str = "official"):
        return [Doc(id=i, pdf=Path(f"{i}.pdf"), schema={}, ground_truth={"v": i}) for i in ("a", "b")]

    def grade(self, pred, ground_truth, schema):
        return {"accuracy": 1.0 if pred == ground_truth else 0.0}

    def aggregate(self, per_doc):
        return {"documents": len(per_doc), "accuracy": sum(d["accuracy"] for d in per_doc) / len(per_doc)}


class FakeProvider:
    name = "fake-x"
    env_key = "FAKE_KEY"
    calls: list[str] = []

    def extract(self, pdf: Path, schema: dict, sidecar: Path):
        FakeProvider.calls.append(pdf.stem)
        return {"v": pdf.stem}, {}


def test_a_run_is_resumable_and_ends_with_the_table(monkeypatch, tmp_path, capsys):
    fake = suite.System("fake:x", "Fake X", "FAKE_KEY", 0.001)
    part = suite.Part("fake", None, 2, 10)
    monkeypatch.setitem(suite.PLANS, "short", (part,))
    monkeypatch.setitem(suite.DATASETS, "fake", FakeDataset())
    monkeypatch.setattr(suite, "make", lambda system: FakeProvider())
    monkeypatch.setenv("FAKE_KEY", "x")
    monkeypatch.setattr("drbench.runner.time.sleep", lambda s: None)
    runs = tmp_path / "runs"
    # one document already has an output: it must not be sent again
    envelope.write(runs / "fake" / "fake-x" / "a.json", system="fake-x", result={"v": "a"}, latency_s=1)
    FakeProvider.calls.clear()
    assert suite.sweep("short", [fake], tmp_path / "data", runs, yes=True) == 0
    assert FakeProvider.calls == ["b"]
    out = capsys.readouterr().out
    assert "1 to run, 1 already done" in out
    assert "| Fake X | 100.0% |" in out
    scores = json.loads((runs / "fake" / "scores.json").read_text())
    assert scores["systems"]["fake-x"]["summary"]["completed"] == 2
    # the same command again sends nothing
    FakeProvider.calls.clear()
    assert suite.sweep("short", [fake], tmp_path / "data", runs, yes=True) == 0
    assert FakeProvider.calls == []


def test_describe_names_every_part_and_the_total():
    text = describe("full", systems_for("landingai"))
    assert "all 440 documents (10,639 pages)" in text and "all 50 documents (19,528 pages)" in text
    assert "| LandingAI ADE | $61 | $1,879 |" in text
