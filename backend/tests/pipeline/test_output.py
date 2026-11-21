"""T8: output files & CLI. Traces: R-OUT-1..5, design §5.6, §6."""
import json
from collections import Counter
from pathlib import Path

import pytest

from pipeline.__main__ import main
from pipeline.run import build
from pipeline.schema import FIELDS, PART1, PART2

DATA = Path(__file__).resolve().parents[3] / "data"
RECORD_KEYS = ["id", *[f.name for f in FIELDS], "sources", "field_flags", "flags",
               "possible_duplicates"]
ISSUE_KEYS = ["id", "field", "source", "raw_value", "final_value", "reason", "severity", "detail"]


def columns(rows):
    """rows: list of dicts (row-oriented) → column-oriented source layout."""
    out = {}
    for i, r in enumerate(rows):
        for k, v in r.items():
            out.setdefault(k, {})[str(i)] = v
    return out


def song(id_, title, **kw):
    base = dict(id=id_, title=title, danceability=0.5, energy=0.5, mood=1, acousticness=0.1,
                tempo=100.0, duration_ms=250_000, num_sections=8, num_segments=1000)
    base.update(kw)
    return base


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    p1 = [song("a", "Alpha", energy="N/A"), song("b", "Beta"), song("c", "Gamma")]
    p2 = [dict(song("a", "Alpha", energy=0.7), valence=0.4),
          dict(song("d", "Gamma", duration_ms=251_000), valence=0.5)]
    (d / PART1).write_text(json.dumps(columns(p1)))
    (d / PART2).write_text(json.dumps(columns(p2)))
    return d


def by_id(songs):
    return {s["id"]: s for s in songs}


# --- records ---------------------------------------------------------------

def test_record_keys_in_schema_order(data_dir):
    out = build(data_dir)
    assert all(list(s) == RECORD_KEYS for s in out.songs)


def test_records_sorted_by_id(data_dir):
    assert [s["id"] for s in build(data_dir).songs] == ["a", "b", "c", "d"]


def test_filled_one_sided_missing_value_not_flagged_on_record(data_dir):
    out = build(data_dir)
    a = by_id(out.songs)["a"]
    assert a["energy"] == 0.7
    assert "energy" not in a["field_flags"]
    [log] = [i for i in out.issues if i["id"] == "a" and i["field"] == "energy"]
    assert log["reason"] == "missing_na" and log["final_value"] == 0.7
    assert log["source"] == {"file": PART1, "row": "0"}


def test_flags_are_sorted_union_plus_duplicate(data_dir):
    out = build(data_dir)
    songs = by_id(out.songs)
    assert songs["b"]["field_flags"] == {"valence": ["not_in_source"]}
    assert songs["b"]["flags"] == ["not_in_source"]
    assert songs["c"]["flags"] == ["not_in_source", "possible_duplicate"]
    assert songs["c"]["possible_duplicates"] == ["d"]
    assert songs["d"]["flags"] == ["possible_duplicate"]


def test_sources_serialized(data_dir):
    a = by_id(build(data_dir).songs)["a"]
    assert a["sources"] == [{"file": PART1, "row": "0"}, {"file": PART2, "row": "0"}]


# --- issues ----------------------------------------------------------------

def test_issue_shape_and_absent_as_null(data_dir):
    out = build(data_dir)
    assert all(list(i) == ISSUE_KEYS for i in out.issues)
    [nis] = [i for i in out.issues if i["id"] == "b" and i["reason"] == "not_in_source"]
    assert nis["raw_value"] is None and nis["severity"] == "info"


def test_issues_sorted(data_dir):
    issues = build(data_dir).issues
    keys = [(i["id"], i["field"]) for i in issues]
    assert keys == sorted(keys)


# --- report ----------------------------------------------------------------

def test_report_counts_match_issues(data_dir):
    out = build(data_dir)
    r = out.report
    assert r["records"] == 4 and r["merged"] == 1
    assert r["by_reason"] == dict(sorted(Counter(i["reason"] for i in out.issues).items()))
    assert sum(r["by_severity"].values()) == len(out.issues)
    assert r["possible_duplicate_pairs"] == 1
    assert r["conflicts"] == 0 and r["corrections"] == 0
    assert r["nulls_by_field_and_reason"] == {"valence": {"not_in_source": 2}}
    assert [i["file"] for i in r["inputs"]] == [PART1, PART2]
    assert [i["rows"] for i in r["inputs"]] == [3, 2]
    assert set(r["band"]) == {"median", "low", "high", "n"}


def test_report_has_no_timestamp(data_dir):
    text = json.dumps(build(data_dir).report)
    assert "time" not in text and "date" not in text


# --- CLI -------------------------------------------------------------------

def test_cli_writes_three_files(data_dir, tmp_path, capsys):
    out_dir = tmp_path / "out" / "normalized"
    assert main(["--data-dir", str(data_dir), "--out-dir", str(out_dir)]) == 0
    for name in ("songs.json", "issues.json", "report.json"):
        text = (out_dir / name).read_text(encoding="utf-8")
        assert text.endswith("\n")
        json.loads(text)
    assert "4 records" in capsys.readouterr().out


def test_cli_keeps_non_ascii_text(tmp_path):
    out_dir = tmp_path / "out"
    assert main(["--data-dir", str(DATA), "--out-dir", str(out_dir)]) == 0
    assert "Naïve" in (out_dir / "songs.json").read_text(encoding="utf-8")


def test_cli_exits_1_on_broken_input_and_writes_nothing(data_dir, tmp_path, capsys):
    (data_dir / PART1).write_text(json.dumps({"id": {"0": "a"}, "loudness": {"0": 1}}))
    out_dir = tmp_path / "out"
    assert main(["--data-dir", str(data_dir), "--out-dir", str(out_dir)]) == 1
    assert "loudness" in capsys.readouterr().err
    assert not out_dir.exists()


def test_cli_exits_1_on_missing_file(tmp_path, capsys):
    out_dir = tmp_path / "out"
    assert main(["--data-dir", str(tmp_path / "nope"), "--out-dir", str(out_dir)]) == 1
    assert PART1 in capsys.readouterr().err
    assert not out_dir.exists()
