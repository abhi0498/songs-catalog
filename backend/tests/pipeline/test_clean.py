"""T3: value cleaning. Traces: R-MISS-1, R-TYPE-1..4, R-RNG-1..2, R-TXT-1..3, P1, P2."""
import math
import unicodedata

import pytest

from pipeline.clean import (
    check_range,
    classify_missing,
    clean_field,
    normalize_text,
    to_int,
    to_number,
)
from pipeline.schema import ABSENT, FIELDS_BY_NAME, Reason, Source

R = Reason
SRC = Source("songs_part1.json", "0")


def clean(name, raw):
    return clean_field(FIELDS_BY_NAME[name], raw, id="x", source=SRC)


def reasons(cleaned):
    return [i.reason for i in cleaned.issues]


# --- classify_missing ------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        (ABSENT, R.MISSING_ABSENT),
        (None, R.MISSING_NULL),
        ("N/A", R.MISSING_NA),
        (" n/a ", R.MISSING_NA),
        ("n/A", R.MISSING_NA),
        ("", R.MISSING_EMPTY),
        ("   ", R.MISSING_EMPTY),
        ("\t \n", R.MISSING_EMPTY),
        ("0.5", None),
        (0, None),
        (0.0, None),
        (False, None),  # not missing; rejected later as unparseable
        ("NA", None),   # only "N/A" is a marker; "NA" is just unparseable
    ],
)
def test_classify_missing(raw, expected):
    assert classify_missing(raw) == expected


# --- normalize_text --------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        (" 4 walls  ", "4 walls"),
        ("a   b\t\nc", "a b c"),
        ("Naïve", "Naïve"),
        ("Café del Mar", "Café del Mar"),
        ("God's Plan", "God's Plan"),
        ("3AM", "3AM"),
    ],
)
def test_normalize_text(raw, expected):
    assert normalize_text(raw) == expected


def test_normalize_text_returns_nfc():
    nfd = unicodedata.normalize("NFD", "Naïve")
    assert nfd != "Naïve"
    assert normalize_text(nfd) == "Naïve"


# --- to_number -------------------------------------------------------------

@pytest.mark.parametrize(
    "raw, value, reason",
    [
        (0.521, 0.521, None),
        (7, 7, None),
        ("0.521", 0.521, R.COERCED_FROM_STRING),
        (" 108.73 ", 108.73, R.COERCED_FROM_STRING),
        ("-0.05", -0.05, R.COERCED_FROM_STRING),
        ("1e3", 1000.0, R.COERCED_FROM_STRING),
        (".5", 0.5, R.COERCED_FROM_STRING),
        ("8", 8.0, R.COERCED_FROM_STRING),
    ],
)
def test_to_number_ok(raw, value, reason):
    got, why = to_number(raw)
    assert got == value and why == reason


@pytest.mark.parametrize(
    "raw",
    [
        "abc", "1.2.3", "0x10", "1_000", "١٢",  # not plain decimal
        "nan", "NaN", "inf", "-Infinity", "+inf",  # R-TYPE-2
        float("nan"), float("inf"), -math.inf,
        True, False,  # R-TYPE-4
        [1], {"v": 1},
    ],
)
def test_to_number_unparseable(raw):
    assert to_number(raw) == (None, R.UNPARSEABLE)


# --- to_int ----------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [(8, 8), (8.0, 8), (0.0, 0), (215000.0, 215000)])
def test_to_int_ok(raw, expected):
    value, why = to_int(raw)
    assert value == expected and type(value) is int and why is None


@pytest.mark.parametrize("raw", [8.5, 0.1, -1.25])
def test_to_int_rejects_non_integral(raw):
    assert to_int(raw) == (None, R.NOT_INTEGER)


# --- check_range -----------------------------------------------------------

@pytest.mark.parametrize(
    "name, value, ok",
    [
        ("danceability", 0, True), ("danceability", 1, True),
        ("danceability", 1.42, False), ("acousticness", -0.05, False),
        ("tempo", 0, False), ("tempo", 0.1, True),
        ("mood", 2, False), ("num_segments", 0, False),
    ],
)
def test_check_range(name, value, ok):
    assert check_range(FIELDS_BY_NAME[name], value) == (None if ok else R.OUT_OF_RANGE)


def test_check_range_skips_fields_without_check():
    assert check_range(FIELDS_BY_NAME["title"], "anything") is None


# --- clean_field: missing --------------------------------------------------

@pytest.mark.parametrize(
    "raw, reason",
    [(ABSENT, R.MISSING_ABSENT), (None, R.MISSING_NULL), ("N/A", R.MISSING_NA), ("  ", R.MISSING_EMPTY)],
)
@pytest.mark.parametrize("name", ["energy", "duration_ms", "title"])
def test_clean_field_missing(name, raw, reason):
    c = clean(name, raw)
    assert c.value is None
    assert reasons(c) == [reason]
    issue = c.issues[0]
    assert (issue.id, issue.field, issue.source) == ("x", name, SRC)
    assert issue.raw_value is raw and issue.final_value is None


# --- clean_field: numbers --------------------------------------------------

def test_numeric_string_is_coerced_and_logged():
    c = clean("danceability", "0.521")
    assert c.value == 0.521
    assert reasons(c) == [R.COERCED_FROM_STRING]
    assert c.issues[0].raw_value == "0.521" and c.issues[0].final_value == 0.521


def test_clean_number_has_no_issues():
    c = clean("energy", 0.673)
    assert c.value == 0.673 and c.issues == ()


def test_float_fields_come_out_as_float():
    c = clean("tempo", 104)
    assert c.value == 104.0 and type(c.value) is float


def test_unparseable_string_is_nulled():
    c = clean("energy", "loud")
    assert c.value is None and reasons(c) == [R.UNPARSEABLE]
    assert c.issues[0].raw_value == "loud"


@pytest.mark.parametrize("raw", ["nan", float("nan"), "Infinity"])
def test_nan_and_inf_are_unparseable(raw):
    assert reasons(clean("tempo", raw)) == [R.UNPARSEABLE]


def test_booleans_are_never_numbers():
    assert reasons(clean("mood", True)) == [R.UNPARSEABLE]


def test_integral_float_accepted_for_int_field():
    c = clean("num_sections", 8.0)
    assert c.value == 8 and type(c.value) is int and c.issues == ()


def test_non_integral_float_rejected_for_int_field():
    c = clean("num_sections", 8.5)
    assert c.value is None and reasons(c) == [R.NOT_INTEGER]


@pytest.mark.parametrize(
    "name, raw",
    [("danceability", 1.42), ("acousticness", -0.05), ("tempo", 0), ("mood", 2)],
)
def test_out_of_range_is_nulled_not_clamped(name, raw):
    c = clean(name, raw)
    assert c.value is None
    assert reasons(c) == [R.OUT_OF_RANGE]
    assert c.issues[0].raw_value == raw and c.issues[0].final_value is None


def test_coerced_then_out_of_range_logs_both_with_null_final():
    c = clean("danceability", "1.42")
    assert c.value is None
    assert reasons(c) == [R.COERCED_FROM_STRING, R.OUT_OF_RANGE]
    assert all(i.final_value is None for i in c.issues)


def test_range_edges_are_valid():
    assert clean("energy", 0).value == 0.0
    assert clean("energy", 1).value == 1.0


def test_duration_skips_range_check_here():
    """Duration domain is handled by duration.py (design §5.2/5.3)."""
    c = clean("duration_ms", 158)
    assert c.value == 158 and c.issues == ()
    assert clean("duration_ms", 0).value == 0


# --- clean_field: text -----------------------------------------------------

def test_title_whitespace_is_normalized_and_logged():
    c = clean("title", " 4 walls  ")
    assert c.value == "4 walls"
    assert reasons(c) == [R.WHITESPACE_NORMALIZED]
    assert c.issues[0].raw_value == " 4 walls  " and c.issues[0].final_value == "4 walls"


def test_title_keeps_diacritics_with_no_issue():
    c = clean("title", "Naïve")
    assert c.value == "Naïve" and c.issues == ()


def test_nfd_title_becomes_nfc_without_whitespace_issue():
    c = clean("title", unicodedata.normalize("NFD", "Café del Mar"))
    assert c.value == "Café del Mar" and c.issues == ()


def test_non_string_title_is_unparseable():
    c = clean("title", 21)
    assert c.value is None and reasons(c) == [R.UNPARSEABLE]
