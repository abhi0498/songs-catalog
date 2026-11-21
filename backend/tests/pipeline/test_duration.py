"""T5: duration band & check. Traces: R-DUR-1..5, D4, P3."""
from pathlib import Path

import pytest

from pipeline.clean import clean_field
from pipeline.duration import Band, apply_durations, check_duration, compute_band
from pipeline.load import load_file
from pipeline.schema import (
    ABSENT, FIELDS_BY_NAME, PART1, PART2, PipelineError, Reason, Source, SourceRow,
)

DATA = Path(__file__).resolve().parents[3] / "data"
R = Reason


def row(id_, dur, segs, file=PART1, idx="0"):
    src = Source(file, idx)
    raw = {"duration_ms": dur, "num_segments": segs}
    clean = {k: clean_field(FIELDS_BY_NAME[k], v, id=id_, source=src) for k, v in raw.items()}
    return SourceRow(id=id_, source=src, raw=raw, clean=clean)


BAND = Band(median=250.0, low=125.0, high=500.0, n=3)


def reasons(c):
    return [i.reason for i in c.issues]


# --- compute_band ----------------------------------------------------------

def test_band_is_median_halved_and_doubled():
    rows = [row("a", 200_000, 1000), row("b", 250_000, 1000), row("c", 400_000, 1000)]
    band = compute_band(rows)
    assert band == Band(median=250.0, low=125.0, high=500.0, n=3)


def test_band_ignores_short_values_and_missing_segments():
    rows = [row("a", 250_000, 1000), row("b", 158, 560), row("c", 300_000, None),
            row("d", 300_000, 0)]  # 0 segments is out_of_range → null
    assert compute_band(rows).n == 1


def test_identical_rows_across_files_count_once():
    rows = [row("a", 200_000, 1000, PART1), row("a", 200_000, 1000, PART2),
            row("b", 300_000, 1000)]
    band = compute_band(rows)
    assert band.n == 2 and band.median == 250.0


def test_same_id_with_different_values_counts_twice():
    rows = [row("a", 200_000, 1000, PART1), row("a", 300_000, 1000, PART2)]
    assert compute_band(rows).n == 2


def test_no_observations_raises():
    with pytest.raises(PipelineError):
        compute_band([row("a", 158, 560)])


# --- check_duration --------------------------------------------------------

def test_in_band_is_kept_without_issue():
    c = check_duration(row("a", 250_000, 1000), BAND)
    assert c.value == 250_000 and c.issues == ()


def test_seconds_value_with_evidence_is_corrected():
    c = check_duration(row("a", 158, 560), BAND)
    assert c.value == 158_000
    assert reasons(c) == [R.UNIT_CORRECTED_S_TO_MS]
    issue = c.issues[0]
    assert issue.raw_value == 158 and issue.final_value == 158_000
    assert issue.detail == {"ms_per_segment": 282.143, "band": [125.0, 500.0], "median": 250.0}


def test_coerced_string_duration_keeps_both_issues_with_corrected_final():
    c = check_duration(row("a", "158", 560), BAND)
    assert c.value == 158_000
    assert reasons(c) == [R.COERCED_FROM_STRING, R.UNIT_CORRECTED_S_TO_MS]
    assert all(i.final_value == 158_000 for i in c.issues)


def test_short_value_that_does_not_fit_as_seconds_is_nulled():
    c = check_duration(row("a", 4, 800), BAND)  # 4 s → 5 ms/segment
    assert c.value is None and reasons(c) == [R.IMPLAUSIBLE_DURATION]
    assert c.issues[0].detail["ms_per_segment"] == 0.005


@pytest.mark.parametrize("dur", [10_000_000, 50_000])  # far above / below band, ≥ 1000
def test_long_value_outside_band_is_nulled_never_rescaled(dur):
    c = check_duration(row("a", dur, 800), BAND)
    assert c.value is None and reasons(c) == [R.IMPLAUSIBLE_DURATION]
    assert c.issues[0].raw_value == dur


@pytest.mark.parametrize("dur", [0, -5])
def test_zero_or_negative_is_implausible(dur):
    assert reasons(check_duration(row("a", dur, 800), BAND)) == [R.IMPLAUSIBLE_DURATION]


@pytest.mark.parametrize("segs", [None, ABSENT, 0])
def test_no_segments_long_value_kept_unverified(segs):
    c = check_duration(row("a", 250_000, segs), BAND)
    assert c.value == 250_000 and reasons(c) == [R.DURATION_UNVERIFIED]
    assert c.issues[0].final_value == 250_000


@pytest.mark.parametrize("segs", [None, 0])
def test_no_segments_short_value_nulled(segs):
    c = check_duration(row("a", 158, segs), BAND)
    assert c.value is None and reasons(c) == [R.IMPLAUSIBLE_DURATION]


def test_null_duration_passes_through_unchanged():
    r = row("a", None, 800)
    assert check_duration(r, BAND) == r.clean["duration_ms"]


def test_band_edges_are_inclusive():
    assert check_duration(row("a", 125_000, 1000), BAND).issues == ()
    assert check_duration(row("a", 500_000, 1000), BAND).issues == ()


# --- real data -------------------------------------------------------------

@pytest.fixture(scope="module")
def real_rows():
    return load_file(DATA / PART1).rows + load_file(DATA / PART2).rows


def test_real_band(real_rows):
    band = compute_band(real_rows)
    assert band.n == 22
    assert band.median == pytest.approx(272.8, abs=0.05)
    assert band.low == pytest.approx(136.4, abs=0.05)
    assert band.high == pytest.approx(545.6, abs=0.1)


def test_real_corrections(real_rows):
    before = {(r.source, r.id): r.clean["duration_ms"].value for r in real_rows}
    apply_durations(real_rows, compute_band(real_rows))
    after = {(r.source, r.id): r.clean["duration_ms"] for r in real_rows}

    changed = {key[1]: c.value for key, c in after.items() if c.value != before[key]}
    assert changed == {
        "3KkXRkHbMCARz0aVfEt68P": 158_000,   # Sunflower
        "4VqPOruhp5EdPBeR92t6lQ": 270_000,   # Uptown Funk
        "2QjOHCTQ1Jl3zawyYOpxh6": 356_000,   # Sweet Child O Mine
    }
    flagged = sorted(
        (key[1], i.reason) for key, c in after.items() for i in c.issues
    )
    assert flagged == sorted((id_, R.UNIT_CORRECTED_S_TO_MS) for id_ in changed)
