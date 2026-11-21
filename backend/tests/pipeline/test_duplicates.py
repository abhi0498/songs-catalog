"""T7: possible duplicates. Traces: R-DUP-1..2, D2, R-ID-6."""
from pathlib import Path

import pytest

from pipeline.duplicates import find_possible_duplicates
from pipeline.duration import apply_durations, compute_band
from pipeline.load import load_file
from pipeline.merge import Record, merge_by_id
from pipeline.schema import FIELDS, PART1, PART2, Reason, Source

DATA = Path(__file__).resolve().parents[3] / "data"


def rec(id_, title, tempo=95.05, duration=263_400, **extra):
    values = {f.name: None for f in FIELDS}
    values.update(title=title, tempo=tempo, duration_ms=duration, **extra)
    return Record(id=id_, sources=[Source(PART2, "0")], values=values, field_flags={})


def by_id(records):
    return {r.id: r for r in records}


def test_close_features_and_same_title_are_linked_both_ways():
    a, b = rec("a", "Perfect"), rec("b", "Perfect", tempo=95.05, duration=264_000)
    issues = find_possible_duplicates([a, b])
    assert a.possible_duplicates == ["b"] and b.possible_duplicates == ["a"]
    assert [(i.id, i.reason) for i in issues] == [
        ("a", Reason.POSSIBLE_DUPLICATE), ("b", Reason.POSSIBLE_DUPLICATE)]
    assert issues[0].detail["other_id"] == "b"
    assert issues[1].detail["other_id"] == "a"


def test_detail_has_diffs():
    a = rec("a", "Perfect", danceability=0.599)
    b = rec("b", "Perfect", duration=264_000, danceability=0.601)
    issue = find_possible_duplicates([a, b])[0]
    assert issue.detail["tempo_diff_pct"] == 0.0
    assert issue.detail["duration_diff_pct"] == 0.227
    assert issue.detail["field_diffs"] == {
        "danceability": [0.599, 0.601], "duration_ms": [263_400, 264_000]}


def test_tempo_two_percent_apart_is_not_flagged():
    a, b = rec("a", "Perfect", tempo=100.0), rec("b", "Perfect", tempo=102.0)
    assert find_possible_duplicates([a, b]) == []
    assert a.possible_duplicates == [] and b.possible_duplicates == []


def test_duration_three_percent_apart_is_not_flagged():
    a, b = rec("a", "X", duration=200_000), rec("b", "X", duration=206_200)
    assert find_possible_duplicates([a, b]) == []


def test_tolerances_are_inclusive():
    a, b = rec("a", "X", tempo=100.0, duration=100_000), rec("b", "X", tempo=99.0, duration=98_000)
    assert len(find_possible_duplicates([a, b])) == 2


@pytest.mark.parametrize("field", ["tempo", "duration"])
def test_null_feature_is_not_flagged(field):
    a, b = rec("a", "Perfect"), rec("b", "Perfect", **{field: None})
    assert find_possible_duplicates([a, b]) == []


def test_title_alone_is_not_enough():
    """A cover with the same title but different tempo stays unflagged (D2)."""
    a, b = rec("a", "Hallelujah", tempo=56.0, duration=420_000), rec("b", "Hallelujah", tempo=73.0)
    assert find_possible_duplicates([a, b]) == []


def test_titles_differing_only_in_case_are_compared():
    a, b = rec("a", "Perfect"), rec("b", "PERFECT")
    assert len(find_possible_duplicates([a, b])) == 2


def test_null_titles_are_not_grouped():
    assert find_possible_duplicates([rec("a", None), rec("b", None)]) == []


def test_three_records_link_every_matching_pair():
    a, b, c = rec("a", "X"), rec("b", "X"), rec("c", "X", tempo=120.0)
    d = rec("d", "X", duration=263_000)
    find_possible_duplicates([c, b, a, d])
    assert a.possible_duplicates == ["b", "d"]
    assert b.possible_duplicates == ["a", "d"]
    assert d.possible_duplicates == ["a", "b"]
    assert c.possible_duplicates == []


def test_values_are_never_changed():
    a, b = rec("a", "Perfect"), rec("b", "Perfect", duration=264_000)
    before = (dict(a.values), dict(b.values))
    find_possible_duplicates([a, b])
    assert (a.values, b.values) == before


def test_real_perfect_pair():
    rows = load_file(DATA / PART1).rows + load_file(DATA / PART2).rows
    apply_durations(rows, compute_band(rows))
    records = merge_by_id(rows).records
    issues = find_possible_duplicates(records)
    recs = by_id(records)
    assert recs["0tgVpDi06FyKpA1z0VMD4v"].possible_duplicates == ["7dNsHhGeGU5MV01r06O8gK"]
    assert recs["7dNsHhGeGU5MV01r06O8gK"].possible_duplicates == ["0tgVpDi06FyKpA1z0VMD4v"]
    assert sorted(i.id for i in issues) == ["0tgVpDi06FyKpA1z0VMD4v", "7dNsHhGeGU5MV01r06O8gK"]
    assert issues[0].detail["duration_diff_pct"] == 0.227
    assert sum(bool(r.possible_duplicates) for r in records) == 2
