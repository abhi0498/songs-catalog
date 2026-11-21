"""T6: merge by id. Traces: R-ID-2..6, R-MISS-2..3, D1, P5."""
from pathlib import Path

import pytest

from pipeline.clean import clean_field
from pipeline.duration import apply_durations, compute_band
from pipeline.load import load_file
from pipeline.merge import merge_by_id
from pipeline.schema import (
    ABSENT, FIELDS, FIELDS_BY_NAME, PART1, PART2, Reason, Source, SourceRow,
)

DATA = Path(__file__).resolve().parents[3] / "data"
R = Reason


def row(id_, file, idx, **raw):
    """A SourceRow with every field the file has; unspecified fields are ABSENT."""
    src = Source(file, idx)
    specs = [s for s in FIELDS if file in s.sources]
    full = {s.name: raw.get(s.name, ABSENT) for s in specs}
    clean = {s.name: clean_field(s, full[s.name], id=id_, source=src) for s in specs}
    return SourceRow(id=id_, source=src, raw=full, clean=clean)


def only(records, id_):
    [rec] = [r for r in records if r.id == id_]
    return rec


def field_issues(issues, id_, field):
    return [i for i in issues if i.id == id_ and i.field == field]


# --- §5.4 table -----------------------------------------------------------

def test_equal_values_are_kept():
    res = merge_by_id([row("a", PART1, "0", energy=0.5), row("a", PART2, "3", energy=0.5)])
    rec = only(res.records, "a")
    assert rec.values["energy"] == 0.5
    assert "energy" not in rec.field_flags
    assert rec.sources == [Source(PART1, "0"), Source(PART2, "3")]


def test_numeric_string_equals_native_number():
    res = merge_by_id([row("a", PART1, "0", energy="0.521"), row("a", PART2, "0", energy=0.521)])
    rec = only(res.records, "a")
    assert rec.values["energy"] == 0.521
    assert rec.field_flags["energy"] == [R.COERCED_FROM_STRING]


def test_one_sided_value_is_used_and_missing_side_stays_in_log_only():
    res = merge_by_id([row("a", PART1, "0", energy="N/A"), row("a", PART2, "0", energy=0.7)])
    rec = only(res.records, "a")
    assert rec.values["energy"] == 0.7
    assert "energy" not in rec.field_flags
    [issue] = field_issues(res.issues, "a", "energy")
    assert issue.reason is R.MISSING_NA and issue.source == Source(PART1, "0")
    assert issue.final_value == 0.7  # log shows what the record ended up with


def test_both_null_keeps_both_reasons():
    res = merge_by_id([row("a", PART1, "0", energy=None), row("a", PART2, "0", energy="N/A")])
    rec = only(res.records, "a")
    assert rec.values["energy"] is None
    assert rec.field_flags["energy"] == [R.MISSING_NA, R.MISSING_NULL]
    assert len(field_issues(res.issues, "a", "energy")) == 2


def test_conflict_is_nulled_and_no_file_wins():
    res = merge_by_id([row("a", PART1, "13", danceability=0.727),
                       row("a", PART2, "1", danceability=0.74)])
    rec = only(res.records, "a")
    assert rec.values["danceability"] is None
    assert rec.field_flags["danceability"] == [R.SOURCE_CONFLICT]
    [issue] = field_issues(res.issues, "a", "danceability")
    assert issue.reason is R.SOURCE_CONFLICT
    assert issue.source is None and issue.final_value is None
    assert issue.raw_value == [0.727, 0.74]
    assert issue.detail == {"values": [
        {"file": PART1, "row": "13", "value": 0.727},
        {"file": PART2, "row": "1", "value": 0.74},
    ]}


def test_title_conflict_is_nulled():
    res = merge_by_id([row("a", PART1, "0", title="One"), row("a", PART2, "0", title="Two")])
    assert only(res.records, "a").values["title"] is None


def test_titles_equal_after_whitespace_cleanup_do_not_conflict():
    res = merge_by_id([row("a", PART1, "0", title=" 4 walls "), row("a", PART2, "0", title="4 walls")])
    rec = only(res.records, "a")
    assert rec.values["title"] == "4 walls"
    assert rec.field_flags["title"] == [R.WHITESPACE_NORMALIZED]


def test_different_ids_never_merge():
    res = merge_by_id([row("a", PART2, "4", title="Perfect"), row("b", PART2, "12", title="Perfect")])
    assert [r.id for r in res.records] == ["a", "b"]


# --- not_in_source (R-MISS-2/3) -------------------------------------------

def test_part1_only_record_gets_not_in_source_valence():
    res = merge_by_id([row("a", PART1, "5", energy=0.5)])
    rec = only(res.records, "a")
    assert rec.values["valence"] is None
    assert rec.field_flags["valence"] == [R.NOT_IN_SOURCE]
    [issue] = field_issues(res.issues, "a", "valence")
    assert issue.source == Source(PART1, "5") and issue.raw_value is ABSENT


def test_merged_record_takes_valence_from_part2_without_not_in_source():
    res = merge_by_id([row("a", PART1, "0"), row("a", PART2, "0", valence=0.31)])
    rec = only(res.records, "a")
    assert rec.values["valence"] == 0.31
    assert "valence" not in rec.field_flags
    assert field_issues(res.issues, "a", "valence") == []


# --- determinism -----------------------------------------------------------

def test_input_order_does_not_change_result():
    rows = [row("b", PART1, "1", energy=0.1), row("a", PART2, "0", energy=0.9),
            row("a", PART1, "10", energy=0.8), row("a", PART1, "2", energy=0.8)]
    forward, backward = merge_by_id(rows), merge_by_id(list(reversed(rows)))
    assert forward.records == backward.records
    assert forward.issues == backward.issues
    assert [r.id for r in forward.records] == ["a", "b"]
    assert only(forward.records, "a").sources == [
        Source(PART1, "2"), Source(PART1, "10"), Source(PART2, "0")]


def test_record_values_follow_schema_order():
    rec = merge_by_id([row("a", PART2, "0")]).records[0]
    assert list(rec.values) == [f.name for f in FIELDS]


# --- real data -------------------------------------------------------------

@pytest.fixture(scope="module")
def real():
    rows = load_file(DATA / PART1).rows + load_file(DATA / PART2).rows
    apply_durations(rows, compute_band(rows))
    return merge_by_id(rows)


def test_real_counts(real):
    assert len(real.records) == 25
    assert sum(len(r.sources) > 1 for r in real.records) == 4


def test_real_conflict_never_gonna_give_you_up(real):
    rec = only(real.records, "4uLU6hMCjMI75M1A2tKUQC")
    assert rec.values["danceability"] is None
    assert rec.field_flags == {"danceability": [R.SOURCE_CONFLICT]}
    [issue] = field_issues(real.issues, rec.id, "danceability")
    assert issue.raw_value == [0.727, 0.74]


def test_real_only_one_conflict(real):
    assert [i.id for i in real.issues if i.reason is R.SOURCE_CONFLICT] == ["4uLU6hMCjMI75M1A2tKUQC"]


def test_real_valence(real):
    nulls = [r.id for r in real.records if r.values["valence"] is None]
    assert len(nulls) == 12
    for r in real.records:
        if r.values["valence"] is None:
            assert r.field_flags["valence"] == [R.NOT_IN_SOURCE]
    for id_ in ("2takcwOaAZWiXQijPHIx7B", "4uLU6hMCjMI75M1A2tKUQC",
                "6DCZcSspjsKoFjzjrWoCEA", "7qiZfU4dY1lWllzX7mPBI3"):
        assert only(real.records, id_).values["valence"] is not None
