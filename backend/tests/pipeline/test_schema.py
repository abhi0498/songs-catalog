"""T2: schema tests. Traces: requirements §3 range table, §4, R-MOOD-1."""
import dataclasses

import pytest

from pipeline import schema
from pipeline.schema import (
    ABSENT,
    FIELDS,
    FIELDS_BY_NAME,
    ID_FIELD,
    PART1,
    PART2,
    SEVERITY,
    Cleaned,
    Issue,
    Reason,
    Severity,
    Source,
    SourceRow,
    columns_for,
)

# --- Field table -----------------------------------------------------------

EXPECTED_ORDER = [
    "title",
    "danceability",
    "energy",
    "acousticness",
    "valence",
    "tempo",
    "duration_ms",
    "num_sections",
    "num_segments",
    "mood",
]


def test_field_order_matches_requirements():
    assert [f.name for f in FIELDS] == EXPECTED_ORDER


def test_field_kinds():
    kinds = {f.name: f.kind for f in FIELDS}
    assert kinds["title"] == "str"
    for name in ("danceability", "energy", "acousticness", "valence", "tempo"):
        assert kinds[name] == "float"
    for name in ("duration_ms", "num_sections", "num_segments", "mood"):
        assert kinds[name] == "int"


def test_valence_is_part2_only_everything_else_in_both():
    for f in FIELDS:
        expected = {PART2} if f.name == "valence" else {PART1, PART2}
        assert f.sources == frozenset(expected), f.name


def test_columns_for_each_file_include_id():
    assert columns_for(PART1) == frozenset({ID_FIELD, *EXPECTED_ORDER} - {"valence"})
    assert columns_for(PART2) == frozenset({ID_FIELD, *EXPECTED_ORDER})


def test_columns_for_unknown_file_is_empty():
    assert columns_for("other.json") == frozenset()


def test_title_has_no_domain_check():
    assert FIELDS_BY_NAME["title"].check is None


# --- Domain checks ---------------------------------------------------------

@pytest.mark.parametrize("name", ["danceability", "energy", "acousticness", "valence"])
@pytest.mark.parametrize(
    "value, ok",
    [(0, True), (0.0, True), (0.5, True), (1, True), (1.0, True),
     (-0.0001, False), (1.0001, False), (1.42, False), (-0.05, False)],
)
def test_unit_interval_fields(name, value, ok):
    assert FIELDS_BY_NAME[name].check(value) is ok


@pytest.mark.parametrize("value, ok", [(0.0001, True), (120.5, True), (0, False), (-1, False)])
def test_tempo_must_be_positive(value, ok):
    assert FIELDS_BY_NAME["tempo"].check(value) is ok


@pytest.mark.parametrize("value, ok", [(1, True), (215000, True), (0, False), (-5, False)])
def test_duration_must_be_positive(value, ok):
    assert FIELDS_BY_NAME["duration_ms"].check(value) is ok


@pytest.mark.parametrize("name", ["num_sections", "num_segments"])
@pytest.mark.parametrize("value, ok", [(1, True), (1490, True), (0, False), (-1, False)])
def test_counts_at_least_one(name, value, ok):
    assert FIELDS_BY_NAME[name].check(value) is ok


@pytest.mark.parametrize("value, ok", [(0, True), (1, True), (2, False), (-1, False)])
def test_mood_is_binary(value, ok):
    assert FIELDS_BY_NAME["mood"].check(value) is ok


# --- Reasons & severity ----------------------------------------------------

EXPECTED_REASONS = {
    "missing_absent": "warning",
    "missing_null": "warning",
    "missing_na": "warning",
    "missing_empty": "warning",
    "not_in_source": "info",
    "coerced_from_string": "info",
    "whitespace_normalized": "info",
    "unparseable": "warning",
    "not_integer": "warning",
    "out_of_range": "warning",
    "implausible_duration": "warning",
    "unit_corrected_s_to_ms": "warning",
    "duration_unverified": "info",
    "source_conflict": "warning",
    "possible_duplicate": "info",
    "missing_id": "error",
}


def test_reason_codes_match_requirements_table():
    assert {r.value for r in Reason} == set(EXPECTED_REASONS)
    assert len(Reason) == 16


def test_every_reason_has_its_severity():
    assert set(SEVERITY) == set(Reason)
    for reason in Reason:
        assert SEVERITY[reason] == Severity(EXPECTED_REASONS[reason.value]), reason


def test_reasons_serialize_as_plain_strings():
    assert Reason.OUT_OF_RANGE == "out_of_range"
    assert str(Reason.SOURCE_CONFLICT) == "source_conflict"


# --- Constants -------------------------------------------------------------

def test_tunable_constants():
    assert schema.DUP_TEMPO_TOL == 0.01
    assert schema.DUP_DURATION_TOL == 0.02
    assert schema.BAND_FACTOR == 2
    assert schema.SECONDS_THRESHOLD == 1000


# --- ABSENT sentinel -------------------------------------------------------

def test_absent_is_distinct_from_none_and_singleton():
    assert ABSENT is not None
    assert ABSENT != None  # noqa: E711
    assert schema.ABSENT is ABSENT
    assert repr(ABSENT) == "ABSENT"


# --- Core types ------------------------------------------------------------

SRC = Source("songs_part1.json", "3")


def test_source_is_frozen_and_hashable():
    assert {SRC, Source("songs_part1.json", "3")} == {SRC}
    with pytest.raises(dataclasses.FrozenInstanceError):
        SRC.row = "4"  # type: ignore[misc]


def test_issue_exposes_severity_from_reason():
    issue = Issue("x", "danceability", SRC, 1.42, None, Reason.OUT_OF_RANGE)
    assert issue.severity is Severity.WARNING
    assert issue.detail is None


def test_cleaned_with_value_may_have_no_issues():
    assert Cleaned(0.5).issues == ()


def test_cleaned_null_requires_an_issue():
    """value None must always come with a reason (P2)."""
    with pytest.raises(ValueError):
        Cleaned(None)
    issue = Issue("x", "energy", SRC, ABSENT, None, Reason.MISSING_ABSENT)
    assert Cleaned(None, (issue,)).value is None


def test_source_row_holds_raw_and_clean():
    row = SourceRow(id="x", source=SRC, raw={"energy": ABSENT}, clean={})
    assert row.raw["energy"] is ABSENT
