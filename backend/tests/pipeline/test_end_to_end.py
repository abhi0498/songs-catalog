"""T9: end-to-end acceptance on the real files (requirements §5) and determinism (P5).

Traces: R-VER-1..3, P5, R-OUT-5.
"""
import hashlib
import json
from pathlib import Path

import pytest

from pipeline.__main__ import main
from pipeline.output import dumps
from pipeline.run import build
from pipeline.schema import PART1, PART2

DATA = Path(__file__).resolve().parents[3] / "data"
FILES = ("songs.json", "issues.json", "report.json")

IDS = {
    "3AM": "5vYA1mW9g2Coh1HUFUSmlb",
    "4 walls": "2klCjJcucgGQysgH170npL",
    "11:11": "093PI3mdUvOSlvMYDwnV1e",
    "21 Guns": "64yrDBpcdwEdNY9loyEGbX",
    "Bohemian Rhapsody": "1hKdDCpiI9mqz1jVHRKG0E",
    "Blinding Lights": "0VjIjW4GlUZAMYd2vXMi3b",
    "Yesterday": "3AJwUDP919kvQ9QcozQPxg",
    "Never Gonna Give You Up": "4uLU6hMCjMI75M1A2tKUQC",
    "Another Brick": "3JvKfv6T31zO0ini8iNItO",
    "Sunflower": "3KkXRkHbMCARz0aVfEt68P",
    "Uptown Funk": "4VqPOruhp5EdPBeR92t6lQ",
    "Sweet Child O Mine": "2QjOHCTQ1Jl3zawyYOpxh6",
    "Perfect A": "0tgVpDi06FyKpA1z0VMD4v",
    "Perfect B": "7dNsHhGeGU5MV01r06O8gK",
}
MERGED = {"2takcwOaAZWiXQijPHIx7B", "4uLU6hMCjMI75M1A2tKUQC",
          "6DCZcSspjsKoFjzjrWoCEA", "7qiZfU4dY1lWllzX7mPBI3"}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    before = {f: sha(DATA / f) for f in (PART1, PART2)}
    out = tmp_path_factory.mktemp("normalized")
    assert main(["--data-dir", str(DATA), "--out-dir", str(out)]) == 0
    after = {f: sha(DATA / f) for f in (PART1, PART2)}
    assert before == after, "raw files must not change (R-OUT-5)"
    return out


@pytest.fixture(scope="module")
def songs(run_dir):
    return {s["id"]: s for s in json.loads((run_dir / "songs.json").read_text("utf-8"))}


@pytest.fixture(scope="module")
def issues(run_dir):
    return json.loads((run_dir / "issues.json").read_text("utf-8"))


@pytest.fixture(scope="module")
def report(run_dir):
    return json.loads((run_dir / "report.json").read_text("utf-8"))


def song(songs, name):
    return songs[IDS[name]]


# --- counts ---------------------------------------------------------------

def test_record_counts(songs, report):
    assert len(songs) == 25 and report["records"] == 25
    assert {i for i, s in songs.items() if len(s["sources"]) > 1} == MERGED
    assert report["merged"] == 4
    assert [i["rows"] for i in report["inputs"]] == [16, 13]


# --- nulls (requirements §5) ----------------------------------------------

@pytest.mark.parametrize(
    "name, field, reason",
    [
        ("21 Guns", "danceability", "out_of_range"),
        ("Never Gonna Give You Up", "danceability", "source_conflict"),
        ("11:11", "energy", "missing_absent"),
        ("Yesterday", "energy", "missing_na"),
        ("Bohemian Rhapsody", "acousticness", "missing_null"),
        ("Another Brick", "acousticness", "out_of_range"),
        ("Blinding Lights", "tempo", "out_of_range"),
    ],
)
def test_named_nulls(songs, name, field, reason):
    s = song(songs, name)
    assert s[field] is None
    assert s["field_flags"][field] == [reason]


def test_exactly_the_expected_nulls(songs):
    nulls = sorted((i, f) for i, s in songs.items() for f, v in s.items()
                   if v is None and f != "valence")
    assert len(nulls) == 7


def test_valence(songs):
    missing = {i for i, s in songs.items() if s["valence"] is None}
    assert len(missing) == 12
    assert all(songs[i]["field_flags"]["valence"] == ["not_in_source"] for i in missing)
    assert all(len(songs[i]["sources"]) == 1 and songs[i]["sources"][0]["file"] == PART1
               for i in missing)


def test_conflict_keeps_both_values_in_log(issues):
    [c] = [i for i in issues if i["reason"] == "source_conflict"]
    assert c["id"] == IDS["Never Gonna Give You Up"] and c["field"] == "danceability"
    assert c["raw_value"] == [0.727, 0.74]


# --- corrections ------------------------------------------------------------

@pytest.mark.parametrize("name, ms", [("Sunflower", 158_000), ("Uptown Funk", 270_000),
                                       ("Sweet Child O Mine", 356_000)])
def test_duration_corrections(songs, name, ms):
    s = song(songs, name)
    assert s["duration_ms"] == ms
    assert s["field_flags"]["duration_ms"] == ["unit_corrected_s_to_ms"]


def test_no_other_duration_changes(issues, report):
    dur = [i for i in issues if i["field"] == "duration_ms"]
    assert {i["reason"] for i in dur} == {"unit_corrected_s_to_ms"} and len(dur) == 3
    assert report["corrections"] == 3
    assert "implausible_duration" not in report["by_reason"]


def test_coercions_and_title(songs):
    s = song(songs, "3AM")
    assert s["danceability"] == 0.521 and s["tempo"] == 108.73
    assert s["field_flags"]["danceability"] == ["coerced_from_string"]
    assert s["field_flags"]["tempo"] == ["coerced_from_string"]
    assert song(songs, "4 walls")["title"] == "4 walls"


# --- duplicates ---------------------------------------------------------------

def test_perfect_pair(songs, report):
    a, b = song(songs, "Perfect A"), song(songs, "Perfect B")
    assert a["possible_duplicates"] == [b["id"]] and b["possible_duplicates"] == [a["id"]]
    assert "possible_duplicate" in a["flags"] and "possible_duplicate" in b["flags"]
    assert report["possible_duplicate_pairs"] == 1
    assert sum(bool(s["possible_duplicates"]) for s in songs.values()) == 2


def test_no_errors(report):
    assert "error" not in report["by_severity"]


# --- determinism (P5, R-VER-3) ----------------------------------------------

def test_two_runs_are_byte_identical(run_dir, tmp_path):
    assert main(["--data-dir", str(DATA), "--out-dir", str(tmp_path)]) == 0
    for f in FILES:
        assert (tmp_path / f).read_bytes() == (run_dir / f).read_bytes(), f


def test_input_file_order_does_not_matter():
    a, b = build(DATA, files=(PART1, PART2)), build(DATA, files=(PART2, PART1))
    assert dumps(a.songs) == dumps(b.songs)
    assert dumps(a.issues) == dumps(b.issues)
    assert dumps(a.report) == dumps(b.report)
