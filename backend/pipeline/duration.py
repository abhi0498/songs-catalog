"""Duration reference band and plausibility check (design §5.3, R-DUR, D4).

Every duration is checked against ms-per-segment from the data itself. The
only correction ever made is seconds → ms, and only with that evidence (P3).
"""
from __future__ import annotations

import dataclasses
import statistics
from dataclasses import dataclass
from typing import Any, Iterable

from .schema import (
    BAND_FACTOR,
    SECONDS_THRESHOLD,
    Cleaned,
    Issue,
    PipelineError,
    Reason,
    SourceRow,
)

DURATION = "duration_ms"
SEGMENTS = "num_segments"


@dataclass(frozen=True)
class Band:
    median: float
    low: float
    high: float
    n: int

    def contains(self, ms_per_segment: float) -> bool:
        return self.low <= ms_per_segment <= self.high

    def detail(self, ms_per_segment: float) -> dict[str, Any]:
        return {
            "ms_per_segment": round(ms_per_segment, 3),
            "band": [round(self.low, 3), round(self.high, 3)],
            "median": round(self.median, 3),
        }


def compute_band(rows: Iterable[SourceRow]) -> Band:
    """Median ms/segment over unique (id, duration, segments) observations (R-DUR-1)."""
    observations: dict[tuple[str, int, int], float] = {}
    for r in rows:
        dur, segs = r.clean[DURATION].value, r.clean[SEGMENTS].value
        if dur is not None and segs is not None and dur >= SECONDS_THRESHOLD:
            observations[(r.id, dur, segs)] = dur / segs
    if not observations:
        raise PipelineError(
            "no rows with a usable duration_ms and num_segments; cannot build the duration band"
        )
    median = statistics.median(observations.values())
    return Band(median=median, low=median / BAND_FACTOR, high=median * BAND_FACTOR,
                n=len(observations))


def check_duration(row: SourceRow, band: Band) -> Cleaned:
    """Apply R-DUR-2/3 to one source row's cleaned duration."""
    current = row.clean[DURATION]
    dur = current.value
    if dur is None:
        return current
    segs = row.clean[SEGMENTS].value

    if segs is None:  # R-DUR-3: nothing to check against
        if dur >= SECONDS_THRESHOLD:
            return _with(row, current, dur, Reason.DURATION_UNVERIFIED, None)
        return _with(row, current, None, Reason.IMPLAUSIBLE_DURATION, None)

    ratio = dur / segs
    if band.contains(ratio):
        return current

    if dur < SECONDS_THRESHOLD:
        as_ms = dur * 1000
        if band.contains(as_ms / segs):
            return _with(row, current, as_ms, Reason.UNIT_CORRECTED_S_TO_MS,
                         band.detail(as_ms / segs))

    return _with(row, current, None, Reason.IMPLAUSIBLE_DURATION, band.detail(ratio))


def apply_durations(rows: Iterable[SourceRow], band: Band) -> None:
    for r in rows:
        r.clean[DURATION] = check_duration(r, band)


def _with(row: SourceRow, current: Cleaned, value: Any, reason: Reason,
          detail: dict[str, Any] | None) -> Cleaned:
    """New Cleaned: earlier issues re-pointed at the new final value, plus one new issue."""
    earlier = tuple(dataclasses.replace(i, final_value=value) for i in current.issues)
    new = Issue(id=row.id, field=DURATION, source=row.source, raw_value=row.raw[DURATION],
                final_value=value, reason=reason, detail=detail)
    return Cleaned(value, earlier + (new,))
